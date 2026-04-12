"""Flags de funcionalidad configurables por el administrador."""
from __future__ import annotations

from app.database import db
from app.models.app_setting import AppSetting

KEY_EDA_MATRIX_DOCENTE = "eda_matrix_docente_enabled"


def _truthy(raw: str) -> bool:
    return raw.strip().lower() in ("1", "true", "yes", "on")


def is_eda_matrix_enabled_for_docentes() -> bool:
    """Si es False, los docentes no acceden a /grades/eda-matrix (ADMIN sí). Por defecto True."""
    row = AppSetting.query.filter_by(key=KEY_EDA_MATRIX_DOCENTE).first()
    if row is None:
        return True
    return _truthy(row.value)


def set_eda_matrix_enabled_for_docentes(enabled: bool) -> None:
    val = "true" if enabled else "false"
    row = AppSetting.query.filter_by(key=KEY_EDA_MATRIX_DOCENTE).first()
    if row:
        row.value = val
    else:
        db.session.add(AppSetting(key=KEY_EDA_MATRIX_DOCENTE, value=val))
    db.session.commit()
