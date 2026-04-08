from app.database import db
from app.models.academic import (
    Behavior, Term, EDA, INDICADORES_CONDUCTA, INDICADORES_CONDUCTA_SECUNDARIA
)
from app.services.grade_service import _round_half_up, numeric_to_qualitative

_ALL_INDICADORES = set(INDICADORES_CONDUCTA) | set(INDICADORES_CONDUCTA_SECUNDARIA)


def upsert_behavior(student_id: int, indicador: str, eda_id: int, calificacion) -> Behavior:
    if indicador not in _ALL_INDICADORES:
        raise ValueError(f"Indicador no válido: {indicador}")

    if calificacion in (None, "", "--"):
        cal = None
    else:
        try:
            cal = int(calificacion)
        except (ValueError, TypeError):
            raise ValueError("Calificación de conducta no válida.")
        if cal < 0 or cal > 20:
            raise ValueError("La calificación debe estar entre 0 y 20.")

    record = Behavior.query.filter_by(
        student_id=student_id, indicador=indicador, eda_id=eda_id
    ).first()
    if record:
        record.calificacion = cal
    else:
        record = Behavior(
            student_id=student_id, indicador=indicador,
            eda_id=eda_id, calificacion=cal,
        )
        db.session.add(record)
    db.session.commit()
    return record


def get_student_behavior_by_eda(student_id: int, eda_id: int) -> dict:
    """Retorna {indicador: Behavior} para una EDA específica."""
    records = Behavior.query.filter_by(
        student_id=student_id, eda_id=eda_id
    ).all()
    return {r.indicador: r for r in records}


def get_student_behavior_all_terms(student_id: int, anio: int) -> dict:
    """Retorna {term_id: {indicador: promedio_de_2_edas}} para el PDF.

    Calcula el promedio de las 2 EDAs de cada bimestre por indicador.
    Returns: {term_id: {indicador: Behavior-like}} donde cada entry tiene calificacion promediada.
    """
    term_ids = [t.id for t in Term.query.filter_by(anio=anio).all()]
    if not term_ids:
        return {}

    edas = EDA.query.filter(EDA.term_id.in_(term_ids)).all()
    eda_ids = [e.id for e in edas]
    if not eda_ids:
        return {}

    # Mapear eda_id → term_id
    eda_term = {e.id: e.term_id for e in edas}
    # Agrupar edas por term
    term_edas: dict[int, list[int]] = {}
    for e in edas:
        term_edas.setdefault(e.term_id, []).append(e.id)

    records = Behavior.query.filter(
        Behavior.student_id == student_id,
        Behavior.eda_id.in_(eda_ids),
    ).all()

    # Agrupar: term_id → indicador → [calificaciones]
    term_ind_vals: dict[int, dict[str, list]] = {}
    for r in records:
        tid = eda_term[r.eda_id]
        if r.calificacion is not None:
            term_ind_vals.setdefault(tid, {}).setdefault(r.indicador, []).append(r.calificacion)

    # Crear resultado con promedios por bimestre
    class _BehProxy:
        """Proxy ligero que imita Behavior para el PDF."""
        def __init__(self, cal):
            self.calificacion = cal
        @property
        def qualitative_grade(self):
            v = self.calificacion
            if v is None:
                return None
            if v >= 18: return "AD"
            if v >= 15: return "A"
            if v >= 11: return "B"
            return "C"

    result: dict[int, dict] = {}
    for tid in term_ids:
        result[tid] = {}
        ind_vals = term_ind_vals.get(tid, {})
        for ind, vals in ind_vals.items():
            avg = _round_half_up(sum(vals) / len(vals))
            result[tid][ind] = _BehProxy(avg)

    return result


def get_student_behavior(student_id: int, anio: int) -> dict:
    """Compatibilidad: retorna {indicador: Behavior} con datos mergeados."""
    all_terms = get_student_behavior_all_terms(student_id, anio)
    merged = {}
    for term_data in all_terms.values():
        for ind, beh in term_data.items():
            if ind not in merged or (beh.calificacion is not None and merged[ind].calificacion is None):
                merged[ind] = beh
    return merged


def get_behavior_average(student_id: int, anio: int, nivel: str = "PRIMARIA") -> dict:
    """Promedio de TODAS las calificaciones de conducta (todas las EDAs del año).

    Returns: dict con 'promedio_num' (int|None), 'promedio_cual' (str)
    """
    term_ids = [t.id for t in Term.query.filter_by(anio=anio).all()]
    if not term_ids:
        return {"promedio_num": None, "promedio_cual": "--"}

    eda_ids = [e.id for e in EDA.query.filter(EDA.term_id.in_(term_ids)).all()]
    if not eda_ids:
        return {"promedio_num": None, "promedio_cual": "--"}

    records = Behavior.query.filter(
        Behavior.student_id == student_id,
        Behavior.eda_id.in_(eda_ids),
    ).all()
    vals = [r.calificacion for r in records if r.calificacion is not None]
    if not vals:
        return {"promedio_num": None, "promedio_cual": "--"}
    avg = _round_half_up(sum(vals) / len(vals))
    return {
        "promedio_num": avg,
        "promedio_cual": numeric_to_qualitative(avg, nivel),
    }


def get_behavior_indicator_averages(student_id: int, anio: int, indicadores: list, nivel: str = "PRIMARIA") -> dict:
    """Promedio por indicador (promedio de todas las EDAs del año de ese indicador).

    Returns: {indicador: {'promedio_num': int|None, 'promedio_cual': str}}
    """
    term_ids = [t.id for t in Term.query.filter_by(anio=anio).all()]
    if not term_ids:
        return {ind: {"promedio_num": None, "promedio_cual": "--"} for ind in indicadores}

    eda_ids = [e.id for e in EDA.query.filter(EDA.term_id.in_(term_ids)).all()]
    if not eda_ids:
        return {ind: {"promedio_num": None, "promedio_cual": "--"} for ind in indicadores}

    records = Behavior.query.filter(
        Behavior.student_id == student_id,
        Behavior.eda_id.in_(eda_ids),
    ).all()

    # Agrupar por indicador
    ind_vals: dict[str, list] = {}
    for r in records:
        if r.calificacion is not None:
            ind_vals.setdefault(r.indicador, []).append(r.calificacion)

    result = {}
    for ind in indicadores:
        vals = ind_vals.get(ind, [])
        if vals:
            avg = _round_half_up(sum(vals) / len(vals))
            result[ind] = {
                "promedio_num": avg,
                "promedio_cual": numeric_to_qualitative(avg, nivel),
            }
        else:
            result[ind] = {"promedio_num": None, "promedio_cual": "--"}
    return result
