"""Mensajes seguros para el usuario y registro de excepciones (sin filtrar datos sensibles)."""
import logging

logger = logging.getLogger("app.errors")

GENERIC_USER_MESSAGE = "No se pudo completar la operación. Intente de nuevo o contacte al administrador."
GENERIC_FLASH_MESSAGE = "Ocurrió un error inesperado. Intente de nuevo o contacte al administrador."


def log_unexpected_exc(exc: BaseException, context: str = "") -> None:
    """Registra la traza completa en el servidor; no exponer detalles al cliente."""
    msg = context or "Unexpected error"
    logger.error("%s", msg, exc_info=exc)
