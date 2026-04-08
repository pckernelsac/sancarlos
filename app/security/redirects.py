"""Utilidades para redirecciones seguras (evitar open redirect)."""
from urllib.parse import urlparse


def safe_next_url(next_raw: str | None, default: str = "/dashboard") -> str:
    """
    Solo permite rutas relativas internas que empiecen por un solo '/'.
    Rechaza esquemas, hosts y protocol-relative URLs.
    """
    if not next_raw or not next_raw.strip():
        return default
    raw = next_raw.strip()
    parsed = urlparse(raw)
    if parsed.scheme or parsed.netloc:
        return default
    path = parsed.path or raw
    if not path.startswith("/") or path.startswith("//"):
        return default
    if "\n" in path or "\r" in path:
        return default
    return path or default
