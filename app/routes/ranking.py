import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response
from app.auth.dependencies import require_login
from app.models.academic import Term
from app.models.user import User
from app.services.ranking_service import get_top_students, get_top_students_annual
from app.services.ranking_pdf_service import generate_ranking_pdf
from app.utils.scope import user_allowed_grados, user_allowed_niveles, sanitize_nivel_grado
from app import render

router = APIRouter(tags=["ranking"])


@router.get("/", name="ranking.index")
async def index(request: Request, current_user: User = Depends(require_login)):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel, grado = sanitize_nivel_grado(
        request.query_params.get("nivel", "PRIMARIA"),
        request.query_params.get("grado", ""),
        current_user,
    )

    terms = Term.query.filter_by(anio=anio).order_by(Term.orden).all()
    term_id = request.query_params.get("term_id", "")

    ranking_data = {}
    if grado:
        for t in terms:
            ranking_data[t.id] = get_top_students(nivel, grado, t.id, top_n=10)
        ranking_data["anual"] = get_top_students_annual(nivel, grado, anio, top_n=10)

    return render(
        request, "ranking/index.html",
        niveles=user_allowed_niveles(current_user), nivel=nivel,
        grados=user_allowed_grados(nivel, current_user), grado=grado,
        terms=terms, term_id=term_id, anio=anio, ranking_data=ranking_data,
    )


@router.get("/pdf", name="ranking.download_pdf")
async def download_pdf(request: Request, current_user: User = Depends(require_login)):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel, grado = sanitize_nivel_grado(
        request.query_params.get("nivel", "PRIMARIA"),
        request.query_params.get("grado", ""),
        current_user,
    )

    if not grado:
        return Response(content="Seleccione un grado.", status_code=400)

    terms = Term.query.filter_by(anio=anio).order_by(Term.orden).all()
    ranking_data = {}
    for t in terms:
        ranking_data[t.id] = get_top_students(nivel, grado, t.id, top_n=10)
    ranking_data["anual"] = get_top_students_annual(nivel, grado, anio, top_n=10)

    buffer = generate_ranking_pdf(ranking_data, terms, nivel, grado, anio)
    return Response(
        content=buffer.read(),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="cuadro_merito_{nivel}_{grado}_{anio}.pdf"'},
    )
