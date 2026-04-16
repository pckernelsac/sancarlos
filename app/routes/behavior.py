from pydantic import ValidationError
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.database import db
from app.auth.dependencies import require_role
from app.schemas.json_payloads import BehaviorMonthlySavePayload
from app.security.permissions import assert_can_view_student
from app.services.behavior_service import (
    upsert_behavior_monthly, get_student_behavior_by_month,
    get_behavior_monthly_average, get_behavior_monthly_indicator_averages,
)
from app.models.student import Student, SECCIONES
from app.models.academic import (
    INDICADORES_CONDUCTA, INDICADORES_CONDUCTA_SECUNDARIA, MESES,
)
from app.models.user import User
from app.utils.scope import sanitize_nivel_grado_convivencia, convivencia_allowed_niveles, convivencia_allowed_grados
from app.utils.safe_errors import log_unexpected_exc, GENERIC_USER_MESSAGE
from app import render
import datetime

router = APIRouter(tags=["behavior"])


@router.get("/", name="behavior.index")
async def index(request: Request, current_user: User = Depends(require_role("ADMIN", "AUXILIAR", "DOCENTE", niveles=("INICIAL", "PRIMARIA")))):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel, grado = sanitize_nivel_grado_convivencia(
        request.query_params.get("nivel", "PRIMARIA"),
        request.query_params.get("grado", ""),
        current_user,
    )
    seccion = request.query_params.get("seccion", "")
    mes = request.query_params.get("mes", "")

    indicadores = (INDICADORES_CONDUCTA_SECUNDARIA
                   if nivel == "SECUNDARIA" else INDICADORES_CONDUCTA)

    students_data = []
    if grado and seccion and mes:
        students = Student.query.filter_by(
            nivel=nivel, grado=grado, seccion=seccion, estado="ACTIVO"
        ).order_by(Student.apellido_paterno, Student.apellido_materno, Student.nombres).all()
        for s in students:
            beh = get_student_behavior_by_month(s.id, mes, anio)
            beh_avg = get_behavior_monthly_average(s.id, anio, nivel)
            ind_avgs = get_behavior_monthly_indicator_averages(s.id, anio, indicadores, nivel)
            students_data.append({
                "student": s, "behavior": beh,
                "promedio": beh_avg, "ind_avgs": ind_avgs,
            })

    return render(
        request, "behavior/index.html",
        niveles=convivencia_allowed_niveles(current_user), nivel=nivel,
        grados=convivencia_allowed_grados(nivel, current_user), secciones=SECCIONES,
        indicadores=indicadores, meses=MESES,
        grado=grado, seccion=seccion, anio=anio,
        mes=mes,
        students_data=students_data,
    )


@router.post("/save", name="behavior.save")
async def save(request: Request, current_user: User = Depends(require_role("ADMIN", "AUXILIAR", "DOCENTE", niveles=("INICIAL", "PRIMARIA")))):
    try:
        data = BehaviorMonthlySavePayload.model_validate(await request.json())
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
        record = upsert_behavior_monthly(
            student_id=data.student_id,
            indicador=data.indicador,
            mes=data.mes,
            anio=data.anio,
            calificacion=data.calificacion,
        )
        return JSONResponse({"ok": True, "calificacion": record.calificacion or "--"})
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as exc:
        log_unexpected_exc(exc, "behavior.save")
        return JSONResponse({"ok": False, "error": GENERIC_USER_MESSAGE}, status_code=400)
