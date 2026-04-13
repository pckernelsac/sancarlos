import datetime
import re

from sqlalchemy.exc import IntegrityError

from app.database import db
from app.models.student import Student


def generate_student_code(apellido_paterno: str, apellido_materno: str = "") -> str:
    """
    Genera un código único: inicial ap. paterno + inicial ap. materno + año + correlativo (4 dígitos).
    Ej: GARCIA, LOPEZ → GL20260001
    Si solo hay paterno: GARCIA → G20260001
    """
    p = apellido_paterno.strip().upper()
    m = apellido_materno.strip().upper()
    initials = p[0] if p else ""
    if m:
        initials += m[0]
    if not initials:
        initials = "XX"

    year = datetime.date.today().year
    prefix = f"{initials}{year}"

    # Buscar el máximo correlativo existente con este prefijo
    pattern = f"{prefix}%"
    last = (
        Student.query
        .filter(Student.codigo.like(pattern))
        .order_by(Student.codigo.desc())
        .first()
    )

    if last:
        # Extraer los dígitos después del prefijo
        suffix = last.codigo[len(prefix):]
        try:
            next_num = int(suffix) + 1
        except ValueError:
            next_num = 1
    else:
        next_num = 1

    return f"{prefix}{next_num:04d}"


def get_all_students(nivel=None, grado=None, seccion=None, estado="ACTIVO",
                     allowed_niveles=None, allowed_grados=None,
                     page=1, per_page=20):
    q = Student.query
    if estado:
        q = q.filter_by(estado=estado)
    if nivel:
        q = q.filter_by(nivel=nivel)
    elif allowed_niveles:
        q = q.filter(Student.nivel.in_(allowed_niveles))
    if grado:
        q = q.filter_by(grado=grado)
    elif allowed_grados:
        q = q.filter(Student.grado.in_(allowed_grados))
    if seccion:
        q = q.filter_by(seccion=seccion)
    q = q.order_by(Student.nivel, Student.grado, Student.seccion,
                   Student.apellido_paterno, Student.apellido_materno, Student.nombres)
    total = q.count()
    students = q.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = max(1, (total + per_page - 1) // per_page)
    return {
        "items": students,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


def create_student(data: dict) -> Student:
    """Inserta estudiante; reintenta si hay colisión en código (concurrencia SQLite)."""
    ap_pat = data.get("apellido_paterno", "") or ""
    ap_mat = data.get("apellido_materno", "") or ""
    for _ in range(8):
        try:
            student = Student(**data)
            db.session.add(student)
            db.session.commit()
            return student
        except IntegrityError as e:
            db.session.rollback()
            err = str(getattr(e, "orig", e)).lower()
            if "codigo" not in err and "students.codigo" not in err:
                raise ValueError("No se pudo guardar el estudiante (datos duplicados o inválidos).") from e
            data["codigo"] = generate_student_code(ap_pat, ap_mat)
    raise ValueError("No se pudo generar un código de estudiante único tras varios intentos.")


def update_student(student_id: int, data: dict) -> Student:
    student = db.session.get(Student, student_id)
    if not student:
        raise ValueError("Estudiante no encontrado.")
    for key, value in data.items():
        setattr(student, key, value)
    db.session.commit()
    return student


def delete_student(student_id: int):
    student = db.session.get(Student, student_id)
    if not student:
        raise ValueError("Estudiante no encontrado.")
    db.session.delete(student)
    db.session.commit()


def find_duplicates():
    """Encuentra estudiantes duplicados (mismo nombre + nivel + grado).
    Retorna lista de grupos: [{"key": str, "keep": Student, "duplicates": [Student...]}]
    """
    from sqlalchemy import func
    # Buscar combinaciones con más de un registro
    dupes = (
        db.session.query(
            Student.apellido_paterno, Student.apellido_materno,
            Student.nombres, Student.nivel, Student.grado,
            func.count(Student.id).label("cnt"),
        )
        .group_by(
            Student.apellido_paterno, Student.apellido_materno,
            Student.nombres, Student.nivel, Student.grado,
        )
        .having(func.count(Student.id) > 1)
        .all()
    )
    groups = []
    for ap, am, nom, niv, gr, cnt in dupes:
        students = (
            Student.query
            .filter_by(
                apellido_paterno=ap, apellido_materno=am,
                nombres=nom, nivel=niv, grado=gr,
            )
            .order_by(Student.id)
            .all()
        )
        keep = students[0]
        groups.append({
            "key": f"{ap} {am}, {nom} — {niv} {gr}°",
            "keep": keep,
            "duplicates": students[1:],
            "total": len(students),
        })
    return groups


def remove_duplicates():
    """Elimina estudiantes duplicados, conservando el registro más antiguo (menor ID).
    Retorna cantidad de registros eliminados."""
    groups = find_duplicates()
    removed = 0
    for g in groups:
        for dup in g["duplicates"]:
            db.session.delete(dup)
            removed += 1
    db.session.commit()
    return removed


def regenerate_codes(nivel=None):
    """Regenera códigos de todos los estudiantes (o de un nivel).
    Retorna la cantidad de códigos regenerados."""
    q = Student.query.order_by(Student.apellido_paterno, Student.apellido_materno, Student.nombres)
    if nivel:
        q = q.filter_by(nivel=nivel)
    students = q.all()
    if not students:
        return 0

    # Paso 1: asignar códigos temporales para evitar conflictos UNIQUE
    for i, s in enumerate(students):
        s.codigo = f"_REGEN_{i}"
    db.session.flush()

    # Paso 2: generar códigos definitivos en orden
    for s in students:
        s.codigo = generate_student_code(s.apellido_paterno, s.apellido_materno)
        db.session.flush()

    db.session.commit()
    return len(students)


def get_dashboard_stats(nivel=None, grado=None) -> dict:
    q = Student.query.filter_by(estado="ACTIVO")
    if nivel:
        q = q.filter_by(nivel=nivel)
    if grado:
        q = q.filter_by(grado=grado)
    total = q.count()
    by_nivel_grado = (
        db.session.query(Student.nivel, Student.grado, db.func.count(Student.id))
        .filter_by(estado="ACTIVO")
    )
    if nivel:
        by_nivel_grado = by_nivel_grado.filter_by(nivel=nivel)
    if grado:
        by_nivel_grado = by_nivel_grado.filter_by(grado=grado)
    by_nivel_grado = by_nivel_grado.group_by(Student.nivel, Student.grado).all()

    NIVEL_ORDER = {"INICIAL": 0, "PRIMARIA": 1, "SECUNDARIA": 2}
    sorted_rows = sorted(by_nivel_grado, key=lambda r: (NIVEL_ORDER.get(r[0], 9), int(r[1])))

    por_grado = {}
    for niv, gr, count in sorted_rows:
        if niv == "INICIAL":
            label = f"{gr} años de Inicial"
        elif niv == "PRIMARIA":
            label = f"{gr}° de Primaria"
        else:
            label = f"{gr}° de Secundaria"
        por_grado[label] = count

    return {
        "total_activos": total,
        "por_grado": por_grado,
    }
