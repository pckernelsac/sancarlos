"""Helpers para determinar el alcance (nivel/grado) de un usuario."""
from app.models.student import (
    NIVELES, GRADOS_INICIAL, GRADOS_PRIMARIA, GRADOS_SECUNDARIA,
)
from app.models.user import RoleEnum

GRADOS_POR_NIVEL = {
    "INICIAL": GRADOS_INICIAL,
    "PRIMARIA": GRADOS_PRIMARIA,
    "SECUNDARIA": GRADOS_SECUNDARIA,
}


def user_allowed_niveles(current_user=None):
    """Niveles visibles para el usuario.
    DOCENTE/AUXILIAR con nivel asignado ven solo ese nivel; ADMIN ve todos."""
    if current_user and current_user.role in (RoleEnum.DOCENTE, RoleEnum.AUXILIAR) and current_user.nivel:
        return [current_user.nivel]
    return NIVELES


def user_allowed_grados(nivel=None, current_user=None):
    """Grados visibles para el usuario según el nivel.
    DOCENTE/AUXILIAR con grado asignado ven solo ese grado;
    de lo contrario ven los grados correspondientes al nivel."""
    if current_user and current_user.role in (RoleEnum.DOCENTE, RoleEnum.AUXILIAR) and current_user.grado:
        return [current_user.grado]
    if current_user:
        nivel = nivel or current_user.nivel or "PRIMARIA"
    else:
        nivel = nivel or "PRIMARIA"
    return GRADOS_POR_NIVEL.get(nivel, GRADOS_PRIMARIA)


def sanitize_nivel_grado(nivel_req, grado_req, current_user=None):
    """Valida y corrige nivel/grado del request contra los permisos del usuario.
    Retorna (nivel, grado) seguros."""
    niveles = user_allowed_niveles(current_user)
    nivel = nivel_req if nivel_req in niveles else niveles[0]

    grados = user_allowed_grados(nivel, current_user)
    grado = grado_req if grado_req in grados else ""

    return nivel, grado
