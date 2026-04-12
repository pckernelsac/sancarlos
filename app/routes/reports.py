from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import Response
from app.database import db
from app.auth.dependencies import require_login, require_role
from app.services.pdf_service_primaria import generate_boleta_primaria_pdf, generate_bulk_boletas_primaria_pdf
from app.services.pdf_service_secundaria import generate_boleta_secundaria_pdf, generate_bulk_boletas_secundaria_pdf
from app.services.pdf_service_inicial import generate_boleta_inicial_pdf, generate_bulk_boletas_inicial_pdf
from app.utils.id_mask import encode_id, decode_id
from app.models.student import Student
from app.models.academic import (
    Term, EDA, EdaGrade, EdaComment,
    INDICADORES_CONDUCTA, INDICADORES_CONDUCTA_SECUNDARIA,
    INDICADORES_PPFF, INDICADORES_PPFF_SECUNDARIA, MESES,
)
from app.services.grade_service import get_student_grades_matrix
from app.services.attendance_service import get_student_attendance
from app.services.behavior_service import (
    get_student_behavior, get_student_behavior_all_terms,
    get_behavior_average, get_behavior_indicator_averages,
)
from app.services.parent_service import (
    get_student_ppff_all_terms, get_ppff_average, get_ppff_indicator_averages,
)
from app.models.user import User
from app.security.permissions import assert_can_view_student
from app import render, flash, redirect_to
from app.services.boleta_staff_service import (
    get_staff_map,
    firma_boleta_for_student,
    firma_coord_label_for_nivel,
)
import datetime

router = APIRouter(tags=["reports"])


# ── Contexto principal ────────────────────────────────────────────────────────

def _build_boleta_context(student_id: int, anio: int, staff_map: dict | None = None) -> dict:
    student = Student.query.get(student_id)
    if not student:
        raise HTTPException(status_code=404)
    matrix, terms = get_student_grades_matrix(student_id, anio)
    attendance_list = get_student_attendance(student_id, anio)
    behavior = get_student_behavior(student_id, anio)

    eda_data: dict = {}
    for term in terms:
        edas = EDA.query.filter_by(term_id=term.id).order_by(EDA.orden).all()
        eda_data[term.id] = {}
        for eda in edas:
            eg_list = EdaGrade.query.filter_by(student_id=student_id, eda_id=eda.id).all()
            eda_data[term.id][eda.orden] = {eg.course_id: eg.numeric_value for eg in eg_list}

    att_by_month = {a.mes: a for a in attendance_list}
    total_faltas = sum(a.faltas for a in attendance_list)
    total_tardanzas = sum(a.tardanzas for a in attendance_list)

    comments_per_term: dict[int, str] = {}
    for term in terms:
        edas = EDA.query.filter_by(term_id=term.id).order_by(EDA.orden).all()
        text = ""
        for eda in edas:
            ec = EdaComment.query.filter_by(student_id=student_id, eda_id=eda.id).first()
            if ec and ec.comentario:
                text = ec.comentario
                break
        comments_per_term[term.id] = text

    all_vals = [d["promedio_num"] for d in matrix.values() if d["promedio_num"] is not None]
    promedio_anual = round(sum(all_vals) / len(all_vals)) if all_vals else None

    behavior_avg = get_behavior_average(student_id, anio, student.nivel)
    behavior_by_term = get_student_behavior_all_terms(student_id, anio)
    behavior_ind_avgs = get_behavior_indicator_averages(
        student_id, anio, INDICADORES_CONDUCTA, student.nivel
    )

    ppff_by_term = get_student_ppff_all_terms(student_id, anio)
    ppff_avg = get_ppff_average(student_id, anio, student.nivel)
    ppff_ind_avgs = get_ppff_indicator_averages(student_id, anio, student.nivel)

    if staff_map is None:
        staff_map = get_staff_map()

    return {
        "student": student, "matrix": matrix, "terms": terms,
        "eda_data": eda_data, "att_by_month": att_by_month,
        "total_faltas": total_faltas, "total_tardanzas": total_tardanzas,
        "behavior": behavior, "behavior_by_term": behavior_by_term,
        "behavior_promedio": behavior_avg, "behavior_ind_avgs": behavior_ind_avgs,
        "indicadores": INDICADORES_CONDUCTA, "indicadores_ppff": INDICADORES_PPFF,
        "ppff_by_term": ppff_by_term, "ppff_promedio": ppff_avg,
        "ppff_ind_avgs": ppff_ind_avgs, "meses": MESES,
        "comments_per_term": comments_per_term, "promedio_anual": promedio_anual,
        "anio": anio, "fecha_emision": datetime.date.today().strftime("%d/%m/%Y"),
        "firma_boleta": firma_boleta_for_student(student, staff_map),
        "firma_coord_label": firma_coord_label_for_nivel(student.nivel),
    }


# ── Rutas ─────────────────────────────────────────────────────────────────────

@router.get("/student/{token}/boleta", name="reports.boleta_preview")
async def boleta_preview(token: str, request: Request, current_user: User = Depends(require_login)):
    student_id = decode_id(token)
    student = Student.query.get(student_id)
    if not student:
        raise HTTPException(status_code=404)
    assert_can_view_student(current_user, student)
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    ctx = _build_boleta_context(student_id, anio)
    return render(request, "reports/boleta_template.html", **ctx)


@router.get("/student/{token}/boleta/pdf", name="reports.boleta_pdf")
async def boleta_pdf(token: str, request: Request, current_user: User = Depends(require_login)):
    student_id = decode_id(token)
    student = Student.query.get(student_id)
    if not student:
        raise HTTPException(status_code=404)
    assert_can_view_student(current_user, student)
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    ctx = _build_boleta_context(student_id, anio)
    pdf_bytes = generate_boleta_primaria_pdf(ctx)
    filename = f"boleta_{ctx['student'].codigo}_{anio}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


@router.get("/student/{token}/boleta-inicial", name="reports.boleta_inicial_preview")
async def boleta_inicial_preview(token: str, request: Request, current_user: User = Depends(require_login)):
    student_id = decode_id(token)
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    student = Student.query.get(student_id)
    if not student:
        raise HTTPException(status_code=404)
    assert_can_view_student(current_user, student)
    if student.nivel != "INICIAL":
        return redirect_to(f"/reports/student/{encode_id(student_id)}/boleta?anio={anio}")
    ctx = _build_boleta_context(student_id, anio)
    return render(request, "reports/boleta_inicial_template.html", **ctx)


@router.get("/student/{token}/boleta-inicial/pdf", name="reports.boleta_inicial_pdf")
async def boleta_inicial_pdf(token: str, request: Request, current_user: User = Depends(require_login)):
    student_id = decode_id(token)
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    student = Student.query.get(student_id)
    if not student:
        raise HTTPException(status_code=404)
    assert_can_view_student(current_user, student)
    if student.nivel != "INICIAL":
        return redirect_to(f"/reports/student/{encode_id(student_id)}/boleta/pdf?anio={anio}")
    ctx = _build_boleta_context(student_id, anio)
    pdf_bytes = generate_boleta_inicial_pdf(ctx)
    filename = f"boleta_ini_{ctx['student'].codigo}_{anio}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})


# ── Boletas masivas ────────────────────────────────────────────────────────────

@router.get("/boletas-masivas", name="reports.boletas_masivas")
async def boletas_masivas(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel = request.query_params.get("nivel", "")
    grado = request.query_params.get("grado", "")
    seccion = request.query_params.get("seccion", "")
    generar = request.query_params.get("generar", "")

    niveles = sorted({s.nivel for s in Student.query.with_entities(Student.nivel).filter_by(estado="ACTIVO").distinct()})
    grados_q = Student.query.with_entities(Student.grado).filter_by(estado="ACTIVO")
    if nivel:
        grados_q = grados_q.filter_by(nivel=nivel)
    grados = sorted({s.grado for s in grados_q.distinct()})
    secciones = sorted({s.seccion for s in Student.query.with_entities(Student.seccion).filter_by(estado="ACTIVO").distinct()})

    if not generar:
        return render(request, "reports/boletas_masivas.html",
                      anio=anio, nivel=nivel, grado=grado, seccion=seccion,
                      niveles=niveles, grados=grados, secciones=secciones)

    q = Student.query.filter_by(estado="ACTIVO")
    if nivel:
        q = q.filter_by(nivel=nivel)
    if grado:
        q = q.filter_by(grado=grado)
    if seccion:
        q = q.filter_by(seccion=seccion)
    students = q.order_by(Student.grado, Student.seccion, Student.apellido_paterno, Student.apellido_materno).all()

    if not students:
        flash(request, "No se encontraron estudiantes activos con los filtros seleccionados.", "warning")
        return redirect_to(f"/reports/boletas-masivas?anio={anio}&grado={grado}&seccion={seccion}")

    staff_map = get_staff_map()
    ctx_list = []
    for s in students:
        if s.nivel == "SECUNDARIA":
            ctx_list.append(_build_boleta_context_secundaria(s.id, anio, staff_map))
        else:
            ctx_list.append(_build_boleta_context(s.id, anio, staff_map))

    ini_ctxs = [c for c, s in zip(ctx_list, students) if s.nivel == "INICIAL"]
    prim_ctxs = [c for c, s in zip(ctx_list, students) if s.nivel == "PRIMARIA"]
    sec_ctxs = [c for c, s in zip(ctx_list, students) if s.nivel == "SECUNDARIA"]

    parts = []
    if ini_ctxs:
        parts.append(generate_bulk_boletas_inicial_pdf(ini_ctxs))
    if prim_ctxs:
        parts.append(generate_bulk_boletas_primaria_pdf(prim_ctxs))
    if sec_ctxs:
        parts.append(generate_bulk_boletas_secundaria_pdf(sec_ctxs))

    if len(parts) == 1:
        pdf_bytes = parts[0]
    else:
        try:
            import pypdf
            import io as io_mod
            writer = pypdf.PdfWriter()
            for part in parts:
                reader = pypdf.PdfReader(io_mod.BytesIO(part))
                for page in reader.pages:
                    writer.add_page(page)
            buf = io_mod.BytesIO()
            writer.write(buf)
            pdf_bytes = buf.getvalue()
        except Exception:
            pdf_bytes = parts[0]

    scope = f"grado{grado}" if grado else "todos"
    if seccion:
        scope += f"_sec{seccion}"
    filename = f"boletas_{scope}_{anio}.pdf"

    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ── Boleta SECUNDARIA ──────────────────────────────────────────────────────────

def _build_boleta_context_secundaria(student_id: int, anio: int, staff_map: dict | None = None) -> dict:
    ctx = _build_boleta_context(student_id, anio, staff_map)
    ctx["indicadores"] = INDICADORES_CONDUCTA_SECUNDARIA
    ctx["behavior_ind_avgs"] = get_behavior_indicator_averages(
        student_id, anio, INDICADORES_CONDUCTA_SECUNDARIA, ctx["student"].nivel
    )
    ctx["area_avgs"] = _compute_area_avgs(ctx)
    return ctx


def _compute_area_avgs(ctx: dict) -> dict:
    matrix = ctx["matrix"]
    terms = ctx["terms"]
    nivel = ctx["student"].nivel
    area_avgs: dict[str, dict] = {}
    for data in matrix.values():
        area = data["course"].area
        if area not in area_avgs:
            area_avgs[area] = {t.id: [] for t in terms}
        for term in terms:
            g = data["terms"].get(term.id)
            if g and g.numeric_value is not None:
                area_avgs[area][term.id].append(g.numeric_value)

    from app.services.grade_service import _round_half_up, numeric_to_qualitative
    result: dict[str, dict] = {}
    for area, term_vals in area_avgs.items():
        result[area] = {}
        all_pf_vals = []
        for term_id, vals in term_vals.items():
            if vals:
                avg = _round_half_up(sum(vals) / len(vals))
                result[area][term_id] = {"num": avg, "cual": numeric_to_qualitative(avg, nivel)}
                all_pf_vals.append(avg)
            else:
                result[area][term_id] = None
        if all_pf_vals:
            pf = _round_half_up(sum(all_pf_vals) / len(all_pf_vals))
            result[area]["pf"] = {"num": pf, "cual": numeric_to_qualitative(pf, nivel)}
        else:
            result[area]["pf"] = None
    return result


@router.get("/student/{token}/boleta-secundaria", name="reports.boleta_secundaria_preview")
async def boleta_secundaria_preview(token: str, request: Request, current_user: User = Depends(require_login)):
    student_id = decode_id(token)
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    student = Student.query.get(student_id)
    if not student:
        raise HTTPException(status_code=404)
    assert_can_view_student(current_user, student)
    if student.nivel != "SECUNDARIA":
        return redirect_to(f"/reports/student/{encode_id(student_id)}/boleta?anio={anio}")
    ctx = _build_boleta_context_secundaria(student_id, anio)
    return render(request, "reports/boleta_secundaria_template.html", **ctx)


@router.get("/student/{token}/boleta-secundaria/pdf", name="reports.boleta_secundaria_pdf")
async def boleta_secundaria_pdf(token: str, request: Request, current_user: User = Depends(require_login)):
    student_id = decode_id(token)
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    student = Student.query.get(student_id)
    if not student:
        raise HTTPException(status_code=404)
    assert_can_view_student(current_user, student)
    if student.nivel != "SECUNDARIA":
        return redirect_to(f"/reports/student/{encode_id(student_id)}/boleta/pdf?anio={anio}")
    ctx = _build_boleta_context_secundaria(student_id, anio)
    pdf_bytes = generate_boleta_secundaria_pdf(ctx)
    filename = f"boleta_sec_{ctx['student'].codigo}_{anio}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})
