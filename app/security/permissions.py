"""
Autorización centralizada sobre estudiantes.
"""
from __future__ import annotations

from fastapi import HTTPException

from app.models.academic import Course
from app.models.user import RoleEnum, User
from app.utils.scope import user_allowed_grados, user_allowed_niveles


def _docente_niveles_grados(user: User) -> tuple[list[str], list[str]]:
    """Replica el alcance académico usado en listados de docentes.
    Considera las restricciones de grado en TeacherCourse.grados."""
    from app.utils.scope import _docente_scope_from_courses
    niveles, grados = _docente_scope_from_courses(user)
    return list(niveles), list(grados)


def can_view_student(user: User, student) -> bool:
    """¿Puede el usuario ver datos académicos identificativos del estudiante?"""
    if not getattr(user, "is_authenticated", False) or user.role is None:
        return False
    if user.role == RoleEnum.ADMIN:
        return True
    if user.role == RoleEnum.AUXILIAR:
        if student.nivel not in user_allowed_niveles(user):
            return False
        allowed_g = user_allowed_grados(student.nivel, user)
        return student.grado in allowed_g
    if user.role == RoleEnum.DOCENTE:
        niveles, grados = _docente_niveles_grados(user)
        if not niveles:
            return False
        if student.nivel not in niveles:
            return False
        if grados and student.grado not in grados:
            return False
        return True
    return False


def can_edit_student(user: User, student) -> bool:
    """Crear/editar/eliminar ficha de estudiante (ADMIN / AUXILIAR en alcance)."""
    if not getattr(user, "is_authenticated", False) or user.role is None:
        return False
    if user.role == RoleEnum.ADMIN:
        return True
    if user.role == RoleEnum.AUXILIAR:
        return can_view_student(user, student)
    return False


def can_grade_student(user: User, student, course_id: int | None = None) -> bool:
    """
    Calificar o registrar evaluaciones para el estudiante.
    ADMIN siempre; DOCENTE con curso asignado coherente con nivel/grado del alumno.
    Respeta TeacherCourse.grados (restricción de grados por docente).
    """
    if not getattr(user, "is_authenticated", False) or user.role is None:
        return False
    if user.role == RoleEnum.ADMIN:
        return True
    if user.role != RoleEnum.DOCENTE:
        return False
    if course_id is not None:
        if not user.can_grade_course(course_id):
            return False
        from app.database import db

        course = db.session.get(Course, course_id)
        if not course or course.nivel != student.nivel:
            return False
        if course.grado is not None and course.grado != student.grado:
            return False
        # Verificar restricción de grados en TeacherCourse
        allowed_grados = user.allowed_grados_for_course(course_id)
        if allowed_grados is not None and student.grado not in allowed_grados:
            return False
    return can_view_student(user, student)


def assert_can_view_student(user: User, student) -> None:
    if not can_view_student(user, student):
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para acceder a los datos de este estudiante.",
        )


def assert_can_grade_student(user: User, student, course_id: int) -> None:
    if not can_grade_student(user, student, course_id):
        raise HTTPException(
            status_code=403,
            detail="No tienes permiso para calificar a este estudiante en este curso.",
        )
