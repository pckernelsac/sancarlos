from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from app.auth.dependencies import require_login
from app.services.student_service import get_dashboard_stats
from app.services.dashboard_service import (
    get_students_by_nivel,
    get_grade_distribution_by_term,
    get_average_by_term,
    get_attendance_by_month,
)
from app.models.academic import Term
from app.models.user import User, RoleEnum
from app import render, redirect_to
import datetime

router = APIRouter(tags=["main"])


def _dash_scope(current_user):
    if current_user.role == RoleEnum.DOCENTE:
        return current_user.nivel, current_user.grado
    return None, None


@router.get("/", name="main.index")
async def index():
    return redirect_to("/dashboard")


@router.get("/dashboard", name="main.dashboard")
async def dashboard(request: Request, current_user: User = Depends(require_login)):
    nivel, grado = _dash_scope(current_user)
    stats = get_dashboard_stats(nivel=nivel, grado=grado)
    anio_actual = datetime.date.today().year
    terms = Term.query.filter_by(anio=anio_actual).order_by(Term.orden).all()

    scope_label = None
    if nivel and grado:
        scope_label = f"{grado}\u00b0 {nivel}"
    elif nivel:
        scope_label = nivel

    return render(
        request, "main/dashboard.html",
        stats=stats, terms=terms, anio=anio_actual, scope_label=scope_label,
    )


@router.get("/dashboard/charts-data", name="main.charts_data")
async def charts_data(request: Request, current_user: User = Depends(require_login)):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel, grado = _dash_scope(current_user)

    return JSONResponse({
        "estudiantes_por_nivel": get_students_by_nivel(nivel=nivel, grado=grado),
        "distribucion_notas": get_grade_distribution_by_term(anio, nivel=nivel, grado=grado),
        "promedio_por_bimestre": get_average_by_term(anio, nivel=nivel, grado=grado),
        "asistencia_mensual": get_attendance_by_month(anio, nivel=nivel, grado=grado),
    })
