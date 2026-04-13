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


def _docente_scope_from_courses(user):
    """Deriva niveles y grados del docente a partir de sus cursos asignados
    (y opcionalmente de user.nivel / user.grado como fallback)."""
    from app.models.academic import Course
    niveles: set[str] = set()
    grados: set[str] = set()
    if user.nivel:
        niveles.add(user.nivel)
    if user.grado:
        grados.add(user.grado)
    course_ids = user.assigned_course_ids()
    if course_ids:
        courses = Course.query.filter(Course.id.in_(list(course_ids))).all()
        for c in courses:
            if c.nivel:
                niveles.add(c.nivel)
            if c.grado:
                grados.add(c.grado)
    return niveles, grados


def user_allowed_niveles(current_user=None):
    """Niveles visibles para el usuario.
    DOCENTE: derivado de cursos asignados (puede abarcar varios niveles).
    AUXILIAR con nivel asignado ve solo ese nivel; ADMIN ve todos."""
    if not current_user:
        return NIVELES
    if current_user.role == RoleEnum.ADMIN:
        return NIVELES
    if current_user.role == RoleEnum.DOCENTE:
        niveles, _ = _docente_scope_from_courses(current_user)
        if niveles:
            return [n for n in NIVELES if n in niveles]
        return NIVELES
    # AUXILIAR
    if current_user.nivel:
        return [current_user.nivel]
    return NIVELES


def user_allowed_grados(nivel=None, current_user=None):
    """Grados visibles para el usuario según el nivel.
    DOCENTE: derivado de cursos asignados para el nivel dado.
    AUXILIAR con grado asignado ve solo ese grado."""
    if current_user and current_user.role == RoleEnum.DOCENTE:
        _, grados = _docente_scope_from_courses(current_user)
        if grados:
            all_grados = GRADOS_POR_NIVEL.get(nivel or "PRIMARIA", GRADOS_PRIMARIA)
            filtered = [g for g in all_grados if g in grados]
            return filtered if filtered else all_grados
        return GRADOS_POR_NIVEL.get(nivel or "PRIMARIA", GRADOS_PRIMARIA)
    if current_user and current_user.role == RoleEnum.AUXILIAR and current_user.grado:
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
