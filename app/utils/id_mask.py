"""Ofuscación de IDs numéricos para URLs públicas.

Usa itsdangerous para firmar el ID,
generando un token URL-safe que oculta el valor real.
"""

from itsdangerous import URLSafeSerializer, BadSignature
from fastapi import HTTPException

# Se inicializa al crear la app
_secret_key: str = "dev-secret-insecuro"


def init_mask(secret_key: str):
    global _secret_key
    _secret_key = secret_key


def _get_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(_secret_key, salt="student-id")


def encode_id(student_id: int) -> str:
    """Convierte un ID numérico a un token ofuscado URL-safe."""
    return _get_serializer().dumps(student_id)


def decode_id(token: str) -> int:
    """Decodifica el token ofuscado. Lanza 404 si es inválido."""
    try:
        return _get_serializer().loads(token)
    except BadSignature:
        raise HTTPException(status_code=404, detail="Recurso no encontrado")
