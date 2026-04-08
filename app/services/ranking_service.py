"""Servicio para calcular el cuadro de mérito (Top N) por bimestre."""

from app.database import db
from app.models.student import Student
from app.models.academic import Grade, Term, Course
from app.services.grade_service import _round_half_up


def get_top_students(nivel: str, grado: str, term_id: int, top_n: int = 10):
    """
    Retorna los top_n estudiantes con mejor promedio en un bimestre.

    Returns:
        list[dict]: [{"rank": int, "student": Student, "promedio": int, "cual": str}, ...]
    """
    from app.services.grade_service import numeric_to_qualitative

    # Estudiantes activos del grado
    students = Student.query.filter_by(
        nivel=nivel, grado=grado, estado="ACTIVO"
    ).order_by(Student.apellido_paterno, Student.apellido_materno, Student.nombres).all()
    if not students:
        return []

    st_ids = [s.id for s in students]
    st_map = {s.id: s for s in students}

    # Cursos del nivel y grado
    course_ids = [c.id for c in Course.query.filter(
        Course.nivel == nivel,
        (Course.grado == grado) | (Course.grado.is_(None))
    ).all()]

    if not course_ids:
        return []

    # Notas del bimestre
    grades = Grade.query.filter(
        Grade.student_id.in_(st_ids),
        Grade.term_id == term_id,
        Grade.course_id.in_(course_ids),
    ).all()

    # Promedio por estudiante
    grade_map: dict[int, list] = {}
    for g in grades:
        if g.numeric_value is not None:
            grade_map.setdefault(g.student_id, []).append(g.numeric_value)

    avgs = {}
    for sid, vals in grade_map.items():
        avgs[sid] = _round_half_up(sum(vals) / len(vals))

    if not avgs:
        return []

    # Ordenar descendente
    sorted_items = sorted(avgs.items(), key=lambda x: x[1], reverse=True)

    # Dense ranking
    result = []
    rank, prev_val = 1, None
    for sid, avg in sorted_items:
        if prev_val is not None and avg != prev_val:
            rank += 1
        if rank > top_n:
            break
        result.append({
            "rank": rank,
            "student": st_map[sid],
            "promedio": avg,
            "cual": numeric_to_qualitative(avg, nivel),
        })
        prev_val = avg

    return result


def get_top_students_annual(nivel: str, grado: str, anio: int, top_n: int = 10):
    """
    Retorna los top_n estudiantes con mejor promedio anual (promedio de bimestres).
    """
    from app.services.grade_service import numeric_to_qualitative

    students = Student.query.filter_by(
        nivel=nivel, grado=grado, estado="ACTIVO"
    ).order_by(Student.apellido_paterno, Student.apellido_materno, Student.nombres).all()
    if not students:
        return []

    st_ids = [s.id for s in students]
    st_map = {s.id: s for s in students}

    course_ids = [c.id for c in Course.query.filter(
        Course.nivel == nivel,
        (Course.grado == grado) | (Course.grado.is_(None))
    ).all()]

    if not course_ids:
        return []

    term_ids = [t.id for t in Term.query.filter_by(anio=anio).all()]
    if not term_ids:
        return []

    grades = Grade.query.filter(
        Grade.student_id.in_(st_ids),
        Grade.term_id.in_(term_ids),
        Grade.course_id.in_(course_ids),
    ).all()

    # Agrupar: student → course → [valores por bimestre]
    st_course: dict[int, dict[int, list]] = {}
    for g in grades:
        if g.numeric_value is not None:
            st_course.setdefault(g.student_id, {}).setdefault(
                g.course_id, []
            ).append(g.numeric_value)

    avgs = {}
    for sid in st_ids:
        course_avgs = [
            _round_half_up(sum(v) / len(v))
            for v in st_course.get(sid, {}).values()
        ]
        if course_avgs:
            avgs[sid] = _round_half_up(sum(course_avgs) / len(course_avgs))

    if not avgs:
        return []

    sorted_items = sorted(avgs.items(), key=lambda x: x[1], reverse=True)

    result = []
    rank, prev_val = 1, None
    for sid, avg in sorted_items:
        if prev_val is not None and avg != prev_val:
            rank += 1
        if rank > top_n:
            break
        result.append({
            "rank": rank,
            "student": st_map[sid],
            "promedio": avg,
            "cual": numeric_to_qualitative(avg, nivel),
        })
        prev_val = avg

    return result
