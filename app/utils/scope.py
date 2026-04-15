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
    y las restricciones de grado en TeacherCourse.
    Retorna (set_niveles, set_grados)."""
    from app.models.academic import Course
    niveles: set[str] = set()
    grados: set[str] = set()
    has_all_grados_for_nivel: set[str] = set()  # niveles donde cubre todos los grados

    tc_map = user.teacher_course_map()  # {course_id: set_grados | None}
    if tc_map:
        course_ids = list(tc_map.keys())
        courses = Course.query.filter(Course.id.in_(course_ids)).all()
        for c in courses:
            if c.nivel:
                niveles.add(c.nivel)
            tc_grados = tc_map.get(c.id)  # restricción del docente
            if tc_grados is not None:
                # Docente tiene grados específicos para este curso
                grados.update(tc_grados)
            elif c.grado:
                # Curso tiene grado fijo
                grados.add(c.grado)
            else:
                # Curso sin grado fijo + sin restricción de docente → todos los grados del nivel
                has_all_grados_for_nivel.add(c.nivel)

    # Si tiene un nivel donde cubre todos los grados, añadirlos
    for niv in has_all_grados_for_nivel:
        grados.update(GRADOS_POR_NIVEL.get(niv, []))

    return niveles, grados


def _docente_allowed_grados_for_nivel(user, nivel):
    """Grados que el docente puede ver para un nivel específico,
    derivados de sus cursos asignados y restricciones TeacherCourse.grados."""
    from app.models.academic import Course
    grados: set[str] = set()
    tc_map = user.teacher_course_map()
    if not tc_map:
        return GRADOS_POR_NIVEL.get(nivel or "PRIMARIA", GRADOS_PRIMARIA)

    course_ids = list(tc_map.keys())
    courses = Course.query.filter(
        Course.id.in_(course_ids), Course.nivel == nivel
    ).all()

    for c in courses:
        tc_grados = tc_map.get(c.id)
        if tc_grados is not None:
            grados.update(tc_grados)
        elif c.grado:
            grados.add(c.grado)
        else:
            # Curso sin grado + sin restricción → todos los grados
            return GRADOS_POR_NIVEL.get(nivel, GRADOS_PRIMARIA)

    if grados:
        all_grados = GRADOS_POR_NIVEL.get(nivel or "PRIMARIA", GRADOS_PRIMARIA)
        return [g for g in all_grados if g in grados]
    return GRADOS_POR_NIVEL.get(nivel or "PRIMARIA", GRADOS_PRIMARIA)


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
    DOCENTE: derivado de cursos asignados + restricción TeacherCourse.grados.
    AUXILIAR con grado asignado ve solo ese grado."""
    if current_user and current_user.role == RoleEnum.DOCENTE:
        return _docente_allowed_grados_for_nivel(current_user, nivel)
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


# ---------------------------------------------------------------------------
# Convivencia: DOCENTE solo ve su nivel y grado asignado (no los de cursos)
# ---------------------------------------------------------------------------

def convivencia_allowed_niveles(current_user=None):
    """Niveles para convivencia: DOCENTE usa su nivel directo, no el de cursos."""
    if current_user and current_user.role == RoleEnum.DOCENTE:
        return [current_user.nivel] if current_user.nivel else []
    return user_allowed_niveles(current_user)


def convivencia_allowed_grados(nivel=None, current_user=None):
    """Grados para convivencia: DOCENTE usa su grado directo, no el de cursos."""
    if current_user and current_user.role == RoleEnum.DOCENTE:
        if current_user.grado:
            return [current_user.grado]
        return GRADOS_POR_NIVEL.get(nivel or "PRIMARIA", GRADOS_PRIMARIA)
    return user_allowed_grados(nivel, current_user)


def sanitize_nivel_grado_convivencia(nivel_req, grado_req, current_user=None):
    """Valida nivel/grado para convivencia. DOCENTE restringido a su asignación directa."""
    niveles = convivencia_allowed_niveles(current_user)
    if not niveles:
        return nivel_req, ""
    nivel = nivel_req if nivel_req in niveles else niveles[0]

    grados = convivencia_allowed_grados(nivel, current_user)
    grado = grado_req if grado_req in grados else (grados[0] if grados else "")

    return nivel, grado
