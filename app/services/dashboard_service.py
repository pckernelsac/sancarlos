from app.database import db
from app.models.student import Student
from app.models.academic import Grade, Term, Course, Attendance, MESES
from app.services.grade_service import numeric_to_qualitative


def _student_ids_for_scope(nivel=None, grado=None):
    """Retorna lista de student_ids activos filtrados por nivel/grado, o None si no hay filtro."""
    if not nivel and not grado:
        return None
    q = db.session.query(Student.id).filter_by(estado="ACTIVO")
    if nivel:
        q = q.filter_by(nivel=nivel)
    if grado:
        q = q.filter_by(grado=grado)
    return [r[0] for r in q.all()]


def get_students_by_nivel(nivel=None, grado=None):
    """Cuenta estudiantes activos agrupados por nivel."""
    q = db.session.query(Student.nivel, db.func.count(Student.id)).filter_by(estado="ACTIVO")
    if nivel:
        q = q.filter_by(nivel=nivel)
    if grado:
        q = q.filter_by(grado=grado)
    rows = q.group_by(Student.nivel).all()
    return {n: count for n, count in rows}


def get_grade_distribution_by_term(anio, nivel=None, grado=None):
    """Distribución AD/A/B/C por bimestre para el año dado."""
    terms = Term.query.filter_by(anio=anio).order_by(Term.orden).all()
    if not terms:
        return {}

    st_ids = _student_ids_for_scope(nivel, grado)

    result = {}
    for term in terms:
        q = (
            Grade.query
            .filter_by(term_id=term.id)
            .join(Course)
            .filter(Grade.numeric_value.isnot(None))
        )
        if st_ids is not None:
            q = q.filter(Grade.student_id.in_(st_ids))
        grades = q.all()
        dist = {"AD": 0, "A": 0, "B": 0, "C": 0}
        for g in grades:
            niv = g.course.nivel if g.course else "PRIMARIA"
            cual = numeric_to_qualitative(g.numeric_value, niv)
            if cual in dist:
                dist[cual] += 1
        result[term.nombre] = dist

    return result


def get_average_by_term(anio, nivel=None, grado=None):
    """Promedio general de notas por bimestre."""
    terms = Term.query.filter_by(anio=anio).order_by(Term.orden).all()
    if not terms:
        return {}

    st_ids = _student_ids_for_scope(nivel, grado)

    result = {}
    for term in terms:
        q = (
            db.session.query(db.func.avg(Grade.numeric_value))
            .filter(Grade.term_id == term.id, Grade.numeric_value.isnot(None))
        )
        if st_ids is not None:
            q = q.filter(Grade.student_id.in_(st_ids))
        avg_val = q.scalar()
        result[term.nombre] = round(float(avg_val), 1) if avg_val else 0

    return result


def get_attendance_by_month(anio, nivel=None, grado=None):
    """Total faltas y tardanzas por mes para el año dado."""
    q = (
        db.session.query(
            Attendance.mes,
            db.func.sum(Attendance.faltas),
            db.func.sum(Attendance.tardanzas),
        )
        .filter_by(anio=anio)
    )
    if nivel or grado:
        q = q.join(Student, Student.id == Attendance.student_id)
        if nivel:
            q = q.filter(Student.nivel == nivel)
        if grado:
            q = q.filter(Student.grado == grado)
    rows = q.group_by(Attendance.mes).all()
    data = {mes: {"faltas": 0, "tardanzas": 0} for mes in MESES}
    for mes, faltas, tardanzas in rows:
        if mes in data:
            data[mes]["faltas"] = int(faltas or 0)
            data[mes]["tardanzas"] = int(tardanzas or 0)
    return data
