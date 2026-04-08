from app.database import db
from app.models.academic import ParentResponsibility, Term, INDICADORES_PPFF
from app.services.grade_service import _round_half_up, numeric_to_qualitative


def upsert_parent_responsibility(student_id: int, indicador: str, term_id: int, calificacion) -> ParentResponsibility:
    if indicador not in INDICADORES_PPFF:
        raise ValueError(f"Indicador no válido: {indicador}")

    if calificacion in (None, "", "--"):
        cal = None
    else:
        try:
            cal = int(calificacion)
        except (ValueError, TypeError):
            raise ValueError("Calificación no válida.")
        if cal < 0 or cal > 20:
            raise ValueError("La calificación debe estar entre 0 y 20.")

    record = ParentResponsibility.query.filter_by(
        student_id=student_id, indicador=indicador, term_id=term_id
    ).first()
    if record:
        record.calificacion = cal
    else:
        record = ParentResponsibility(
            student_id=student_id, indicador=indicador,
            term_id=term_id, calificacion=cal,
        )
        db.session.add(record)
    db.session.commit()
    return record


def get_student_ppff_by_term(student_id: int, term_id: int) -> dict:
    """Retorna {indicador: ParentResponsibility} para un bimestre específico."""
    records = ParentResponsibility.query.filter_by(
        student_id=student_id, term_id=term_id
    ).all()
    return {r.indicador: r for r in records}


def get_student_ppff_all_terms(student_id: int, anio: int) -> dict:
    """Retorna {term_id: {indicador: ParentResponsibility}} para todos los bimestres del año."""
    term_ids = [t.id for t in Term.query.filter_by(anio=anio).all()]
    if not term_ids:
        return {}

    records = ParentResponsibility.query.filter(
        ParentResponsibility.student_id == student_id,
        ParentResponsibility.term_id.in_(term_ids),
    ).all()

    result: dict[int, dict] = {tid: {} for tid in term_ids}
    for r in records:
        result[r.term_id][r.indicador] = r
    return result


def get_ppff_average(student_id: int, anio: int, nivel: str = "PRIMARIA") -> dict:
    """Promedio general de PPFF del año."""
    term_ids = [t.id for t in Term.query.filter_by(anio=anio).all()]
    if not term_ids:
        return {"promedio_num": None, "promedio_cual": "--"}

    records = ParentResponsibility.query.filter(
        ParentResponsibility.student_id == student_id,
        ParentResponsibility.term_id.in_(term_ids),
    ).all()
    vals = [r.calificacion for r in records if r.calificacion is not None]
    if not vals:
        return {"promedio_num": None, "promedio_cual": "--"}
    avg = _round_half_up(sum(vals) / len(vals))
    return {
        "promedio_num": avg,
        "promedio_cual": numeric_to_qualitative(avg, nivel),
    }


def get_ppff_term_average(student_id: int, term_id: int, nivel: str = "PRIMARIA") -> dict:
    """Promedio de PPFF de un bimestre específico."""
    records = ParentResponsibility.query.filter_by(
        student_id=student_id, term_id=term_id
    ).all()
    vals = [r.calificacion for r in records if r.calificacion is not None]
    if not vals:
        return {"promedio_num": None, "promedio_cual": "--"}
    avg = _round_half_up(sum(vals) / len(vals))
    return {
        "promedio_num": avg,
        "promedio_cual": numeric_to_qualitative(avg, nivel),
    }


def get_ppff_indicator_averages(student_id: int, anio: int, nivel: str = "PRIMARIA") -> dict:
    """Promedio por indicador (promedio de todos los bimestres del año)."""
    term_ids = [t.id for t in Term.query.filter_by(anio=anio).all()]
    if not term_ids:
        return {ind: {"promedio_num": None, "promedio_cual": "--"} for ind in INDICADORES_PPFF}

    records = ParentResponsibility.query.filter(
        ParentResponsibility.student_id == student_id,
        ParentResponsibility.term_id.in_(term_ids),
    ).all()

    ind_vals: dict[str, list] = {}
    for r in records:
        if r.calificacion is not None:
            ind_vals.setdefault(r.indicador, []).append(r.calificacion)

    result = {}
    for ind in INDICADORES_PPFF:
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
