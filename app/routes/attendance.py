from pydantic import ValidationError
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.auth.dependencies import require_role
from app.database import db
from app.models.student import Student, SECCIONES
from app.schemas.json_payloads import AttendanceSavePayload
from app.security.permissions import assert_can_view_student
from app.utils.safe_errors import log_unexpected_exc, GENERIC_USER_MESSAGE
from app.services.attendance_service import upsert_attendance, get_class_attendance_month
from app.models.academic import MESES
from app.models.user import User
from app.utils.scope import sanitize_nivel_grado_convivencia, convivencia_allowed_niveles, convivencia_allowed_grados
from app import render
import datetime

router = APIRouter(tags=["attendance"])


@router.get("/", name="attendance.index")
async def index(request: Request, current_user: User = Depends(require_role("ADMIN", "AUXILIAR", "DOCENTE", niveles=("INICIAL", "PRIMARIA")))):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel, grado = sanitize_nivel_grado_convivencia(
        request.query_params.get("nivel", "PRIMARIA"),
        request.query_params.get("grado", ""),
        current_user,
    )
    seccion = request.query_params.get("seccion", "")
    mes = request.query_params.get("mes", datetime.date.today().strftime("%B"))

    rows = []
    if grado and seccion and mes:
        rows = get_class_attendance_month(grado, seccion, mes, anio, nivel=nivel)

    return render(
        request, "attendance/index.html",
        niveles=convivencia_allowed_niveles(current_user), nivel=nivel,
        grados=convivencia_allowed_grados(nivel, current_user), secciones=SECCIONES, meses=MESES,
        grado=grado, seccion=seccion, mes=mes,
        anio=anio, rows=rows,
    )


@router.post("/save", name="attendance.save")
async def save(request: Request, current_user: User = Depends(require_role("ADMIN", "AUXILIAR", "DOCENTE", niveles=("INICIAL", "PRIMARIA")))):
    try:
        data = AttendanceSavePayload.model_validate(await request.json())
    except ValidationError:
        return JSONResponse({"ok": False, "error": "Datos inválidos."}, status_code=400)

    student = db.session.get(Student, data.student_id)
    if not student:
        return JSONResponse({"ok": False, "error": "Estudiante no encontrado."}, status_code=404)
    try:
        assert_can_view_student(current_user, student)
    except HTTPException as e:
        return JSONResponse({"ok": False, "error": e.detail}, status_code=e.status_code)

    try:
        record = upsert_attendance(
            student_id=data.student_id,
            mes=data.mes,
            anio=data.anio,
            faltas=data.faltas,
            tardanzas=data.tardanzas,
        )
        return JSONResponse({"ok": True, "faltas": record.faltas, "tardanzas": record.tardanzas})
    except Exception as exc:
        log_unexpected_exc(exc, "attendance.save")
        return JSONResponse({"ok": False, "error": GENERIC_USER_MESSAGE}, status_code=400)
