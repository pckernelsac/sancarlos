import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.security.csrf import CSRFMiddleware, ensure_csrf_token
from app.security.security_headers import SecurityHeadersMiddleware
from app.security.rate_limit import configure_login_limiter
from app.utils.safe_errors import log_unexpected_exc
from config.settings import get_config
from app.database import db
from app.utils.id_mask import init_mask, encode_id

APP_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = APP_DIR / "templates"
STATIC_DIR = APP_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

_log_db = logging.getLogger("app.database")


def create_app() -> FastAPI:
    cfg = get_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Por si el worker arranca sin haber pasado por el bloque síncrono (defensa en profundidad).
        try:
            db.ensure_schema()
            _log_db.warning("sancarlos: esquema de base de datos verificado (ensure_schema OK)")
        except Exception:
            _log_db.exception("sancarlos: fallo al asegurar esquema de BD")
            raise
        yield

    app = FastAPI(
        title="San Carlos — Sistema Académico",
        docs_url=None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # --- Base de datos ---
    db.init(cfg.DATABASE_URL)

    configure_login_limiter(cfg.LOGIN_RATE_LIMIT_MAX_FAILURES, cfg.LOGIN_RATE_LIMIT_WINDOW_SEC)

    # Orden (último registrado = más exterior en la petición): cabeceras → sesión → CSRF
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=cfg.SECRET_KEY,
        same_site=cfg.SESSION_SAME_SITE,
        https_only=cfg.SESSION_COOKIE_SECURE,
    )
    app.add_middleware(SecurityHeadersMiddleware, content_security_policy=cfg.CONTENT_SECURITY_POLICY)

    # --- ID mask ---
    init_mask(cfg.SECRET_KEY)

    # --- Archivos estáticos ---
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # --- Importar modelos (registra las tablas) ---
    from app import models as _models  # noqa

    # Crear tablas y comprobar que exista al menos `users` (evita UndefinedTable en /auth/login).
    db.ensure_schema()

    # --- Routers (equivalente a Blueprints) ---
    from app.auth.routes import router as auth_router
    from app.routes.main import router as main_router
    from app.routes.students import router as students_router
    from app.routes.grades import router as grades_router
    from app.routes.attendance import router as attendance_router
    from app.routes.behavior import router as behavior_router
    from app.routes.reports import router as reports_router
    from app.routes.admin import router as admin_router
    from app.routes.ranking import router as ranking_router
    from app.routes.consolidado import router as consolidado_router
    from app.routes.parents import router as parents_router

    app.include_router(auth_router, prefix="/auth")
    app.include_router(main_router)
    app.include_router(students_router, prefix="/students")
    app.include_router(grades_router, prefix="/grades")
    app.include_router(attendance_router, prefix="/attendance")
    app.include_router(behavior_router, prefix="/behavior")
    app.include_router(reports_router, prefix="/reports")
    app.include_router(admin_router, prefix="/admin")
    app.include_router(ranking_router, prefix="/ranking")
    app.include_router(consolidado_router, prefix="/consolidado")
    app.include_router(parents_router, prefix="/parents")

    # --- Filtro Jinja mask_id ---
    templates.env.filters["mask_id"] = encode_id

    # --- Globals de Jinja2 ---
    _setup_jinja_globals(app)

    # --- Middleware: log de excepciones no controladas (sin filtrar datos al cliente) ---
    @app.middleware("http")
    async def log_unhandled_exceptions(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            path = request.url.path
            log_unexpected_exc(exc, f"unhandled request exception path={path}")
            raise

    # --- Middleware para limpiar la sesión de BD después de cada request ---
    @app.middleware("http")
    async def db_session_middleware(request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        finally:
            db.remove_session()

    # --- Error handlers ---
    @app.exception_handler(404)
    async def not_found(request: Request, exc):
        ctx = _base_context(request)
        return templates.TemplateResponse("errors/404.html", ctx, status_code=404)

    @app.exception_handler(403)
    async def forbidden(request: Request, exc):
        ctx = _base_context(request)
        return templates.TemplateResponse("errors/403.html", ctx, status_code=403)

    @app.exception_handler(500)
    async def server_error(request: Request, exc):
        log_unexpected_exc(exc, "HTTP 500")
        ctx = _base_context(request)
        return templates.TemplateResponse("errors/500.html", ctx, status_code=500)

    return app


# ══════════════════════════════════════════════════════════════════════════════
#  Jinja2 globals — replican url_for, get_flashed_messages, current_user, etc.
# ══════════════════════════════════════════════════════════════════════════════

def _setup_jinja_globals(app: FastAPI):
    """Registra funciones globales en Jinja2 para compatibilidad con Flask."""

    # Mapa de rutas: endpoint_name → (path_template, path_param_names)
    # Se construye al primer request
    _route_cache: dict = {}

    def _build_route_cache():
        if _route_cache:
            return
        for route in app.routes:
            name = getattr(route, "name", None)
            path = getattr(route, "path", None)
            if name and path:
                # Extraer nombres de path params: {param} → param
                import re
                param_names = set(re.findall(r"\{(\w+)\}", path))
                _route_cache[name] = (path, param_names)

    def url_for(__name: str, **kwargs) -> str:
        """Replica Flask's url_for: separa path params de query params."""
        _build_route_cache()

        # Static files
        if __name == "static":
            filename = kwargs.get("filename", "")
            return f"/static/{filename}"

        info = _route_cache.get(__name)
        if not info:
            return f"/#{__name}"

        path_template, param_names = info
        path_kwargs = {k: kwargs[k] for k in param_names if k in kwargs}
        query_kwargs = {k: v for k, v in kwargs.items()
                        if k not in param_names and v is not None and v != ""}

        # Reemplazar {param} en el path
        path = path_template
        for k, v in path_kwargs.items():
            path = path.replace(f"{{{k}}}", str(v))

        if query_kwargs:
            path += "?" + urlencode(query_kwargs)
        return path

    def get_flashed_messages(with_categories=False):
        """Lee y limpia mensajes flash de la sesión."""
        # Necesitamos acceder al request actual — usamos un truco con contextvars
        # Los mensajes se inyectan como variable de contexto en render()
        return []  # Se manejan en render()

    templates.env.globals["url_for"] = url_for


def _base_context(request: Request) -> dict:
    """Contexto base para todas las respuestas de template."""
    from app.auth.dependencies import get_current_user
    current_user = get_current_user(request)
    ensure_csrf_token(request)

    def csrf_token() -> str:
        return request.session.get("_csrf_token", "") or ""

    # Flash messages: leer de sesión y limpiar
    messages = request.session.pop("_flashes", [])

    # Simular request.endpoint y request.blueprint para compatibilidad con base.html
    scope = request.scope
    route = scope.get("route")
    endpoint_name = getattr(route, "name", "") if route else ""

    class _RequestCompat:
        """Proxy que agrega endpoint/blueprint al request de Starlette."""
        def __init__(self, req, ep):
            self._req = req
            self.endpoint = ep or ""
            self.blueprint = ep.split(".")[0] if ep and "." in ep else ""
        def __getattr__(self, name):
            return getattr(self._req, name)

    request_compat = _RequestCompat(request, endpoint_name)

    from app.services.feature_flags import is_eda_matrix_enabled_for_docentes

    return {
        "request": request_compat,
        "current_user": current_user,
        "csrf_token": csrf_token,
        "get_flashed_messages": lambda with_categories=False: messages if with_categories else [m for _, m in messages],
        "eda_matrix_docente_enabled": is_eda_matrix_enabled_for_docentes(),
    }


def render(request: Request, template_name: str, status_code: int = 200, **context) -> HTMLResponse:
    """Helper para renderizar templates con contexto base incluido."""
    ctx = _base_context(request)
    ctx.update(context)
    return templates.TemplateResponse(template_name, ctx, status_code=status_code)


def flash(request: Request, message: str, category: str = "info"):
    """Agrega un mensaje flash a la sesión (equivalente a Flask's flash)."""
    if "_flashes" not in request.session:
        request.session["_flashes"] = []
    request.session["_flashes"].append([category, message])


def redirect_to(url: str, status_code: int = 303) -> RedirectResponse:
    """Redirect helper."""
    return RedirectResponse(url=url, status_code=status_code)
