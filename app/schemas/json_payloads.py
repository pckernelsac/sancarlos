"""Modelos Pydantic para cuerpos JSON de operaciones sensibles."""
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


def _clamp_numeric_str(v: Any, max_len: int = 32) -> Any:
    if isinstance(v, str) and len(v) > max_len:
        raise ValueError("Valor demasiado largo.")
    return v


class SaveGradePayload(BaseModel):
    student_id: int = Field(..., ge=1)
    course_id: int = Field(..., ge=1)
    term_id: int = Field(..., ge=1)
    numeric_value: Any = ""

    @field_validator("numeric_value", mode="before")
    @classmethod
    def empty_str_to_blank(cls, v):
        return _clamp_numeric_str(v, 32)


class SaveEdaGradePayload(BaseModel):
    student_id: int = Field(..., ge=1)
    course_id: int = Field(..., ge=1)
    eda_id: int = Field(..., ge=1)
    numeric_value: Any = ""

    @field_validator("numeric_value", mode="before")
    @classmethod
    def clamp_numeric(cls, v):
        return _clamp_numeric_str(v, 32)


class SaveEdaCommentPayload(BaseModel):
    student_id: int = Field(..., ge=1)
    eda_id: int = Field(..., ge=1)
    comentario: str = Field(default="", max_length=4000)

    @field_validator("comentario")
    @classmethod
    def strip_comment(cls, v: str) -> str:
        return (v or "").strip()


class RegistroItemPayload(BaseModel):
    student_id: int = Field(..., ge=1)
    course_id: int = Field(..., ge=1)
    eda_id: int = Field(..., ge=1)
    semana: int = Field(..., ge=1, le=4)
    field: str = Field(..., min_length=1, max_length=64)
    value: Any = ""

    @field_validator("field")
    @classmethod
    def field_safe_chars(cls, v: str) -> str:
        if not re.match(r"^[\w\-]+$", v):
            raise ValueError("Nombre de campo no válido.")
        return v

    @field_validator("value", mode="before")
    @classmethod
    def clamp_value(cls, v):
        return _clamp_numeric_str(v, 32)


class RegistroExamenPayload(BaseModel):
    student_id: int = Field(..., ge=1)
    course_id: int = Field(..., ge=1)
    eda_id: int = Field(..., ge=1)
    value: Any = ""

    @field_validator("value", mode="before")
    @classmethod
    def clamp_value(cls, v):
        return _clamp_numeric_str(v, 32)


class RegistroHeadersPayload(BaseModel):
    course_id: int = Field(..., ge=1)
    headers: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def headers_bounds(self):
        h = self.headers
        if len(h) > 80:
            raise ValueError("Demasiadas claves en encabezados.")
        for k, val in h.items():
            if not isinstance(k, str) or len(k) > 64:
                raise ValueError("Clave de encabezado no válida.")
            s = str(val) if val is not None else ""
            if len(s) > 512:
                raise ValueError("Texto de encabezado demasiado largo.")
        return self


class StudentIndicatorPayload(BaseModel):
    student_id: int = Field(..., ge=1)
    indicador: str = Field(..., min_length=1, max_length=128)
    calificacion: Any = ""

    @field_validator("calificacion", mode="before")
    @classmethod
    def clamp_cal(cls, v):
        return _clamp_numeric_str(v, 32)


class ParentSavePayload(BaseModel):
    student_id: int = Field(..., ge=1)
    term_id: int = Field(..., ge=1)
    indicador: str = Field(..., min_length=1, max_length=128)
    calificacion: Any = ""

    @field_validator("calificacion", mode="before")
    @classmethod
    def clamp_cal(cls, v):
        return _clamp_numeric_str(v, 32)


class BehaviorSavePayload(BaseModel):
    student_id: int = Field(..., ge=1)
    eda_id: int = Field(..., ge=1)
    indicador: str = Field(..., min_length=1, max_length=128)
    calificacion: Any = ""

    @field_validator("calificacion", mode="before")
    @classmethod
    def clamp_cal(cls, v):
        return _clamp_numeric_str(v, 32)


_MES_RE = re.compile(
    r"^(Enero|Febrero|Marzo|Abril|Mayo|Junio|Julio|Agosto|Septiembre|Octubre|Noviembre|Diciembre)$",
    re.IGNORECASE,
)


class AdminCourseSavePayload(BaseModel):
    """POST /admin/courses/save — evita JSON arbitrariamente grande."""

    model_config = {"extra": "ignore"}

    id: int | None = Field(default=None, ge=1)
    nombre: str = Field(..., min_length=1, max_length=200)
    area: str = Field(..., min_length=1, max_length=128)
    nivel: str = Field(default="PRIMARIA", max_length=32)
    grado: str | None = Field(default=None, max_length=32)

    @field_validator("id", mode="before")
    @classmethod
    def id_optional(cls, v):
        if v is None or v == "":
            return None
        return v


class AttendanceSavePayload(BaseModel):
    student_id: int = Field(..., ge=1)
    mes: str = Field(..., min_length=1, max_length=32)
    anio: int = Field(..., ge=2000, le=2100)
    faltas: int = Field(0, ge=0, le=366)
    tardanzas: int = Field(0, ge=0, le=366)

    @field_validator("mes")
    @classmethod
    def mes_valido(cls, v: str) -> str:
        t = (v or "").strip()
        if not _MES_RE.match(t):
            raise ValueError("Mes no válido.")
        return t.title()
