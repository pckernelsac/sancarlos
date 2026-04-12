"""Carga y resolución de nombres para firmas de boletas (PDF/HTML)."""
from __future__ import annotations

from app.database import db
from app.models.boleta_staff import BoletaStaffConfig
from app.models.student import GRADOS_INICIAL, GRADOS_PRIMARIA, GRADOS_SECUNDARIA

# Valor por defecto si no hay nombre guardado en BD (misma línea que antes en boletas).
DEFAULT_DIRECTOR_GENERAL = "Lic. Glicerio Palacios Contreras"


def all_boleta_staff_keys() -> list[str]:
    keys = ["coord_primaria", "coord_secundaria", "director_general"]
    keys += [f"tutor_inicial_{g}" for g in GRADOS_INICIAL]
    keys += [f"tutor_primaria_{g}" for g in GRADOS_PRIMARIA]
    keys += [f"tutor_secundaria_{g}" for g in GRADOS_SECUNDARIA]
    return keys


def get_staff_map() -> dict[str, str]:
    rows = BoletaStaffConfig.query.all()
    return {r.clave: (r.nombre_completo or "").strip() for r in rows}


def upsert_staff_map(data: dict[str, str]) -> None:
    """Persiste clave → nombre (cadena vacía borra el valor en BD)."""
    for clave in all_boleta_staff_keys():
        val = (data.get(clave) or "").strip()
        row = BoletaStaffConfig.query.filter_by(clave=clave).first()
        if row:
            row.nombre_completo = val if val else None
        elif val:
            db.session.add(BoletaStaffConfig(clave=clave, nombre_completo=val))
    db.session.commit()


def firma_boleta_for_student(student, staff_map: dict[str, str]) -> dict[str, str]:
    """Coordinador, director general y tutor de aula para PDF/HTML de boleta."""
    nivel = student.nivel
    coord_key = "coord_secundaria" if nivel == "SECUNDARIA" else "coord_primaria"
    coord = staff_map.get(coord_key, "").strip()

    tutor_key = ""
    if nivel == "INICIAL":
        tutor_key = f"tutor_inicial_{student.grado}"
    elif nivel == "PRIMARIA":
        tutor_key = f"tutor_primaria_{student.grado}"
    elif nivel == "SECUNDARIA":
        tutor_key = f"tutor_secundaria_{student.grado}"

    tutor = staff_map.get(tutor_key, "").strip() if tutor_key else ""
    dir_custom = (staff_map.get("director_general") or "").strip()
    director = dir_custom if dir_custom else DEFAULT_DIRECTOR_GENERAL
    return {"coordinador": coord, "tutor": tutor, "director": director}


def firma_coord_label_for_nivel(nivel: str | None) -> str:
    if nivel == "SECUNDARIA":
        return "COORDINADOR(A)"
    return "COORDINADORA"
