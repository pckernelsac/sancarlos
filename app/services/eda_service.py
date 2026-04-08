from typing import Optional
from app.database import db
from app.models.academic import EDA, EdaGrade, EdaComment, Grade, Term
from app.models.student import Student
from app.models.academic import Course
from app.services.grade_service import numeric_to_qualitative, _round_half_up


# ── CRUD EDAs ─────────────────────────────────────────────────────────────────

def seed_edas_for_term(term_id: int) -> int:
    """Crea o actualiza las 2 EDAs de un bimestre con numeración global.
    I Bimestre → EDA 1/2, II → EDA 3/4, III → EDA 5/6, IV → EDA 7/8."""
    term = db.session.get(Term, term_id)
    if not term:
        return 0
    base = (term.orden - 1) * 2  # I=0, II=2, III=4, IV=6
    created = 0
    for orden in (1, 2):
        nombre = f"EDA {base + orden}"
        existing = EDA.query.filter_by(term_id=term_id, orden=orden).first()
        if existing:
            if existing.nombre != nombre:
                existing.nombre = nombre
        else:
            db.session.add(EDA(term_id=term_id, nombre=nombre, orden=orden))
            created += 1
    if created:
        db.session.commit()
    return created


# ── Guardado y recálculo ──────────────────────────────────────────────────────

def upsert_eda_grade(student_id: int, course_id: int, eda_id: int,
                     numeric_value: Optional[int]) -> EdaGrade:
    """Guarda la nota de una EDA y recalcula el promedio bimestral automáticamente."""
    if numeric_value is not None and not (0 <= numeric_value <= 20):
        raise ValueError("La nota debe estar entre 0 y 20.")

    # Upsert EdaGrade
    eg = EdaGrade.query.filter_by(
        student_id=student_id, course_id=course_id, eda_id=eda_id
    ).first()
    if eg:
        eg.numeric_value = numeric_value
    else:
        eg = EdaGrade(student_id=student_id, course_id=course_id,
                      eda_id=eda_id, numeric_value=numeric_value)
        db.session.add(eg)

    db.session.flush()  # asegura que el EdaGrade esté en sesión antes de recalcular

    # Recalcula el Grade bimestral (promedio de todas las EDAs del bimestre)
    eda = db.session.get(EDA, eda_id)
    _recalculate_bimester_grade(student_id, course_id, eda.term_id)

    db.session.commit()
    return eg


def _recalculate_bimester_grade(student_id: int, course_id: int, term_id: int):
    """Promedio de todas las EDAs del bimestre → actualiza Grade bimestral."""
    edas = EDA.query.filter_by(term_id=term_id).order_by(EDA.orden).all()
    values = []
    for eda in edas:
        eg = EdaGrade.query.filter_by(
            student_id=student_id, course_id=course_id, eda_id=eda.id
        ).first()
        if eg and eg.numeric_value is not None:
            values.append(eg.numeric_value)

    avg = _round_half_up(sum(values) / len(values)) if values else None

    grade = Grade.query.filter_by(
        student_id=student_id, course_id=course_id, term_id=term_id
    ).first()
    if grade:
        grade.numeric_value = avg
    elif avg is not None:
        db.session.add(Grade(student_id=student_id, course_id=course_id,
                             term_id=term_id, numeric_value=avg))


# ── Comentarios ───────────────────────────────────────────────────────────────

def upsert_eda_comment(student_id: int, eda_id: int, comentario: str) -> EdaComment:
    """Guarda o actualiza el comentario del docente para un estudiante en una EDA."""
    comentario = comentario.strip()[:1000]   # máximo 1000 caracteres
    record = EdaComment.query.filter_by(student_id=student_id, eda_id=eda_id).first()
    if record:
        record.comentario = comentario or None
    else:
        record = EdaComment(student_id=student_id, eda_id=eda_id,
                            comentario=comentario or None)
        db.session.add(record)
    db.session.commit()
    return record


# ── Carga de datos para la vista ──────────────────────────────────────────────

def get_eda_matrix_data(grado: str, seccion: str, term_id: int,
                        nivel: str = "PRIMARIA",
                        allowed_course_ids: set | None = None) -> dict:
    """
    Retorna todo lo necesario para renderizar la vista EDA:
    {
      students, courses, edas,
      eda_maps:   { eda_id: { (student_id, course_id): numeric_value } },
      bim_map:    { (student_id, course_id): numeric_value },  ← promedio bimestral
      avg_per_student: { eda_id: { student_id: {"num": int, "cual": str} } }
    }
    """
    term = db.session.get(Term, term_id)
    if not term:
        return {}

    students = Student.query.filter_by(
        nivel=nivel, grado=grado, seccion=seccion, estado="ACTIVO"
    ).order_by(Student.apellido_paterno, Student.apellido_materno, Student.nombres).all()

    all_courses = Course.query.filter(
        Course.nivel == nivel,
        (Course.grado == grado) | (Course.grado.is_(None))
    ).order_by(Course.area, Course.nombre).all()
    courses = [
        c for c in all_courses
        if allowed_course_ids is None or c.id in allowed_course_ids
    ]

    edas = EDA.query.filter_by(term_id=term_id).order_by(EDA.orden).all()

    if not students or not courses or not edas:
        return {
            "students": students, "courses": courses, "edas": edas,
            "eda_maps": {}, "bim_map": {}, "avg_per_student": {}, "term": term,
        }

    st_ids = [s.id for s in students]
    co_ids = [c.id for c in courses]
    eda_ids = [e.id for e in edas]

    # Notas por EDA
    all_eda_grades = EdaGrade.query.filter(
        EdaGrade.student_id.in_(st_ids),
        EdaGrade.course_id.in_(co_ids),
        EdaGrade.eda_id.in_(eda_ids),
    ).all()

    eda_maps: dict[int, dict] = {e.id: {} for e in edas}
    for eg in all_eda_grades:
        eda_maps[eg.eda_id][(eg.student_id, eg.course_id)] = eg.numeric_value

    # Promedio bimestral (Grade existente)
    bim_grades = Grade.query.filter(
        Grade.student_id.in_(st_ids),
        Grade.course_id.in_(co_ids),
        Grade.term_id == term_id,
    ).all()
    bim_map = {(g.student_id, g.course_id): g.numeric_value for g in bim_grades}

    # Promedio por estudiante por EDA (fila "total" de la tabla)
    avg_per_student: dict[int, dict] = {}
    for eda in edas:
        avg_per_student[eda.id] = {}
        for s in students:
            vals = [
                eda_maps[eda.id][(s.id, c.id)]
                for c in courses
                if (s.id, c.id) in eda_maps[eda.id]
                and eda_maps[eda.id][(s.id, c.id)] is not None
            ]
            if vals:
                n = round(sum(vals) / len(vals))
                avg_per_student[eda.id][s.id] = {"num": n, "cual": numeric_to_qualitative(n, nivel)}
            else:
                avg_per_student[eda.id][s.id] = None

    # Promedio bimestral por estudiante
    bim_avg: dict[int, dict | None] = {}
    for s in students:
        vals = [
            bim_map[(s.id, c.id)]
            for c in courses
            if (s.id, c.id) in bim_map and bim_map[(s.id, c.id)] is not None
        ]
        if vals:
            n = round(sum(vals) / len(vals))
            bim_avg[s.id] = {"num": n, "cual": numeric_to_qualitative(n, nivel)}
        else:
            bim_avg[s.id] = None

    # Comentarios por estudiante por EDA  →  { eda_id: { student_id: texto } }
    all_comments = EdaComment.query.filter(
        EdaComment.student_id.in_(st_ids),
        EdaComment.eda_id.in_(eda_ids),
    ).all()
    comment_map: dict[int, dict[int, str]] = {e.id: {} for e in edas}
    for c in all_comments:
        comment_map[c.eda_id][c.student_id] = c.comentario or ""

    # Orden de mérito: estudiantes con promedio ordenados desc (dense ranking)
    with_avg    = sorted([s for s in students if bim_avg.get(s.id)],
                         key=lambda s: bim_avg[s.id]["num"], reverse=True)
    without_avg = [s for s in students if not bim_avg.get(s.id)]
    merit_order = []
    rank = 1
    prev_num = None
    for i, s in enumerate(with_avg):
        num = bim_avg[s.id]["num"]
        if prev_num is not None and num != prev_num:
            rank += 1
        merit_order.append({"student": s, "rank": rank, "avg": bim_avg[s.id]})
        prev_num = num
    for s in without_avg:
        merit_order.append({"student": s, "rank": None, "avg": None})

    return {
        "students": students, "courses": courses, "edas": edas, "term": term,
        "eda_maps": eda_maps, "bim_map": bim_map,
        "avg_per_student": avg_per_student, "bim_avg": bim_avg,
        "comment_map": comment_map, "merit_order": merit_order,
    }
