from app.database import db
from app.models.academic import (
    Behavior, BehaviorMonthly, Term, EDA,
    INDICADORES_CONDUCTA, INDICADORES_CONDUCTA_SECUNDARIA, MESES,
)
from app.services.grade_service import _round_half_up, numeric_to_qualitative

_ALL_INDICADORES = set(INDICADORES_CONDUCTA) | set(INDICADORES_CONDUCTA_SECUNDARIA)


# ── Monthly behavior (new) ───────────────────────────────────────────────────

def upsert_behavior_monthly(student_id: int, indicador: str, mes: str, anio: int, calificacion) -> BehaviorMonthly:
    if indicador not in _ALL_INDICADORES:
        raise ValueError(f"Indicador no válido: {indicador}")
    if mes not in MESES:
        raise ValueError(f"Mes no válido: {mes}")

    if calificacion in (None, "", "--"):
        cal = None
    else:
        try:
            cal = int(calificacion)
        except (ValueError, TypeError):
            raise ValueError("Calificación de conducta no válida.")
        if cal < 0 or cal > 20:
            raise ValueError("La calificación debe estar entre 0 y 20.")

    record = BehaviorMonthly.query.filter_by(
        student_id=student_id, indicador=indicador, mes=mes, anio=anio
    ).first()
    if record:
        record.calificacion = cal
    else:
        record = BehaviorMonthly(
            student_id=student_id, indicador=indicador,
            mes=mes, anio=anio, calificacion=cal,
        )
        db.session.add(record)
    db.session.commit()
    return record


def get_student_behavior_by_month(student_id: int, mes: str, anio: int) -> dict:
    """Retorna {indicador: BehaviorMonthly} para un mes específico."""
    records = BehaviorMonthly.query.filter_by(
        student_id=student_id, mes=mes, anio=anio
    ).all()
    return {r.indicador: r for r in records}


def get_student_behavior_all_months(student_id: int, anio: int) -> dict:
    """Retorna {mes: {indicador: BehaviorMonthly}} para el PDF."""
    records = BehaviorMonthly.query.filter_by(
        student_id=student_id, anio=anio
    ).all()
    result: dict[str, dict] = {}
    for r in records:
        result.setdefault(r.mes, {})[r.indicador] = r
    return result


def get_behavior_monthly_average(student_id: int, anio: int, nivel: str = "PRIMARIA") -> dict:
    """Promedio de TODAS las calificaciones mensuales de conducta del año."""
    records = BehaviorMonthly.query.filter_by(
        student_id=student_id, anio=anio
    ).all()
    vals = [r.calificacion for r in records if r.calificacion is not None]
    if not vals:
        return {"promedio_num": None, "promedio_cual": "--"}
    avg = _round_half_up(sum(vals) / len(vals))
    return {
        "promedio_num": avg,
        "promedio_cual": numeric_to_qualitative(avg, nivel),
    }


def get_behavior_monthly_indicator_averages(student_id: int, anio: int, indicadores: list, nivel: str = "PRIMARIA") -> dict:
    """Promedio por indicador (promedio de todos los meses del año)."""
    records = BehaviorMonthly.query.filter_by(
        student_id=student_id, anio=anio
    ).all()
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


# ── Legacy EDA-based behavior (kept for compatibility) ───────────────────────

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
    """Retorna {term_id: {indicador: promedio_de_2_edas}} para el PDF."""
    term_ids = [t.id for t in Term.query.filter_by(anio=anio).all()]
    if not term_ids:
        return {}

    edas = EDA.query.filter(EDA.term_id.in_(term_ids)).all()
    eda_ids = [e.id for e in edas]
    if not eda_ids:
        return {}

    eda_term = {e.id: e.term_id for e in edas}
    term_edas: dict[int, list[int]] = {}
    for e in edas:
        term_edas.setdefault(e.term_id, []).append(e.id)

    records = Behavior.query.filter(
        Behavior.student_id == student_id,
        Behavior.eda_id.in_(eda_ids),
    ).all()

    term_ind_vals: dict[int, dict[str, list]] = {}
    for r in records:
        tid = eda_term[r.eda_id]
        if r.calificacion is not None:
            term_ind_vals.setdefault(tid, {}).setdefault(r.indicador, []).append(r.calificacion)

    class _BehProxy:
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
    all_terms = get_student_behavior_all_terms(student_id, anio)
    merged = {}
    for term_data in all_terms.values():
        for ind, beh in term_data.items():
            if ind not in merged or (beh.calificacion is not None and merged[ind].calificacion is None):
                merged[ind] = beh
    return merged


def get_behavior_average(student_id: int, anio: int, nivel: str = "PRIMARIA") -> dict:
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
