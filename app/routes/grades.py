import io
import re
import zipfile

from pydantic import ValidationError
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse, Response
from app.database import db
from app.auth.dependencies import require_login, require_role
from app.schemas.json_payloads import (
    RegistroExamenPayload,
    RegistroHeadersPayload,
    RegistroItemPayload,
    SaveEdaCommentPayload,
    SaveEdaGradePayload,
    SaveGradePayload,
)
from app.security.permissions import assert_can_view_student, can_grade_student
from app.services.grade_service import upsert_grade, get_student_grades_matrix
from app.services.eda_service import upsert_eda_grade, get_eda_matrix_data, upsert_eda_comment
from app.services.registro_service import (
    upsert_semana_field, upsert_examen, get_registro_full, SEMANAS, CAMPOS_SEMANA, CAMPOS_SEMANA_3,
    get_headers_for_course, save_headers_for_course, DEFAULT_HEADERS,
)
from app.services.registro_pdf_service import generate_registro_auxiliar_pdf_bytes
from app.models.student import Student, GRADOS, SECCIONES, NIVELES
from app.models.academic import Course, Term, EDA
from app.models.user import User
from app import render, redirect_to
from app.utils.scope import sanitize_nivel_grado, user_allowed_grados
from app.utils.safe_errors import log_unexpected_exc, GENERIC_USER_MESSAGE
import datetime

router = APIRouter(tags=["grades"])


def _docente_niveles(allowed_ids):
    if allowed_ids is None:
        return NIVELES
    niveles = (
        db.session.query(Course.nivel)
        .filter(Course.id.in_(allowed_ids))
        .distinct()
        .all()
    )
    orden = {n: i for i, n in enumerate(NIVELES)}
    return sorted([n[0] for n in niveles], key=lambda x: orden.get(x, 99))


def _docente_grados(nivel, current_user):
    return user_allowed_grados(nivel, current_user)


def _safe_download_slug(text: str, max_len: int = 72) -> str:
    t = re.sub(r"[^\w\s\-]", "", (text or "").strip(), flags=re.UNICODE)
    t = re.sub(r"\s+", "_", t)
    return (t or "export")[:max_len]


@router.get("/matrix", name="grades.matrix")
async def matrix(request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel, grado = sanitize_nivel_grado(
        request.query_params.get("nivel", "PRIMARIA"),
        request.query_params.get("grado", ""),
        current_user,
    )
    seccion = request.query_params.get("seccion", "")
    term_id = request.query_params.get("term_id")
    term_id = int(term_id) if term_id else None

    terms = Term.query.filter_by(anio=anio).order_by(Term.orden).all()
    selected_term = None
    students = []
    courses = []
    grade_map = {}
    avg_map = {}

    allowed_ids = None
    if current_user.has_role("DOCENTE"):
        allowed_ids = current_user.assigned_course_ids()

    niveles_permitidos = _docente_niveles(allowed_ids)
    if nivel not in niveles_permitidos and niveles_permitidos:
        nivel = niveles_permitidos[0]

    if grado and seccion and term_id:
        selected_term = Term.query.get(term_id)
        if not selected_term:
            raise HTTPException(status_code=404)
        students = Student.query.filter_by(
            nivel=nivel, grado=grado, seccion=seccion, estado="ACTIVO"
        ).order_by(Student.apellido_paterno, Student.apellido_materno, Student.nombres).all()

        all_courses_q = Course.query.filter(
            Course.nivel == nivel,
            (Course.grado == grado) | (Course.grado.is_(None))
        ).order_by(Course.area, Course.nombre)
        courses = [c for c in all_courses_q if allowed_ids is None or c.id in allowed_ids]

        from app.models.academic import Grade
        if students and courses:
            st_ids = [s.id for s in students]
            co_ids = [c.id for c in courses]
            existing = Grade.query.filter(
                Grade.student_id.in_(st_ids),
                Grade.course_id.in_(co_ids),
                Grade.term_id == term_id,
            ).all()
            grade_map = {(g.student_id, g.course_id): g.numeric_value for g in existing}

        from app.services.grade_service import numeric_to_qualitative
        for s in students:
            vals = [grade_map[(s.id, c.id)] for c in courses
                    if (s.id, c.id) in grade_map and grade_map[(s.id, c.id)] is not None]
            if vals:
                avg = round(sum(vals) / len(vals))
                avg_map[s.id] = {"num": avg, "cual": numeric_to_qualitative(avg, nivel)}
            else:
                avg_map[s.id] = None

    return render(
        request, "grades/matrix.html",
        niveles=niveles_permitidos, nivel=nivel,
        grados=_docente_grados(nivel, current_user), secciones=SECCIONES,
        terms=terms, selected_term=selected_term,
        grado=grado, seccion=seccion,
        students=students, courses=courses,
        grade_map=grade_map, avg_map=avg_map,
        allowed_ids=allowed_ids, anio=anio,
    )


@router.post("/save", name="grades.save_grade")
async def save_grade(request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
    try:
        p = SaveGradePayload.model_validate(await request.json())
    except ValidationError:
        return JSONResponse({"ok": False, "error": "Datos inválidos."}, status_code=400)

    if current_user.has_role("DOCENTE"):
        return JSONResponse({"ok": False, "error": "Los docentes deben ingresar notas desde el Registro Auxiliar."}, status_code=403)

    student = db.session.get(Student, p.student_id)
    if not student:
        return JSONResponse({"ok": False, "error": "Estudiante no encontrado."}, status_code=404)
    if not can_grade_student(current_user, student, p.course_id):
        return JSONResponse({"ok": False, "error": "No tienes permiso para calificar este curso."}, status_code=403)

    try:
        raw = p.numeric_value
        numeric_value = int(raw) if str(raw).strip() != "" else None
    except (ValueError, TypeError):
        return JSONResponse({"ok": False, "error": "Nota no válida."}, status_code=400)

    try:
        grade = upsert_grade(p.student_id, p.course_id, p.term_id, numeric_value)
        return JSONResponse({"ok": True, "qualitative": grade.qualitative_grade, "numeric": grade.numeric_value})
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as exc:
        log_unexpected_exc(exc, "grades.save_grade")
        return JSONResponse({"ok": False, "error": "Error interno del servidor."}, status_code=500)


@router.get("/eda-matrix", name="grades.eda_matrix")
async def eda_matrix(request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel, grado = sanitize_nivel_grado(
        request.query_params.get("nivel", "PRIMARIA"),
        request.query_params.get("grado", ""),
        current_user,
    )
    seccion = request.query_params.get("seccion", "")
    term_id = request.query_params.get("term_id")
    term_id = int(term_id) if term_id else None

    terms = Term.query.filter_by(anio=anio).order_by(Term.orden).all()
    data = {}

    allowed_ids = None
    if current_user.has_role("DOCENTE"):
        allowed_ids = current_user.assigned_course_ids()

    niveles_permitidos = _docente_niveles(allowed_ids)
    if nivel not in niveles_permitidos and niveles_permitidos:
        nivel = niveles_permitidos[0]

    if grado and seccion and term_id:
        data = get_eda_matrix_data(grado, seccion, term_id, nivel=nivel, allowed_course_ids=allowed_ids)

    return render(
        request, "grades/eda_matrix.html",
        niveles=niveles_permitidos, nivel=nivel,
        grados=_docente_grados(nivel, current_user), secciones=SECCIONES,
        terms=terms, grado=grado, seccion=seccion,
        term_id=term_id, anio=anio, allowed_ids=allowed_ids,
        **data,
    )


@router.post("/eda/save", name="grades.save_eda_grade")
async def save_eda_grade(request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
    try:
        p = SaveEdaGradePayload.model_validate(await request.json())
    except ValidationError:
        return JSONResponse({"ok": False, "error": "Datos inválidos."}, status_code=400)

    if current_user.has_role("DOCENTE"):
        return JSONResponse({"ok": False, "error": "Los docentes deben ingresar notas desde el Registro Auxiliar."}, status_code=403)

    student = db.session.get(Student, p.student_id)
    if not student:
        return JSONResponse({"ok": False, "error": "Estudiante no encontrado."}, status_code=404)
    if not can_grade_student(current_user, student, p.course_id):
        return JSONResponse({"ok": False, "error": "No tienes permiso para calificar este curso."}, status_code=403)

    try:
        raw = p.numeric_value
        numeric_value = int(raw) if str(raw).strip() != "" else None
    except (ValueError, TypeError):
        return JSONResponse({"ok": False, "error": "Nota no válida."}, status_code=400)

    try:
        eg = upsert_eda_grade(p.student_id, p.course_id, p.eda_id, numeric_value)

        from app.models.academic import Grade, EDA as EdaModel
        eda = db.session.get(EdaModel, p.eda_id)
        bim = Grade.query.filter_by(
            student_id=p.student_id, course_id=p.course_id, term_id=eda.term_id
        ).first()

        return JSONResponse({
            "ok": True,
            "qualitative": eg.qualitative_grade,
            "numeric": eg.numeric_value,
            "bim_numeric": bim.numeric_value if bim else None,
            "bim_qual": bim.qualitative_grade if bim else "--",
        })
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as exc:
        log_unexpected_exc(exc, "grades.save_eda_grade")
        return JSONResponse({"ok": False, "error": "Error interno."}, status_code=500)


@router.post("/eda/comment", name="grades.save_eda_comment")
async def save_eda_comment(request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
    try:
        p = SaveEdaCommentPayload.model_validate(await request.json())
    except ValidationError:
        return JSONResponse({"ok": False, "error": "Datos inválidos."}, status_code=400)

    student = db.session.get(Student, p.student_id)
    if not student:
        return JSONResponse({"ok": False, "error": "Estudiante no encontrado."}, status_code=404)
    try:
        assert_can_view_student(current_user, student)
    except HTTPException as e:
        return JSONResponse({"ok": False, "error": e.detail}, status_code=e.status_code)

    if current_user.has_role("DOCENTE"):
        eda_obj = db.session.get(EDA, p.eda_id)
        if eda_obj and eda_obj.locked:
            return JSONResponse({"ok": False, "error": "La EDA está bloqueada. Contacta al administrador."}, status_code=423)
        term_obj = db.session.get(Term, eda_obj.term_id) if eda_obj else None
        if term_obj and term_obj.locked:
            return JSONResponse({"ok": False, "error": "El bimestre está bloqueado. Contacta al administrador."}, status_code=423)

    try:
        record = upsert_eda_comment(
            student_id=p.student_id,
            eda_id=p.eda_id,
            comentario=p.comentario,
        )
        return JSONResponse({"ok": True, "comentario": record.comentario or ""})
    except Exception as exc:
        log_unexpected_exc(exc, "grades.save_eda_comment")
        return JSONResponse({"ok": False, "error": GENERIC_USER_MESSAGE}, status_code=400)


@router.get("/student/{token}", name="grades.student_grades")
async def student_grades(token: str, request: Request, current_user: User = Depends(require_login)):
    from app.utils.id_mask import decode_id
    student_id = decode_id(token)
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    student = Student.query.get(student_id)
    if not student:
        raise HTTPException(status_code=404)
    assert_can_view_student(current_user, student)
    matrix, terms = get_student_grades_matrix(student_id, anio)
    return render(request, "grades/student_detail.html",
                  student=student, matrix=matrix, terms=terms, anio=anio)


# ═══════════════════════════════════════════════════════════════════════════════
#  REGISTRO AUXILIAR
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/registro-auxiliar", name="grades.registro_auxiliar")
async def registro_auxiliar(request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
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
    course_id = request.query_params.get("course_id")
    course_id = int(course_id) if course_id else None

    terms = Term.query.filter_by(anio=anio).order_by(Term.orden).all()
    edas = []
    courses_list = []

    allowed_ids = None
    if current_user.has_role("DOCENTE"):
        allowed_ids = current_user.assigned_course_ids()

    niveles_permitidos = _docente_niveles(allowed_ids)
    if nivel not in niveles_permitidos and niveles_permitidos:
        nivel = niveles_permitidos[0]

    if term_id:
        edas = EDA.query.filter_by(term_id=term_id).order_by(EDA.orden).all()

    if grado and term_id:
        all_courses = Course.query.filter(
            Course.nivel == nivel,
            (Course.grado == grado) | (Course.grado.is_(None))
        ).order_by(Course.area, Course.nombre).all()
        courses_list = [c for c in all_courses if allowed_ids is None or c.id in allowed_ids]

    if grado and seccion and eda_id and course_id:
        return redirect_to(
            f"/grades/registro-auxiliar/{eda_id}/{course_id}?grado={grado}&seccion={seccion}"
        )

    return render(
        request, "grades/registro_auxiliar_filter.html",
        niveles=niveles_permitidos, nivel=nivel,
        grados=_docente_grados(nivel, current_user), secciones=SECCIONES,
        terms=terms, edas=edas, courses=courses_list,
        grado=grado, seccion=seccion,
        term_id=term_id, eda_id=eda_id, course_id=course_id,
        allowed_ids=allowed_ids, anio=anio,
    )


@router.get("/registro-auxiliar/{eda_id}/{course_id}", name="grades.registro_auxiliar_detail")
async def registro_auxiliar_detail(eda_id: int, course_id: int, request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
    grado = request.query_params.get("grado", "")
    seccion = request.query_params.get("seccion", "")

    if not grado or not seccion:
        return redirect_to("/grades/registro-auxiliar")

    if not current_user.can_grade_course(course_id):
        raise HTTPException(status_code=403)

    data = get_registro_full(eda_id, course_id, grado, seccion)
    if not data:
        raise HTTPException(status_code=404)

    headers = get_headers_for_course(course_id)

    return render(
        request, "grades/registro_auxiliar.html",
        **data, grado=grado, seccion=seccion,
        semanas=SEMANAS, campos_semana=CAMPOS_SEMANA, campos_semana3=CAMPOS_SEMANA_3,
        headers=headers, default_headers=DEFAULT_HEADERS,
    )


@router.get("/registro-auxiliar/{eda_id}/{course_id}/export.pdf", name="grades.registro_auxiliar_export_pdf")
async def registro_auxiliar_export_pdf(eda_id: int, course_id: int, request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
    grado = request.query_params.get("grado", "")
    seccion = request.query_params.get("seccion", "")
    if not grado or not seccion:
        raise HTTPException(status_code=400)
    if not current_user.can_grade_course(course_id):
        raise HTTPException(status_code=403)
    data = get_registro_full(eda_id, course_id, grado, seccion)
    if not data:
        raise HTTPException(status_code=404)
    headers = get_headers_for_course(course_id)
    body = generate_registro_auxiliar_pdf_bytes(data, headers, grado=grado, seccion=seccion)
    eda = data["eda"]
    course = data["course"]
    base = _safe_download_slug(f"RegistroAux_{course.nombre}_{eda.nombre}_{grado}{seccion}")
    fname = f"{base}.pdf"
    return Response(content=body, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"', "Cache-Control": "no-store"})


@router.get("/registro-auxiliar/export.zip", name="grades.registro_auxiliar_export_zip")
async def registro_auxiliar_export_zip(request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    nivel, grado = sanitize_nivel_grado(
        request.query_params.get("nivel", "PRIMARIA"),
        request.query_params.get("grado", ""),
        current_user,
    )
    seccion = request.query_params.get("seccion", "") or "A"
    term_id = request.query_params.get("term_id")
    term_id = int(term_id) if term_id else None

    if not grado or not term_id:
        raise HTTPException(status_code=400)

    allowed_ids = None
    if current_user.has_role("DOCENTE"):
        allowed_ids = current_user.assigned_course_ids()

    niveles_permitidos = _docente_niveles(allowed_ids)
    if nivel not in niveles_permitidos and niveles_permitidos:
        raise HTTPException(status_code=403)

    term = Term.query.get(term_id)
    if not term or term.anio != anio:
        raise HTTPException(status_code=400)

    all_courses = Course.query.filter(
        Course.nivel == nivel,
        (Course.grado == grado) | (Course.grado.is_(None)),
    ).order_by(Course.area, Course.nombre).all()
    courses_list = [c for c in all_courses if allowed_ids is None or c.id in allowed_ids]
    edas = EDA.query.filter_by(term_id=term_id).order_by(EDA.orden).all()
    if not courses_list or not edas:
        raise HTTPException(status_code=404)

    buf = io.BytesIO()
    n_files = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for course in courses_list:
            hdrs = get_headers_for_course(course.id)
            for eda in edas:
                payload = get_registro_full(eda.id, course.id, grado, seccion)
                if not payload or not payload.get("students"):
                    continue
                pdf_bytes = generate_registro_auxiliar_pdf_bytes(payload, hdrs, grado=grado, seccion=seccion)
                inner = f"{course.id}_{eda.id}_{_safe_download_slug(course.nombre, 40)}_{_safe_download_slug(eda.nombre, 40)}.pdf"
                zf.writestr(inner, pdf_bytes)
                n_files += 1

    if n_files == 0:
        raise HTTPException(status_code=404)

    buf.seek(0)
    zip_name = _safe_download_slug(f"RegistrosAux_{nivel}_{grado}{seccion}_{term.nombre}_{term.anio}")
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}.zip"'},
    )


@router.post("/registro-auxiliar/save-item", name="grades.save_registro_item")
async def save_registro_item(request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
    try:
        p = RegistroItemPayload.model_validate(await request.json())
    except ValidationError:
        return JSONResponse({"ok": False, "error": "Datos inválidos."}, status_code=400)

    student = db.session.get(Student, p.student_id)
    if not student:
        return JSONResponse({"ok": False, "error": "Estudiante no encontrado."}, status_code=404)
    if not current_user.can_grade_course(p.course_id):
        return JSONResponse({"ok": False, "error": "Sin permiso para este curso."}, status_code=403)
    if not can_grade_student(current_user, student, p.course_id):
        return JSONResponse({"ok": False, "error": "Sin permiso para este estudiante."}, status_code=403)

    try:
        raw = p.value
        value = int(raw) if str(raw).strip() != "" else None
    except (ValueError, TypeError):
        return JSONResponse({"ok": False, "error": "Valor no válido."}, status_code=400)

    if current_user.has_role("DOCENTE"):
        eda_obj = db.session.get(EDA, p.eda_id)
        if eda_obj and eda_obj.locked:
            return JSONResponse({"ok": False, "error": "La EDA está bloqueada. Contacta al administrador."}, status_code=423)
        term_obj = db.session.get(Term, eda_obj.term_id) if eda_obj else None
        if term_obj and term_obj.locked:
            return JSONResponse({"ok": False, "error": "El bimestre está bloqueado. Contacta al administrador."}, status_code=423)

    try:
        result = upsert_semana_field(
            p.student_id, p.course_id, p.eda_id, p.semana, p.field, value
        )
        return JSONResponse({"ok": True, **result})
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as exc:
        log_unexpected_exc(exc, "grades.save_registro_item")
        return JSONResponse({"ok": False, "error": "Error interno."}, status_code=500)


@router.post("/registro-auxiliar/save-examen", name="grades.save_registro_examen")
async def save_registro_examen(request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
    try:
        p = RegistroExamenPayload.model_validate(await request.json())
    except ValidationError:
        return JSONResponse({"ok": False, "error": "Datos inválidos."}, status_code=400)

    student = db.session.get(Student, p.student_id)
    if not student:
        return JSONResponse({"ok": False, "error": "Estudiante no encontrado."}, status_code=404)
    if not current_user.can_grade_course(p.course_id):
        return JSONResponse({"ok": False, "error": "Sin permiso para este curso."}, status_code=403)
    if not can_grade_student(current_user, student, p.course_id):
        return JSONResponse({"ok": False, "error": "Sin permiso para este estudiante."}, status_code=403)

    try:
        raw = p.value
        value = int(raw) if str(raw).strip() != "" else None
    except (ValueError, TypeError):
        return JSONResponse({"ok": False, "error": "Valor no válido."}, status_code=400)

    if current_user.has_role("DOCENTE"):
        eda_obj = db.session.get(EDA, p.eda_id)
        if eda_obj and eda_obj.locked:
            return JSONResponse({"ok": False, "error": "La EDA está bloqueada. Contacta al administrador."}, status_code=423)
        term_obj = db.session.get(Term, eda_obj.term_id) if eda_obj else None
        if term_obj and term_obj.locked:
            return JSONResponse({"ok": False, "error": "El bimestre está bloqueado. Contacta al administrador."}, status_code=423)

    try:
        result = upsert_examen(p.student_id, p.course_id, p.eda_id, value)
        return JSONResponse({"ok": True, **result})
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as exc:
        log_unexpected_exc(exc, "grades.save_registro_examen")
        return JSONResponse({"ok": False, "error": "Error interno."}, status_code=500)


@router.post("/registro-auxiliar/save-headers", name="grades.save_registro_headers")
async def save_registro_headers(request: Request, current_user: User = Depends(require_role("ADMIN", "DOCENTE"))):
    try:
        p = RegistroHeadersPayload.model_validate(await request.json())
    except ValidationError:
        return JSONResponse({"ok": False, "error": "Datos inválidos."}, status_code=400)

    if not current_user.can_grade_course(p.course_id):
        return JSONResponse({"ok": False, "error": "Sin permiso para este curso."}, status_code=403)

    try:
        saved = save_headers_for_course(p.course_id, p.headers)
        return JSONResponse({"ok": True, "headers": saved})
    except Exception as exc:
        log_unexpected_exc(exc, "grades.save_registro_headers")
        return JSONResponse({"ok": False, "error": GENERIC_USER_MESSAGE}, status_code=400)
