import os
from typing import Literal

from dotenv import load_dotenv

load_dotenv()

_DEV_SECRET = "dev-secret-insecuro"


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or str(v).strip() == "":
        return default
    return int(str(v).strip())


def _normalize_database_url(url: str) -> str:
    """Compatibilidad con URLs `postgres://` (p. ej. algunos hosts) y driver explícito."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://") :]
    return url


def _validate_secret_key_for_env(secret_key: str, app_env: str) -> str:
    if app_env == "production":
        if not secret_key or secret_key == _DEV_SECRET or len(secret_key) < 32:
            raise RuntimeError(
                "SECRET_KEY obligatoria en producción: defina una cadena aleatoria de al menos 32 "
                "caracteres (p. ej. openssl rand -hex 32). No use el valor de desarrollo."
            )
        return secret_key
    if not secret_key:
        return _DEV_SECRET
    return secret_key


class Config:
    APP_ENV = os.environ.get("APP_ENV", "development")
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    # Local: crear BD `sancarlos` y usuario/contraseña en PostgreSQL, o definir DATABASE_URL en .env
    DATABASE_URL = _normalize_database_url(
        os.environ.get(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@127.0.0.1:5432/sancarlos",
        )
    )
    DEBUG = APP_ENV == "development"
    # Sesión: en producción Secure=True por defecto; en local HTTP usar SESSION_COOKIE_SECURE=0
    SESSION_COOKIE_SECURE: bool = False
    SESSION_SAME_SITE: Literal["lax", "strict", "none"] = "lax"
    # Cabeceras: CSP completo opcional (sobrescribe el valor por defecto de SecurityHeadersMiddleware)
    CONTENT_SECURITY_POLICY: str | None = os.environ.get("CONTENT_SECURITY_POLICY") or None
    # Rate limit login (intentos fallidos / ventana en segundos); 0 = desactivado
    LOGIN_RATE_LIMIT_MAX_FAILURES: int = _env_int("LOGIN_RATE_LIMIT_MAX_FAILURES", 15)
    LOGIN_RATE_LIMIT_WINDOW_SEC: int = _env_int("LOGIN_RATE_LIMIT_WINDOW_SEC", 300)


def get_config() -> Config:
    cfg = Config()
    cfg.DATABASE_URL = _normalize_database_url(cfg.DATABASE_URL)
    cfg.SECRET_KEY = _validate_secret_key_for_env(cfg.SECRET_KEY or "", cfg.APP_ENV)
    is_prod = cfg.APP_ENV == "production"
    cfg.SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", default=is_prod)
    same_site = (os.environ.get("SESSION_SAME_SITE") or "lax").strip().lower()
    if same_site in ("lax", "strict", "none"):
        cfg.SESSION_SAME_SITE = same_site  # type: ignore[assignment]
    return cfg
