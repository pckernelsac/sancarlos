import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from app.auth.dependencies import require_login
from app.models.student import SECCIONES
from app.models.user import User
from app.services.consolidado_service import get_consolidado
from app.utils.scope import user_allowed_grados, user_allowed_niveles, sanitize_nivel_grado
from app import render

router = APIRouter(tags=["consolidado"])


@router.get("/", name="consolidado.index")
async def index(request: Request, current_user: User = Depends(require_login)):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel, grado = sanitize_nivel_grado(
        request.query_params.get("nivel", "PRIMARIA"),
        request.query_params.get("grado", ""),
        current_user,
    )
    seccion = request.query_params.get("seccion", "")

    data = {}
    if grado:
        data = get_consolidado(nivel, grado, seccion, anio)

    return render(
        request, "consolidado/index.html",
        niveles=user_allowed_niveles(current_user), nivel=nivel,
        grados=user_allowed_grados(nivel, current_user), grado=grado,
        secciones=SECCIONES, seccion=seccion, anio=anio, data=data,
    )


@router.get("/chart-data", name="consolidado.chart_data")
async def chart_data(request: Request, current_user: User = Depends(require_login)):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel, grado = sanitize_nivel_grado(
        request.query_params.get("nivel", "PRIMARIA"),
        request.query_params.get("grado", ""),
        current_user,
    )
    seccion = request.query_params.get("seccion", "")

    if not grado:
        return JSONResponse({"labels": [], "datasets": [], "promedios": []})

    data = get_consolidado(nivel, grado, seccion, anio)

    labels = [s["student"]["full_name"] if isinstance(s["student"], dict) else s["student"].full_name
              for s in data["students"]]
    terms = data["terms"]

    colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444"]
    datasets = []
    for i, term in enumerate(terms):
        datasets.append({
            "label": term.nombre,
            "data": [s["bimestres"].get(term.id) for s in data["students"]],
            "backgroundColor": colors[i % len(colors)],
        })

    promedios = [s["promedio"] for s in data["students"]]

    return JSONResponse({"labels": labels, "datasets": datasets, "promedios": promedios})
