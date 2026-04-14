from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, Response
from app.auth.dependencies import require_login, require_role
from app.services.student_service import get_all_students, create_student, update_student, delete_student, generate_student_code
from app.services.excel_service import import_students_from_excel, generate_template_excel
from app.models.student import Student, GRADOS, SECCIONES, ESTADOS, NIVELES, GRADOS_INICIAL, GRADOS_PRIMARIA, GRADOS_SECUNDARIA
from app.models.user import User, RoleEnum
from app.models.academic import Course
from app.security.permissions import can_edit_student
from app.utils.id_mask import encode_id
from app import render, flash, redirect_to
from app.utils.safe_errors import log_unexpected_exc, GENERIC_FLASH_MESSAGE
import datetime

router = APIRouter(tags=["students"])

# Subida Excel: tope de tamaño y firma ZIP (xlsx)
_EXCEL_MAX_BYTES = 5 * 1024 * 1024
_STUDENT_FIELD_LIMITS = {
    "nombres": 120,
    "apellido_paterno": 80,
    "apellido_materno": 80,
    "dni": 24,
    "grado": 16,
    "seccion": 8,
}
_SEARCH_Q_MAX = 120


def _docente_scope(user):
    from app.utils.scope import _docente_scope_from_courses
    niveles, grados = _docente_scope_from_courses(user)
    return (list(niveles), list(grados))


@router.get("/", name="students.list_students")
async def list_students(request: Request, current_user: User = Depends(require_login)):
    nivel = request.query_params.get("nivel", "")
    grado = request.query_params.get("grado", "")
    seccion = request.query_params.get("seccion", "")
    estado = request.query_params.get("estado", "ACTIVO")
    try:
        page = max(1, int(request.query_params.get("page", "1")))
    except (ValueError, TypeError):
        page = 1

    if current_user.role == RoleEnum.DOCENTE:
        doc_niveles, doc_grados = _docente_scope(current_user)
        if nivel and nivel in doc_niveles:
            filter_nivel = nivel
        elif len(doc_niveles) == 1:
            filter_nivel = doc_niveles[0]
        else:
            filter_nivel = nivel or None
        if grado and grado in doc_grados:
            filter_grado = grado
        elif len(doc_grados) == 1:
            filter_grado = doc_grados[0]
        else:
            filter_grado = grado or None

        result = get_all_students(
            nivel=filter_nivel, grado=filter_grado,
            seccion=seccion or None, estado=estado or None,
            allowed_niveles=doc_niveles if not filter_nivel else None,
            allowed_grados=doc_grados if not filter_grado else None,
            page=page,
        )
        filtros_niveles = doc_niveles
    else:
        result = get_all_students(
            nivel=nivel or None, grado=grado or None,
            seccion=seccion or None, estado=estado or None,
            page=page,
        )
        filtros_niveles = NIVELES

    grados_por_nivel = {
        "INICIAL": GRADOS_INICIAL,
        "PRIMARIA": GRADOS_PRIMARIA,
        "SECUNDARIA": GRADOS_SECUNDARIA,
    }

    filtros = {"nivel": nivel, "grado": grado, "seccion": seccion, "estado": estado}

    def _pagination_qs(pg):
        from urllib.parse import urlencode
        params = {k: v for k, v in filtros.items() if v}
        params["page"] = pg
        return urlencode(params)

    return render(
        request, "students/list.html",
        students=result["items"], niveles=filtros_niveles,
        grados_por_nivel=grados_por_nivel,
        secciones=SECCIONES, estados=ESTADOS,
        filtros=filtros,
        pagination={"page": result["page"], "total_pages": result["total_pages"], "total": result["total"]},
        _pagination_qs=_pagination_qs,
    )


@router.get("/new", name="students.new_student")
async def new_student_page(request: Request, current_user: User = Depends(require_role("ADMIN", "AUXILIAR"))):
    return render(request, "students/form.html", student=None,
                  niveles=NIVELES, grados=GRADOS, secciones=SECCIONES, estados=ESTADOS)


@router.post("/new", name="students.new_student_post")
async def new_student_submit(request: Request, current_user: User = Depends(require_role("ADMIN", "AUXILIAR"))):
    form = await request.form()
    try:
        data = _extract_student_form(form, is_new=True)
        student = create_student(data)
        flash(request, f"Estudiante {student.full_name} creado con código {student.codigo}.", "success")
        return redirect_to("/students/")
    except ValueError as e:
        flash(request, str(e), "danger")
    except Exception as exc:
        log_unexpected_exc(exc, "students.new_student_post")
        flash(request, GENERIC_FLASH_MESSAGE, "danger")
    return render(request, "students/form.html", student=None,
                  niveles=NIVELES, grados=GRADOS, secciones=SECCIONES, estados=ESTADOS)


@router.get("/{token}/edit", name="students.edit_student")
async def edit_student_page(token: str, request: Request, current_user: User = Depends(require_role("ADMIN", "AUXILIAR"))):
    from app.utils.id_mask import decode_id
    student_id = decode_id(token)
    student = Student.query.get(student_id)
    if not student:
        raise HTTPException(status_code=404)
    if not can_edit_student(current_user, student):
        raise HTTPException(status_code=403)
    return render(request, "students/form.html", student=student,
                  niveles=NIVELES, grados=GRADOS, secciones=SECCIONES, estados=ESTADOS)


@router.post("/{token}/edit", name="students.edit_student_post")
async def edit_student_submit(token: str, request: Request, current_user: User = Depends(require_role("ADMIN", "AUXILIAR"))):
    from app.utils.id_mask import decode_id
    student_id = decode_id(token)
    student = Student.query.get(student_id)
    if not student:
        raise HTTPException(status_code=404)
    if not can_edit_student(current_user, student):
        raise HTTPException(status_code=403)
    form = await request.form()
    try:
        data = _extract_student_form(form)
        update_student(student_id, data)
        flash(request, "Datos actualizados correctamente.", "success")
        return redirect_to("/students/")
    except ValueError as e:
        flash(request, str(e), "danger")
    except Exception as exc:
        log_unexpected_exc(exc, "students.edit_student_post")
        flash(request, GENERIC_FLASH_MESSAGE, "danger")
    return render(request, "students/form.html", student=student,
                  niveles=NIVELES, grados=GRADOS, secciones=SECCIONES, estados=ESTADOS)


@router.post("/{token}/delete", name="students.delete_student_view")
async def delete_student_view(token: str, request: Request, current_user: User = Depends(require_role("ADMIN"))):
    from app.utils.id_mask import decode_id
    student_id = decode_id(token)
    try:
        delete_student(student_id)
        flash(request, "Estudiante eliminado.", "success")
    except ValueError as e:
        flash(request, str(e), "danger")
    except Exception as exc:
        log_unexpected_exc(exc, "students.delete_student_view")
        flash(request, GENERIC_FLASH_MESSAGE, "danger")
    return redirect_to("/students/")


@router.get("/upload", name="students.upload_excel")
async def upload_page(request: Request, current_user: User = Depends(require_role("ADMIN", "AUXILIAR"))):
    return render(request, "students/upload.html", niveles=NIVELES, grados=GRADOS, secciones=SECCIONES)


@router.post("/upload", name="students.upload_excel_post")
async def upload_submit(request: Request, excel_file: UploadFile = File(None), current_user: User = Depends(require_role("ADMIN", "AUXILIAR"))):
    if not excel_file or excel_file.filename == "":
        flash(request, "Selecciona un archivo Excel (.xlsx).", "warning")
        return redirect_to("/students/upload")

    if not excel_file.filename.lower().endswith(".xlsx"):
        flash(request, "Solo se aceptan archivos .xlsx (Excel 2007+).", "danger")
        return redirect_to("/students/upload")

    try:
        import io

        total = 0
        chunks: list[bytes] = []
        while True:
            chunk = await excel_file.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > _EXCEL_MAX_BYTES:
                flash(request, "El archivo supera el tamaño máximo permitido (5 MB).", "danger")
                return redirect_to("/students/upload")
            chunks.append(chunk)
        content = b"".join(chunks)
        if len(content) < 4 or content[:2] != b"PK":
            flash(request, "El archivo no parece un Excel .xlsx válido.", "danger")
            return redirect_to("/students/upload")
        result = import_students_from_excel(io.BytesIO(content))
    except ValueError as e:
        flash(request, str(e), "danger")
        return redirect_to("/students/upload")
    except Exception as exc:
        log_unexpected_exc(exc, "students.upload_excel_post")
        flash(request, GENERIC_FLASH_MESSAGE, "danger")
        return redirect_to("/students/upload")

    return render(request, "students/upload_result.html", result=result)


@router.get("/upload/template", name="students.download_template")
async def download_template(current_user: User = Depends(require_role("ADMIN", "AUXILIAR"))):
    buffer = generate_template_excel()
    return Response(
        content=buffer.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="plantilla_estudiantes.xlsx"'},
    )


@router.get("/search", name="students.search")
async def search(request: Request, current_user: User = Depends(require_login)):
    q = request.query_params.get("q", "").strip()
    if len(q) < 2:
        return JSONResponse([])
    if len(q) > _SEARCH_Q_MAX:
        q = q[:_SEARCH_Q_MAX]
    query = Student.query.filter(
        (Student.nombres.ilike(f"%{q}%")) |
        (Student.apellido_paterno.ilike(f"%{q}%")) |
        (Student.apellido_materno.ilike(f"%{q}%")) |
        (Student.codigo.ilike(f"%{q}%"))
    ).filter_by(estado="ACTIVO")

    if current_user.role == RoleEnum.DOCENTE:
        doc_niveles, doc_grados = _docente_scope(current_user)
        if doc_niveles:
            query = query.filter(Student.nivel.in_(doc_niveles))
        if doc_grados:
            query = query.filter(Student.grado.in_(doc_grados))

    students = query.order_by(Student.apellido_paterno, Student.apellido_materno, Student.nombres).limit(20).all()
    return JSONResponse([{
        "token": encode_id(s.id),
        "codigo": s.codigo,
        "full_name": s.full_name, "aula": s.aula,
    } for s in students])


def _extract_student_form(form, is_new=False) -> dict:
    def _lim(key: str, value: str) -> str:
        m = _STUDENT_FIELD_LIMITS.get(key, 128)
        t = (value or "").strip()
        if len(t) > m:
            raise ValueError(f"El campo supera la longitud máxima permitida ({m} caracteres).")
        return t

    fecha = None
    fecha_str = form.get("fecha_nacimiento", "")
    if fecha_str:
        fecha = datetime.date.fromisoformat(fecha_str)
    ap_paterno = _lim("apellido_paterno", form["apellido_paterno"]).upper()
    ap_materno = _lim("apellido_materno", form.get("apellido_materno", "")).upper()
    nombres_raw = _lim("nombres", form["nombres"])
    data = {
        "nombres": nombres_raw.upper(),
        "apellido_paterno": ap_paterno,
        "apellido_materno": ap_materno,
        "nivel": form.get("nivel", "PRIMARIA"),
        "grado": _lim("grado", form["grado"]),
        "seccion": _lim("seccion", form["seccion"]),
        "estado": form.get("estado", "ACTIVO"),
        "dni": (_lim("dni", dr) if (dr := (form.get("dni") or "").strip()) else None),
        "fecha_nacimiento": fecha,
    }
    if is_new:
        data["codigo"] = generate_student_code(ap_paterno, ap_materno)
    return data
