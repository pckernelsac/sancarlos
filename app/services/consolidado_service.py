"""Servicio para el Consolidado de Notas por aula."""

from app.database import db
from app.models.student import Student
from app.models.academic import Grade, Term, Course
from app.services.grade_service import _round_half_up, numeric_to_qualitative


def get_consolidado(nivel: str, grado: str, seccion: str, anio: int):
    """
    Retorna el consolidado de notas de todos los estudiantes de un aula.

    Returns:
        dict con claves:
        - students: lista de dicts con datos por estudiante
        - terms: lista de Term ordenados
        - has_data: bool
    """
    terms = Term.query.filter_by(anio=anio).order_by(Term.orden).all()
    if not terms:
        return {"students": [], "terms": [], "has_data": False}

    # Estudiantes activos del aula, ordenados alfabéticamente
    query = Student.query.filter_by(
        nivel=nivel, grado=grado, estado="ACTIVO"
    )
    if seccion:
        query = query.filter_by(seccion=seccion)
    students = query.order_by(Student.apellido_paterno, Student.apellido_materno, Student.nombres).all()

    if not students:
        return {"students": [], "terms": terms, "has_data": False}

    st_ids = [s.id for s in students]

    # Cursos del nivel y grado
    course_ids = [c.id for c in Course.query.filter(
        Course.nivel == nivel,
        (Course.grado == grado) | (Course.grado.is_(None))
    ).all()]

    if not course_ids:
        return {"students": [], "terms": terms, "has_data": False}

    term_ids = [t.id for t in terms]

    # Todas las notas del aula en el año
    grades = Grade.query.filter(
        Grade.student_id.in_(st_ids),
        Grade.term_id.in_(term_ids),
        Grade.course_id.in_(course_ids),
    ).all()

    # Agrupar: student_id → term_id → [valores]
    st_term: dict[int, dict[int, list]] = {}
    for g in grades:
        if g.numeric_value is not None:
            st_term.setdefault(g.student_id, {}).setdefault(
                g.term_id, []
            ).append(g.numeric_value)

    # Calcular promedios por bimestre y promedio general
    # Se guardan como float con 2 decimales para mostrar en tabla/gráficos
    result = []
    for student in students:
        term_data = st_term.get(student.id, {})
        bimestre_avgs = {}
        valid_avgs = []

        for term in terms:
            vals = term_data.get(term.id, [])
            if vals:
                avg = round(sum(vals) / len(vals), 2)
                bimestre_avgs[term.id] = avg
                valid_avgs.append(avg)
            else:
                bimestre_avgs[term.id] = None

        promedio = round(sum(valid_avgs) / len(valid_avgs), 2) if valid_avgs else None

        result.append({
            "student": student,
            "bimestres": bimestre_avgs,
            "promedio": promedio,
            "cual": numeric_to_qualitative(_round_half_up(promedio) if promedio is not None else None, nivel),
            "orden": None,  # se calcula después
        })

    # Calcular orden de mérito (dense ranking por promedio descendente)
    # Solo estudiantes con promedio
    with_avg = [(i, r["promedio"]) for i, r in enumerate(result) if r["promedio"] is not None]
    with_avg.sort(key=lambda x: x[1], reverse=True)

    rank, prev_val = 1, None
    for idx, (i, avg) in enumerate(with_avg):
        if prev_val is not None and avg != prev_val:
            rank = idx + 1
        result[i]["orden"] = rank
        prev_val = avg

    return {"students": result, "terms": terms, "has_data": bool(with_avg)}
