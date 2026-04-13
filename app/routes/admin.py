import io

from pydantic import ValidationError
from fastapi import APIRouter, Request, Depends, File, UploadFile
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError
from app.auth.dependencies import require_role
from app.database import db
from app.schemas.json_payloads import AdminCourseSavePayload
from app.utils.safe_errors import log_unexpected_exc, GENERIC_FLASH_MESSAGE, GENERIC_USER_MESSAGE
from app.models.user import User, RoleEnum, TeacherCourse
from app.models.academic import Course, Term, EDA, AREAS
from app.services.boleta_staff_service import get_staff_map, upsert_staff_map, all_boleta_staff_keys
from app.services.excel_import_teachers import (
    import_teachers_from_excel,
    generate_teachers_template_excel,
    MAX_EXCEL_BYTES as _TEACHERS_EXCEL_MAX_BYTES,
)
from app.services.feature_flags import (
    is_eda_matrix_enabled_for_docentes,
    set_eda_matrix_enabled_for_docentes,
)
from app.models.student import Student, GRADOS, NIVELES, GRADOS_INICIAL, GRADOS_PRIMARIA, GRADOS_SECUNDARIA
from app import render, flash, redirect_to
import datetime

router = APIRouter(tags=["admin"])


# ── USUARIOS ──────────────────────────────────────────────────────────────────

@router.get("/users", name="admin.users")
async def users(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    users_list = User.query.order_by(User.full_name).all()
    return render(request, "admin/users.html", users=users_list, roles=RoleEnum)


@router.get("/users/new", name="admin.new_user")
async def new_user_page(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    all_courses = Course.query.order_by(Course.nivel, Course.area, Course.nombre).all()
    from app.models.student import GRADOS_INICIAL, GRADOS_PRIMARIA, GRADOS_SECUNDARIA
    return render(request, "admin/user_form.html", user=None, roles=RoleEnum,
                  all_courses=all_courses, assigned_ids=set(), niveles=NIVELES,
                  grados_map={"INICIAL": GRADOS_INICIAL, "PRIMARIA": GRADOS_PRIMARIA, "SECUNDARIA": GRADOS_SECUNDARIA})


@router.post("/users/new", name="admin.new_user_post")
async def new_user_submit(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    form = await request.form()
    try:
        user = User(
            username=form["username"].strip(),
            full_name=form["full_name"].strip(),
            role=RoleEnum(form["role"]),
            nivel=form.get("nivel") or None,
            grado=form.get("grado") or None,
            is_active=True,
        )
        user.set_password(form["password"])
        db.session.add(user)
        db.session.flush()

        if user.role == RoleEnum.DOCENTE:
            selected_ids = set(int(x) for x in form.getlist("course_ids"))
            for cid in selected_ids:
                db.session.add(TeacherCourse(user_id=user.id, course_id=cid))

        db.session.commit()
        flash(request, "Usuario creado correctamente.", "success")
        return redirect_to("/admin/users")
    except IntegrityError:
        db.session.rollback()
        flash(request, "No se pudo crear el usuario (datos duplicados o inválidos).", "danger")
    except Exception as exc:
        db.session.rollback()
        log_unexpected_exc(exc, "admin.new_user_post")
        flash(request, GENERIC_FLASH_MESSAGE, "danger")

    all_courses = Course.query.order_by(Course.nivel, Course.area, Course.nombre).all()
    from app.models.student import GRADOS_INICIAL, GRADOS_PRIMARIA, GRADOS_SECUNDARIA
    return render(request, "admin/user_form.html", user=None, roles=RoleEnum,
                  all_courses=all_courses, assigned_ids=set(), niveles=NIVELES,
                  grados_map={"INICIAL": GRADOS_INICIAL, "PRIMARIA": GRADOS_PRIMARIA, "SECUNDARIA": GRADOS_SECUNDARIA})


@router.get("/users/{user_id}/edit", name="admin.edit_user")
async def edit_user_page(user_id: int, request: Request, current_user: User = Depends(require_role("ADMIN"))):
    user = User.query.get(user_id)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    all_courses = Course.query.order_by(Course.nivel, Course.area, Course.nombre).all()
    from app.models.student import GRADOS_INICIAL, GRADOS_PRIMARIA, GRADOS_SECUNDARIA
    assigned_ids = user.assigned_course_ids() if user.role == RoleEnum.DOCENTE else set()
    return render(request, "admin/user_form.html", user=user, roles=RoleEnum,
                  all_courses=all_courses, assigned_ids=assigned_ids, niveles=NIVELES,
                  grados_map={"INICIAL": GRADOS_INICIAL, "PRIMARIA": GRADOS_PRIMARIA, "SECUNDARIA": GRADOS_SECUNDARIA})


@router.post("/users/{user_id}/edit", name="admin.edit_user_post")
async def edit_user_submit(user_id: int, request: Request, current_user: User = Depends(require_role("ADMIN"))):
    user = User.query.get(user_id)
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    form = await request.form()
    try:
        user.full_name = form["full_name"].strip()
        user.role = RoleEnum(form["role"])
        user.is_active = "is_active" in form
        user.nivel = form.get("nivel") or None
        user.grado = form.get("grado") or None
        if form.get("password"):
            user.set_password(form["password"])

        TeacherCourse.query.filter_by(user_id=user.id).delete()
        if user.role == RoleEnum.DOCENTE:
            selected_ids = set(int(x) for x in form.getlist("course_ids"))
            for cid in selected_ids:
                db.session.add(TeacherCourse(user_id=user.id, course_id=cid))

        db.session.commit()
        flash(request, "Usuario actualizado.", "success")
        return redirect_to("/admin/users")
    except IntegrityError:
        db.session.rollback()
        flash(request, "No se pudo actualizar el usuario (datos duplicados o inválidos).", "danger")
    except Exception as exc:
        db.session.rollback()
        log_unexpected_exc(exc, "admin.edit_user_post")
        flash(request, GENERIC_FLASH_MESSAGE, "danger")

    all_courses = Course.query.order_by(Course.nivel, Course.area, Course.nombre).all()
    from app.models.student import GRADOS_INICIAL, GRADOS_PRIMARIA, GRADOS_SECUNDARIA
    assigned_ids = user.assigned_course_ids() if user.role == RoleEnum.DOCENTE else set()
    return render(request, "admin/user_form.html", user=user, roles=RoleEnum,
                  all_courses=all_courses, assigned_ids=assigned_ids, niveles=NIVELES,
                  grados_map={"INICIAL": GRADOS_INICIAL, "PRIMARIA": GRADOS_PRIMARIA, "SECUNDARIA": GRADOS_SECUNDARIA})


@router.get("/users/plantilla-docentes", name="admin.download_teachers_template")
async def download_teachers_template(current_user: User = Depends(require_role("ADMIN"))):
    buffer = generate_teachers_template_excel()
    return Response(
        content=buffer.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plantilla_docentes.xlsx"'},
    )


@router.post("/users/importar-docentes", name="admin.import_teachers_excel")
async def import_teachers_excel(
    request: Request,
    excel_file: UploadFile = File(None),
    current_user: User = Depends(require_role("ADMIN")),
):
    if not excel_file or excel_file.filename == "":
        flash(request, "Selecciona un archivo Excel (.xlsx).", "warning")
        return redirect_to("/admin/users")

    if not excel_file.filename.lower().endswith(".xlsx"):
        flash(request, "Solo se aceptan archivos .xlsx (Excel 2007+).", "danger")
        return redirect_to("/admin/users")

    try:
        total = 0
        chunks: list[bytes] = []
        while True:
            chunk = await excel_file.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > _TEACHERS_EXCEL_MAX_BYTES:
                flash(request, "El archivo supera el tamaño máximo permitido (5 MB).", "danger")
                return redirect_to("/admin/users")
            chunks.append(chunk)
        content = b"".join(chunks)
        if len(content) < 4 or content[:2] != b"PK":
            flash(request, "El archivo no parece un Excel .xlsx válido.", "danger")
            return redirect_to("/admin/users")
        result = import_teachers_from_excel(io.BytesIO(content))
    except ValueError as e:
        flash(request, str(e), "danger")
        return redirect_to("/admin/users")
    except Exception as exc:
        log_unexpected_exc(exc, "admin.import_teachers_excel")
        flash(request, GENERIC_FLASH_MESSAGE, "danger")
        return redirect_to("/admin/users")

    return render(request, "admin/teachers_import_result.html", result=result)


# ── CURSOS ────────────────────────────────────────────────────────────────────

@router.get("/courses", name="admin.courses")
async def courses(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    nivel_filter = request.query_params.get("nivel", "PRIMARIA")
    courses_list = Course.query.filter_by(nivel=nivel_filter).order_by(Course.area, Course.nombre).all()
    return render(request, "admin/courses.html", courses=courses_list, areas=AREAS,
                  grados=GRADOS, niveles=NIVELES, nivel_filter=nivel_filter)


@router.post("/courses/save", name="admin.save_course")
async def save_course(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    try:
        data = AdminCourseSavePayload.model_validate(await request.json())
    except ValidationError:
        return JSONResponse({"ok": False, "error": "Datos inválidos."}, status_code=400)

    course_id = data.id
    try:
        if course_id:
            c = Course.query.get(int(course_id))
            if not c:
                return JSONResponse({"ok": False, "error": "Curso no encontrado."}, status_code=404)
            c.nombre = data.nombre.strip()
            c.area = data.area
            c.nivel = data.nivel or "PRIMARIA"
            c.grado = data.grado or None
        else:
            c = Course(
                nombre=data.nombre.strip(),
                area=data.area,
                nivel=data.nivel or "PRIMARIA",
                grado=data.grado or None,
            )
            db.session.add(c)
        db.session.commit()
        return JSONResponse({"ok": True, "id": c.id})
    except Exception as exc:
        db.session.rollback()
        log_unexpected_exc(exc, "admin.save_course")
        return JSONResponse({"ok": False, "error": GENERIC_USER_MESSAGE}, status_code=400)


@router.post("/courses/{course_id}/delete", name="admin.delete_course")
async def delete_course(course_id: int, request: Request, current_user: User = Depends(require_role("ADMIN"))):
    c = Course.query.get(course_id)
    if not c:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    db.session.delete(c)
    db.session.commit()
    flash(request, "Curso eliminado.", "success")
    return redirect_to("/admin/courses")


# ── BIMESTRES ─────────────────────────────────────────────────────────────────

@router.get("/terms", name="admin.terms")
async def terms(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    anio = int(request.query_params.get("anio", datetime.date.today().year))
    terms_list = Term.query.filter_by(anio=anio).order_by(Term.orden).all()
    return render(request, "admin/terms.html", terms=terms_list, anio=anio)


@router.post("/terms/{term_id}/toggle-lock", name="admin.toggle_term_lock")
async def toggle_term_lock(term_id: int, request: Request, current_user: User = Depends(require_role("ADMIN"))):
    term = Term.query.get(term_id)
    if not term:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    term.locked = not term.locked
    db.session.commit()
    estado = "bloqueado" if term.locked else "desbloqueado"
    flash(request, f"{term.nombre} {term.anio} {estado}.", "success")
    return redirect_to(f"/admin/terms?anio={term.anio}")


@router.post("/eda/{eda_id}/toggle-lock", name="admin.toggle_eda_lock")
async def toggle_eda_lock(eda_id: int, request: Request, current_user: User = Depends(require_role("ADMIN"))):
    eda = EDA.query.get(eda_id)
    if not eda:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    eda.locked = not eda.locked
    db.session.commit()
    estado = "bloqueada" if eda.locked else "desbloqueada"
    flash(request, f"{eda.nombre} ({eda.term.nombre}) {estado}.", "success")
    return redirect_to(f"/admin/terms?anio={eda.term.anio}")


# ── Firmas en boletas (coordinadores / tutores) ───────────────────────────────

@router.get("/boleta-firmas", name="admin.boleta_firmas")
async def boleta_firmas_page(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    m = get_staff_map()
    return render(
        request,
        "admin/boleta_firmas.html",
        staff=m,
        grados_inicial=GRADOS_INICIAL,
        grados_primaria=GRADOS_PRIMARIA,
        grados_secundaria=GRADOS_SECUNDARIA,
    )


@router.post("/boleta-firmas", name="admin.boleta_firmas_post")
async def boleta_firmas_save(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    form = await request.form()
    try:
        data = {k: (form.get(k) or "").strip() for k in all_boleta_staff_keys()}
        upsert_staff_map(data)
        flash(request, "Datos de firmas de boletas guardados.", "success")
    except Exception as exc:
        db.session.rollback()
        log_unexpected_exc(exc, "admin.boleta_firmas_post")
        flash(request, GENERIC_FLASH_MESSAGE, "danger")
    return redirect_to("/admin/boleta-firmas")


@router.get("/feature-flags", name="admin.feature_flags")
async def feature_flags_page(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    return render(
        request,
        "admin/feature_flags.html",
        eda_matrix_docente=is_eda_matrix_enabled_for_docentes(),
    )


@router.post("/feature-flags", name="admin.feature_flags_post")
async def feature_flags_save(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    form = await request.form()
    try:
        set_eda_matrix_enabled_for_docentes(form.get("eda_matrix_docente") == "on")
        flash(request, "Opciones guardadas.", "success")
    except Exception as exc:
        db.session.rollback()
        log_unexpected_exc(exc, "admin.feature_flags_post")
        flash(request, GENERIC_FLASH_MESSAGE, "danger")
    return redirect_to("/admin/feature-flags")


@router.post("/terms/seed", name="admin.seed_terms")
async def seed_terms(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    from app.services.eda_service import seed_edas_for_term
    form = await request.form()
    anio = int(form.get("anio", datetime.date.today().year))
    nombres = ["I Bimestre", "II Bimestre", "III Bimestre", "IV Bimestre"]
    created_terms = 0
    for orden, nombre in enumerate(nombres, 1):
        term = Term.query.filter_by(nombre=nombre, anio=anio).first()
        if not term:
            term = Term(nombre=nombre, orden=orden, anio=anio)
            db.session.add(term)
            db.session.flush()
            created_terms += 1
        seed_edas_for_term(term.id)
    db.session.commit()
    flash(request, f"{created_terms} bimestre(s) creados con sus EDAs para {anio}.", "success")
    return redirect_to(f"/admin/terms?anio={anio}")


# ── ELIMINACIÓN MASIVA DE ESTUDIANTES ────────────────────────────────────────

@router.get("/students/bulk-delete", name="admin.bulk_delete_students")
async def bulk_delete_students_page(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    counts = dict(
        db.session.query(Student.nivel, db.func.count(Student.id))
        .group_by(Student.nivel).all()
    )
    return render(request, "admin/bulk_delete_students.html",
                  niveles=NIVELES, counts=counts)


@router.post("/students/bulk-delete", name="admin.bulk_delete_students_post")
async def bulk_delete_students_submit(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    form = await request.form()

    # Validar CSRF
    nivel = (form.get("nivel") or "").strip().upper()
    confirmacion = (form.get("confirmacion") or "").strip()

    if nivel not in NIVELES:
        flash(request, "Selecciona un nivel válido.", "danger")
        return redirect_to("/admin/students/bulk-delete")

    expected = f"ELIMINAR {nivel}"
    if confirmacion != expected:
        flash(request, f"Escribe exactamente «{expected}» para confirmar.", "danger")
        return redirect_to("/admin/students/bulk-delete")

    try:
        students = Student.query.filter_by(nivel=nivel).all()
        count = len(students)
        for s in students:
            db.session.delete(s)
        db.session.commit()
        flash(request, f"{count} estudiantes de {nivel} eliminados correctamente.", "success")
    except Exception as exc:
        db.session.rollback()
        log_unexpected_exc(exc, "admin.bulk_delete_students_post")
        flash(request, GENERIC_FLASH_MESSAGE, "danger")

    return redirect_to("/admin/students/bulk-delete")


# ── REGENERAR CÓDIGOS DE ESTUDIANTES ─────────────────────────────────────────

@router.get("/students/regenerate-codes", name="admin.regenerate_codes")
async def regenerate_codes_page(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    counts = dict(
        db.session.query(Student.nivel, db.func.count(Student.id))
        .group_by(Student.nivel).all()
    )
    total = sum(counts.values())
    return render(request, "admin/regenerate_codes.html",
                  niveles=NIVELES, counts=counts, total=total)


@router.post("/students/regenerate-codes", name="admin.regenerate_codes_post")
async def regenerate_codes_submit(request: Request, current_user: User = Depends(require_role("ADMIN"))):
    from app.services.student_service import regenerate_codes
    form = await request.form()
    nivel = (form.get("nivel") or "").strip().upper()

    if nivel and nivel not in NIVELES:
        flash(request, "Nivel no válido.", "danger")
        return redirect_to("/admin/students/regenerate-codes")

    try:
        count = regenerate_codes(nivel=nivel or None)
        label = nivel if nivel else "todos los niveles"
        flash(request, f"{count} códigos de {label} regenerados correctamente.", "success")
    except Exception as exc:
        db.session.rollback()
        log_unexpected_exc(exc, "admin.regenerate_codes_post")
        flash(request, GENERIC_FLASH_MESSAGE, "danger")

    return redirect_to("/admin/students/regenerate-codes")
