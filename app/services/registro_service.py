"""Servicio para el Registro Auxiliar (evaluación semanal por EDA)."""
from typing import Optional
from app.database import db
from app.models.academic import (
    EDA, EdaGrade, RegistroSemana, RegistroExamen, Course, Term,
    RegistroHeaderConfig,
)
from app.models.student import Student
from app.services.eda_service import upsert_eda_grade
from app.services.grade_service import numeric_to_qualitative, _round_half_up

# Campos permitidos por semana
CAMPOS_SEMANA = ["tarea", "intervencion", "fast_test", "aptitudinal"]
CAMPOS_SEMANA_3 = CAMPOS_SEMANA + ["rev_cuaderno", "rev_libro"]
SEMANAS = [1, 2, 3, 4]

# Encabezados por defecto
DEFAULT_HEADERS = {
    "tarea":        "TAREA",
    "intervencion": "INTERVENCIÓN",
    "fast_test":    "FAST TEST",
    "aptitudinal":  "APTITUDINAL",
    "rev_cuaderno": "REV. CUADERNO",
    "rev_libro":    "REV. LIBRO",
}

# Alias para compatibilidad
HEADER_ITEMS = DEFAULT_HEADERS


def get_headers_for_course(course_id: int) -> dict:
    """Retorna los encabezados personalizados para un curso, o los por defecto."""
    rows = RegistroHeaderConfig.query.filter_by(course_id=course_id).all()
    headers = dict(DEFAULT_HEADERS)  # copia
    for r in rows:
        if r.field_name in headers:
            headers[r.field_name] = r.display_name
    return headers


def save_headers_for_course(course_id: int, headers: dict) -> dict:
    """Guarda encabezados personalizados. Solo guarda los que difieren del default."""
    saved = {}
    for field_name, display_name in headers.items():
        if field_name not in DEFAULT_HEADERS:
            continue
        display_name = display_name.strip()
        if not display_name:
            display_name = DEFAULT_HEADERS[field_name]

        existing = RegistroHeaderConfig.query.filter_by(
            course_id=course_id, field_name=field_name
        ).first()

        if display_name == DEFAULT_HEADERS[field_name]:
            # Es el valor default, eliminar si existe
            if existing:
                db.session.delete(existing)
        else:
            if existing:
                existing.display_name = display_name
            else:
                db.session.add(RegistroHeaderConfig(
                    course_id=course_id,
                    field_name=field_name,
                    display_name=display_name,
                ))
        saved[field_name] = display_name

    db.session.commit()
    return saved


# ── Upsert semana ─────────────────────────────────────────────────────────────

def upsert_semana_field(student_id: int, course_id: int, eda_id: int,
                        semana: int, field: str, value: Optional[int]) -> dict:
    """Guarda un campo de la semana y recalcula la nota EDA. Retorna promedios actualizados."""
    if value is not None and not (0 <= value <= 20):
        raise ValueError("La nota debe estar entre 0 y 20.")
    if semana not in SEMANAS:
        raise ValueError("Semana inválida.")
    campos_validos = CAMPOS_SEMANA_3 if semana == 3 else CAMPOS_SEMANA
    if field not in campos_validos:
        raise ValueError(f"Campo '{field}' no válido para semana {semana}.")

    row = RegistroSemana.query.filter_by(
        student_id=student_id, course_id=course_id, eda_id=eda_id, semana=semana
    ).first()
    if row:
        setattr(row, field, value)
    else:
        row = RegistroSemana(
            student_id=student_id, course_id=course_id,
            eda_id=eda_id, semana=semana, **{field: value}
        )
        db.session.add(row)
    db.session.flush()

    return _save_and_return(student_id, course_id, eda_id, row)


# ── Upsert examen bimestral ───────────────────────────────────────────────────

def upsert_examen(student_id: int, course_id: int, eda_id: int,
                  value: Optional[int]) -> dict:
    """Guarda el examen bimestral y recalcula la nota EDA."""
    if value is not None and not (0 <= value <= 20):
        raise ValueError("La nota debe estar entre 0 y 20.")

    row = RegistroExamen.query.filter_by(
        student_id=student_id, course_id=course_id, eda_id=eda_id
    ).first()
    if row:
        row.examen_bimestral = value
    else:
        row = RegistroExamen(
            student_id=student_id, course_id=course_id,
            eda_id=eda_id, examen_bimestral=value
        )
        db.session.add(row)
    db.session.flush()

    return _save_and_return(student_id, course_id, eda_id, None)


# ── Recálculo interno ─────────────────────────────────────────────────────────

def _save_and_return(student_id, course_id, eda_id, semana_row) -> dict:
    """Recalcula la nota EDA y hace commit. Retorna dict con valores actualizados."""
    return _recalculate_eda_from_registro(student_id, course_id, eda_id)


def _recalculate_eda_from_registro(student_id: int, course_id: int, eda_id: int) -> dict:
    """
    Calcula:
      - promedio de cada semana (P1..P4)
      - pre_promedio = avg(P1..P4 no nulos)
      - examen_bimestral
      - prom_cuantitativo = round((pre_promedio + examen) / 2)
    Actualiza EdaGrade con el promedio cuantitativo.
    """
    weekly = {}
    for sem in SEMANAS:
        row = RegistroSemana.query.filter_by(
            student_id=student_id, course_id=course_id, eda_id=eda_id, semana=sem
        ).first()
        weekly[sem] = row.promedio if row else None

    week_vals = [v for v in weekly.values() if v is not None]
    pre_prom = _round_half_up(sum(week_vals) / len(week_vals)) if week_vals else None

    exam_row = RegistroExamen.query.filter_by(
        student_id=student_id, course_id=course_id, eda_id=eda_id
    ).first()
    examen = exam_row.examen_bimestral if exam_row else None

    if pre_prom is not None and examen is not None:
        final = _round_half_up((pre_prom + examen) / 2)
    elif pre_prom is not None:
        final = pre_prom
    elif examen is not None:
        final = examen
    else:
        final = None

    upsert_eda_grade(student_id, course_id, eda_id, final)

    course = db.session.get(Course, course_id)
    nivel = course.nivel if course else "PRIMARIA"

    return {
        "weekly_proms": weekly,
        "pre_prom":     pre_prom,
        "examen":       examen,
        "cuant":        final,
        "cual":         numeric_to_qualitative(final, nivel),
    }


# ── Carga de datos para la vista ──────────────────────────────────────────────

def get_registro_data(eda_id: int, course_id: int) -> dict:
    """
    Devuelve todo lo necesario para renderizar el registro auxiliar:
    {
      eda, course, term, students,
      semana_map:  { (student_id, semana): RegistroSemana },
      examen_map:  { student_id: int|None },
      weekly_prom: { (student_id, semana): int|None },
      pre_prom:    { student_id: int|None },
      cuant_map:   { student_id: int|None },
      cual_map:    { student_id: str },
      summary:     { aprobados, desaprobados, total, promedio_asignatura },
    }
    """
    eda    = db.session.get(EDA, eda_id)
    course = db.session.get(Course, course_id)
    if not eda or not course:
        return {}

    term = db.session.get(Term, eda.term_id)

    # Obtener grado y sección de los estudiantes activos que tengan el grado del curso
    # (o todos si el curso aplica a todos los grados)
    grado_filter = course.grado  # None = todos

    # Necesitamos saber el grado/sección, pero el registro auxiliar se filtra
    # por los parámetros del request (grado/sección), no por el modelo.
    # Devolvemos sin filtrar por grado aquí; el route lo filtra.
    return {
        "eda":    eda,
        "course": course,
        "term":   term,
    }


def get_registro_full(eda_id: int, course_id: int, grado: str, seccion: str) -> dict:
    """
    Carga completa para la vista del registro auxiliar por aula.
    """
    eda    = db.session.get(EDA, eda_id)
    course = db.session.get(Course, course_id)
    if not eda or not course:
        return {}

    term = db.session.get(Term, eda.term_id)

    students = Student.query.filter_by(
        nivel=course.nivel, grado=grado, seccion=seccion, estado="ACTIVO"
    ).order_by(Student.apellido_paterno, Student.apellido_materno, Student.nombres).all()

    if not students:
        return {"eda": eda, "course": course, "term": term,
                "students": [], "semana_map": {}, "examen_map": {},
                "weekly_prom": {}, "pre_prom": {}, "cuant_map": {}, "cual_map": {}}

    st_ids = [s.id for s in students]

    # Cargar todas las filas semanales
    semana_rows = RegistroSemana.query.filter(
        RegistroSemana.student_id.in_(st_ids),
        RegistroSemana.course_id == course_id,
        RegistroSemana.eda_id   == eda_id,
    ).all()
    semana_map = {(r.student_id, r.semana): r for r in semana_rows}

    # Cargar exámenes
    examen_rows = RegistroExamen.query.filter(
        RegistroExamen.student_id.in_(st_ids),
        RegistroExamen.course_id == course_id,
        RegistroExamen.eda_id   == eda_id,
    ).all()
    examen_map = {r.student_id: r.examen_bimestral for r in examen_rows}

    # Cargar notas EDA almacenadas (fuente de verdad canónica)
    eda_grade_rows = EdaGrade.query.filter(
        EdaGrade.student_id.in_(st_ids),
        EdaGrade.course_id == course_id,
        EdaGrade.eda_id    == eda_id,
    ).all()
    eda_grade_map = {r.student_id: r.numeric_value for r in eda_grade_rows}

    # Calcular promedios semanales (para mostrar el desglose)
    weekly_prom: dict = {}
    pre_prom_map: dict = {}
    cuant_map: dict = {}
    cual_map: dict = {}

    for s in students:
        week_vals = []
        for sem in SEMANAS:
            row = semana_map.get((s.id, sem))
            p = row.promedio if row else None
            weekly_prom[(s.id, sem)] = p
            if p is not None:
                week_vals.append(p)

        pp = _round_half_up(sum(week_vals) / len(week_vals)) if week_vals else None
        pre_prom_map[s.id] = pp

        # Usar el EdaGrade almacenado como nota final (sincronizado con EDA matrix)
        final = eda_grade_map.get(s.id)
        cuant_map[s.id] = final
        cual_map[s.id]  = numeric_to_qualitative(final, course.nivel)

    # Resumen
    grades_list = [v for v in cuant_map.values() if v is not None]
    aprobados    = sum(1 for v in grades_list if v >= 11)
    desaprobados = sum(1 for v in grades_list if v < 11)
    prom_asig    = round(sum(grades_list) / len(grades_list), 2) if grades_list else None

    return {
        "eda":          eda,
        "course":       course,
        "term":         term,
        "students":     students,
        "semana_map":   semana_map,
        "examen_map":   examen_map,
        "weekly_prom":  weekly_prom,
        "pre_prom":     pre_prom_map,
        "cuant_map":    cuant_map,
        "cual_map":     cual_map,
        "summary": {
            "aprobados":    aprobados,
            "desaprobados": desaprobados,
            "total":        len(students),
            "prom_asig":    prom_asig,
        },
    }


def escala_academica_text(cuant: Optional[int], nivel: str) -> str:
    """Etiqueta de escala académica (misma lógica que la vista HTML)."""
    if cuant is None:
        return ""
    if nivel == "INICIAL":
        if cuant >= 14:
            return "LOGRO PREVISTO"
        if cuant >= 11:
            return "EN PROCESO"
        return "EN INICIO"
    if cuant >= 18:
        return "LOGRO DESTACADO"
    if cuant >= 14:
        return "LOGRO PROGRESIVO"
    if cuant >= 11:
        return "EN PROCESO"
    return "EN INICIO"
