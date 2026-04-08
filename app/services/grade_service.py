from typing import Optional
from app.database import db
from app.models.academic import Grade, Course, Term
from app.models.student import Student


def numeric_to_qualitative(value: Optional[int], nivel: str = "PRIMARIA") -> str:
    """Convierte nota numérica a cualitativa según la escala del nivel.

    INICIAL:    C (0-10), B (11-13), A (14-20)
    PRIMARIA:   C (0-10), B (11-13), A (14-17), AD (18-20)
    SECUNDARIA: C (0-10), B (11-13), A (14-17), AD (18-20)
    """
    if value is None:
        return "--"
    if nivel == "INICIAL":
        if value >= 14:
            return "A"
        if value >= 11:
            return "B"
        return "C"
    else:
        # PRIMARIA y SECUNDARIA comparten escala
        if value >= 18:
            return "AD"
        if value >= 14:
            return "A"
        if value >= 11:
            return "B"
        return "C"


def _round_half_up(x: float) -> int:
    """Redondeo .5 hacia arriba (evita el redondeo bancario de Python)."""
    return int(x + 0.5)


def upsert_grade(student_id: int, course_id: int, term_id: int, numeric_value: Optional[int]) -> Grade:
    """Crea o actualiza una nota. Valida rango 0-20."""
    if numeric_value is not None and not (0 <= numeric_value <= 20):
        raise ValueError("La nota debe estar entre 0 y 20.")

    grade = Grade.query.filter_by(
        student_id=student_id,
        course_id=course_id,
        term_id=term_id
    ).first()

    if grade:
        grade.numeric_value = numeric_value
    else:
        grade = Grade(
            student_id=student_id,
            course_id=course_id,
            term_id=term_id,
            numeric_value=numeric_value
        )
        db.session.add(grade)

    db.session.commit()
    return grade


def get_student_grades_matrix(student_id: int, anio: int) -> dict:
    """
    Retorna estructura:
    {
      course_id: {
        "course": Course,
        "terms": {term_id: Grade | None},
        "promedio_num": float | None,
        "promedio_cual": str
      }
    }
    """
    terms = Term.query.filter_by(anio=anio).order_by(Term.orden).all()
    student = db.session.get(Student, student_id)
    # Cursos aplicables al nivel y grado del estudiante
    courses = Course.query.filter(
        Course.nivel == student.nivel,
        (Course.grado == student.grado) | (Course.grado.is_(None))
    ).order_by(Course.area, Course.nombre).all()

    grades_q = Grade.query.filter_by(student_id=student_id).join(Term).filter(Term.anio == anio).all()
    grade_map = {(g.course_id, g.term_id): g for g in grades_q}

    matrix = {}
    for course in courses:
        term_grades = {t.id: grade_map.get((course.id, t.id)) for t in terms}
        values = [g.numeric_value for g in term_grades.values() if g and g.numeric_value is not None]
        promedio = _round_half_up(sum(values) / len(values)) if values else None
        matrix[course.id] = {
            "course": course,
            "terms": term_grades,
            "promedio_num": promedio,
            "promedio_cual": numeric_to_qualitative(promedio, student.nivel),
        }
    return matrix, terms


def get_area_averages(student_id: int, anio: int) -> dict:
    """Promedio final por área académica."""
    student = db.session.get(Student, student_id)
    nivel = student.nivel if student else "PRIMARIA"
    matrix, _ = get_student_grades_matrix(student_id, anio)
    area_totals: dict[str, list] = {}
    for data in matrix.values():
        area = data["course"].area
        if data["promedio_num"] is not None:
            area_totals.setdefault(area, []).append(data["promedio_num"])

    return {
        area: {
            "promedio_num": _round_half_up(sum(vals) / len(vals)),
            "promedio_cual": numeric_to_qualitative(_round_half_up(sum(vals) / len(vals)), nivel),
        }
        for area, vals in area_totals.items()
    }
