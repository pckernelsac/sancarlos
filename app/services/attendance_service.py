from app.database import db
from app.models.academic import Attendance


def upsert_attendance(student_id: int, mes: str, anio: int, faltas: int, tardanzas: int) -> Attendance:
    record = Attendance.query.filter_by(student_id=student_id, mes=mes, anio=anio).first()
    if record:
        record.faltas = faltas
        record.tardanzas = tardanzas
    else:
        record = Attendance(
            student_id=student_id, mes=mes, anio=anio,
            faltas=faltas, tardanzas=tardanzas
        )
        db.session.add(record)
    db.session.commit()
    return record


def get_student_attendance(student_id: int, anio: int) -> list[Attendance]:
    return Attendance.query.filter_by(student_id=student_id, anio=anio).all()


def get_class_attendance_month(grado: str, seccion: str, mes: str, anio: int) -> list:
    """Lista de (Student, Attendance | None) para un aula y mes."""
    from app.models.student import Student
    students = Student.query.filter_by(grado=grado, seccion=seccion, estado="ACTIVO").order_by(Student.apellido_paterno, Student.apellido_materno, Student.nombres).all()
    result = []
    for s in students:
        att = Attendance.query.filter_by(student_id=s.id, mes=mes, anio=anio).first()
        result.append((s, att))
    return result
