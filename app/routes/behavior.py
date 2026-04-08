from pydantic import ValidationError
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from app.database import db
from app.auth.dependencies import require_role
from app.schemas.json_payloads import BehaviorSavePayload
from app.security.permissions import assert_can_view_student
from app.services.behavior_service import (
    upsert_behavior, get_student_behavior_by_eda, get_behavior_average,
    get_behavior_indicator_averages,
)
from app.models.student import Student, SECCIONES
from app.models.academic import (
    Term, EDA, INDICADORES_CONDUCTA, INDICADORES_CONDUCTA_SECUNDARIA,
)
from app.models.user import User
from app.utils.scope import user_allowed_grados, user_allowed_niveles, sanitize_nivel_grado
from app.utils.safe_errors import log_unexpected_exc, GENERIC_USER_MESSAGE
from app import render
import datetime

router = APIRouter(tags=["behavior"])


@router.get("/", name="behavior.index")
async def index(request: Request, current_user: User = Depends(require_role("ADMIN", "AUXILIAR"))):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel, grado = sanitize_nivel_grado(
        request.query_params.get("nivel", "PRIMARIA"),
        request.query_params.get("grado", ""),
        current_user,
    )
    seccion = request.query_params.get("seccion", "")
    term_id = request.query_params.get("term_id")
    term_id = int(term_id) if term_id else None
    eda_id = request.query_params.get("eda_id")
    eda_id = int(eda_id) if eda_id else None

    indicadores = (INDICADORES_CONDUCTA_SECUNDARIA
                   if nivel == "SECUNDARIA" else INDICADORES_CONDUCTA)

    terms = Term.query.filter_by(anio=anio).order_by(Term.orden).all()
    edas = []

    if term_id:
        edas = EDA.query.filter_by(term_id=term_id).order_by(EDA.orden).all()
        if not eda_id and edas:
            eda_id = edas[0].id

    selected_term = Term.query.get(term_id) if term_id else None
    term_locked = selected_term.locked if selected_term else False

    students_data = []
    if grado and seccion and eda_id:
        students = Student.query.filter_by(
            nivel=nivel, grado=grado, seccion=seccion, estado="ACTIVO"
        ).order_by(Student.apellido_paterno, Student.apellido_materno, Student.nombres).all()
        for s in students:
            beh = get_student_behavior_by_eda(s.id, eda_id)
            beh_avg = get_behavior_average(s.id, anio, nivel)
            ind_avgs = get_behavior_indicator_averages(s.id, anio, indicadores, nivel)
            students_data.append({
                "student": s, "behavior": beh,
                "promedio": beh_avg, "ind_avgs": ind_avgs,
            })

    return render(
        request, "behavior/index.html",
        niveles=user_allowed_niveles(current_user), nivel=nivel,
        grados=user_allowed_grados(nivel, current_user), secciones=SECCIONES,
        indicadores=indicadores,
        grado=grado, seccion=seccion, anio=anio,
        terms=terms, term_id=term_id,
        edas=edas, eda_id=eda_id,
        term_locked=term_locked,
        students_data=students_data,
    )


@router.post("/save", name="behavior.save")
async def save(request: Request, current_user: User = Depends(require_role("ADMIN", "AUXILIAR"))):
    try:
        data = BehaviorSavePayload.model_validate(await request.json())
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
        if not current_user.has_role("ADMIN"):
            eda_obj = db.session.get(EDA, data.eda_id)
            if eda_obj:
                term_obj = db.session.get(Term, eda_obj.term_id)
                if term_obj and term_obj.locked:
                    return JSONResponse({"ok": False, "error": "El bimestre está bloqueado. Contacta al administrador."}, status_code=423)

        record = upsert_behavior(
            student_id=data.student_id,
            indicador=data.indicador,
            eda_id=data.eda_id,
            calificacion=data.calificacion,
        )
        return JSONResponse({"ok": True, "calificacion": record.calificacion or "--"})
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as exc:
        log_unexpected_exc(exc, "behavior.save")
        return JSONResponse({"ok": False, "error": GENERIC_USER_MESSAGE}, status_code=400)
