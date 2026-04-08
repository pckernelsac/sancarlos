"""Protección CSRF: token en sesión + validación en métodos mutadores."""
import secrets
import hmac
from urllib.parse import urlparse

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

CSRF_SESSION_KEY = "_csrf_token"
CSRF_FORM_FIELD = "csrf_token"
HEADER_NAMES = ("X-CSRFToken", "X-CSRF-Token")


def ensure_csrf_token(request: Request) -> str:
    tok = request.session.get(CSRF_SESSION_KEY)
    if not tok:
        tok = secrets.token_urlsafe(32)
        request.session[CSRF_SESSION_KEY] = tok
    return tok


def _csrf_matches(request: Request, submitted: str | None) -> bool:
    if not submitted:
        return False
    expected = request.session.get(CSRF_SESSION_KEY)
    if not expected:
        return False
    return hmac.compare_digest(str(submitted), str(expected))


def _request_host(request: Request) -> str:
    if request.url.hostname:
        return request.url.hostname.lower()
    host = request.headers.get("host") or ""
    return host.split(":")[0].lower()


def _same_site_legit(request: Request) -> bool:
    """
    Petición POST probablemente originada en este sitio (sin leer el body).
    Los fetch/XHR con JSON deben enviar X-CSRFToken; los formularios HTML suelen
    incluir Origin o Referer del mismo host.
    """
    host = _request_host(request)
    if not host:
        return False
    origin = request.headers.get("origin")
    if origin:
        try:
            oh = urlparse(origin).hostname
            if oh:
                return oh.lower() == host
        except Exception:
            return False
    ref = request.headers.get("referer")
    if ref:
        try:
            rh = urlparse(ref).hostname
            if rh:
                return rh.lower() == host
        except Exception:
            return False
    return False


async def validate_csrf_for_request(request: Request) -> None:
    ensure_csrf_token(request)
    for name in HEADER_NAMES:
        hdr = request.headers.get(name)
        if hdr and _csrf_matches(request, hdr):
            return
    ct = (request.headers.get("content-type") or "").lower()
    if "application/json" in ct:
        raise HTTPException(status_code=403, detail="CSRF: falta cabecera X-CSRFToken")
    if _same_site_legit(request):
        return
    raise HTTPException(
        status_code=403,
        detail="CSRF: envía la cabecera X-CSRFToken o accede desde el mismo sitio.",
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    """Debe montarse *antes* que SessionMiddleware en add_middleware (Session queda exterior)."""

    async def dispatch(self, request: Request, call_next):
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)
        if request.url.path.startswith("/static"):
            return await call_next(request)
        try:
            await validate_csrf_for_request(request)
        except HTTPException as exc:
            from fastapi.responses import JSONResponse, PlainTextResponse

            accept = (request.headers.get("accept") or "").lower()
            if "text/html" in accept:
                return PlainTextResponse(exc.detail, status_code=exc.status_code)
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        return await call_next(request)
