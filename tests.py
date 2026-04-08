"""
Tests del Sistema Académico San Carlos
Ejecutar: python -m pytest tests.py -v
"""
import os
import re
# Forzar BD en memoria ANTES de importar la app, para que SQLAlchemy
# nunca toque el archivo real sancarlos.db
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
# Tests: sin rate limit en login (evita flakiness)
os.environ["LOGIN_RATE_LIMIT_MAX_FAILURES"] = "0"

import pytest
from starlette.testclient import TestClient

from app import create_app
from app.database import db
from app.models.user import User, RoleEnum, TeacherCourse
from app.models.student import Student
from app.models.academic import (
    Course, Term, Grade, Attendance, Behavior, EDA, EdaGrade,
    RegistroSemana, RegistroExamen, ParentResponsibility,
)
from app.services.grade_service import numeric_to_qualitative, upsert_grade


# ─── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def app():
    """Crea app con BD en memoria para tests."""
    application = create_app()
    db.create_all()
    yield application
    db.remove_session()
    db.drop_all()


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def seed(app):
    """Crea datos básicos y retorna dict con IDs."""
    admin = User(username="admin", full_name="Administrador", role=RoleEnum.ADMIN)
    admin.set_password("admin1234")

    docente = User(username="docente", full_name="Prof. García", role=RoleEnum.DOCENTE)
    docente.set_password("docente1234")

    auxiliar = User(username="auxiliar", full_name="Aux. López", role=RoleEnum.AUXILIAR)
    auxiliar.set_password("auxiliar1234")

    db.session.add_all([admin, docente, auxiliar])
    db.session.flush()

    term = Term(nombre="I Bimestre", orden=1, anio=2026)
    db.session.add(term)
    db.session.flush()

    eda = EDA(term_id=term.id, nombre="EDA 1", orden=1)
    db.session.add(eda)
    db.session.flush()

    course = Course(nombre="Matemática", area="Matemática", nivel="PRIMARIA")
    db.session.add(course)
    db.session.flush()

    tc = TeacherCourse(user_id=docente.id, course_id=course.id)
    db.session.add(tc)

    student = Student(
        codigo="2026-001", nombres="Juan",
        apellido_paterno="PEREZ", apellido_materno="GOMEZ",
        nivel="PRIMARIA", grado="3", seccion="A", estado="ACTIVO",
    )
    db.session.add(student)
    db.session.commit()

    return {
        "admin_id": admin.id, "docente_id": docente.id, "auxiliar_id": auxiliar.id,
        "term_id": term.id, "course_id": course.id, "student_id": student.id,
        "eda_id": eda.id,
    }


def login(client, username, password):
    """Inicia sesión; TestClient mantiene cookies automáticamente."""
    page = client.get("/auth/login")
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text)
    token = m.group(1) if m else ""
    return client.post(
        "/auth/login",
        data={"username": username, "password": password, "csrf_token": token},
        headers={"X-CSRFToken": token},
        follow_redirects=True,
    )


# ─── 1. Tests de creación de la app ─────────────────────────────────

class TestAppFactory:
    def test_app_creates(self, app):
        assert app is not None

    def test_routers_registered(self, app):
        """Verifica que las rutas principales existan."""
        paths = [r.path for r in app.routes if hasattr(r, "path")]
        # Verificar que al menos algunas rutas clave están registradas
        assert any("/auth" in p for p in paths)
        assert any("/students" in p for p in paths)
        assert any("/grades" in p for p in paths)


# ─── 2. Tests de modelos ────────────────────────────────────────────

class TestUserModel:
    def test_create_user(self, app, seed):
        user = db.session.get(User, seed["admin_id"])
        assert user.username == "admin"
        assert user.role == RoleEnum.ADMIN

    def test_password_hashing(self, app, seed):
        user = db.session.get(User, seed["admin_id"])
        assert user.check_password("admin1234") is True
        assert user.check_password("wrong") is False

    def test_has_role(self, app, seed):
        admin = db.session.get(User, seed["admin_id"])
        docente = db.session.get(User, seed["docente_id"])
        auxiliar = db.session.get(User, seed["auxiliar_id"])
        assert admin.has_role("ADMIN") is True
        assert docente.has_role("DOCENTE") is True
        assert auxiliar.has_role("AUXILIAR") is True
        assert docente.has_role("ADMIN") is False

    def test_can_grade_course_admin(self, app, seed):
        admin = db.session.get(User, seed["admin_id"])
        assert admin.can_grade_course(seed["course_id"]) is True

    def test_can_grade_course_docente(self, app, seed):
        docente = db.session.get(User, seed["docente_id"])
        assert docente.can_grade_course(seed["course_id"]) is True
        assert docente.can_grade_course(99999) is False

    def test_assigned_course_ids(self, app, seed):
        docente = db.session.get(User, seed["docente_id"])
        ids = docente.assigned_course_ids()
        assert seed["course_id"] in ids

    def test_repr(self, app, seed):
        admin = db.session.get(User, seed["admin_id"])
        assert "admin" in repr(admin)


class TestStudentModel:
    def test_create_student(self, app, seed):
        s = db.session.get(Student, seed["student_id"])
        assert s.codigo == "2026-001"
        assert s.nivel == "PRIMARIA"

    def test_full_name(self, app, seed):
        s = db.session.get(Student, seed["student_id"])
        assert s.full_name == "PEREZ GOMEZ, Juan"

    def test_aula(self, app, seed):
        s = db.session.get(Student, seed["student_id"])
        assert s.aula == "3 A"


class TestAcademicModels:
    def test_term_creation(self, app, seed):
        t = db.session.get(Term, seed["term_id"])
        assert t.nombre == "I Bimestre"
        assert t.anio == 2026

    def test_course_creation(self, app, seed):
        c = db.session.get(Course, seed["course_id"])
        assert c.area == "Matemática"

    def test_grade_unique_constraint(self, app, seed):
        g1 = Grade(student_id=seed["student_id"], course_id=seed["course_id"],
                    term_id=seed["term_id"], numeric_value=15)
        db.session.add(g1)
        db.session.commit()

        g2 = Grade(student_id=seed["student_id"], course_id=seed["course_id"],
                    term_id=seed["term_id"], numeric_value=18)
        db.session.add(g2)
        with pytest.raises(Exception):
            db.session.commit()
        db.session.rollback()

    def test_attendance_model(self, app, seed):
        a = Attendance(student_id=seed["student_id"], mes="Marzo", anio=2026, faltas=2, tardanzas=1)
        db.session.add(a)
        db.session.commit()
        assert a.id is not None

    def test_behavior_qualitative(self, app, seed):
        b = Behavior(student_id=seed["student_id"], indicador="Respeto",
                     eda_id=seed["eda_id"], calificacion=19)
        db.session.add(b)
        db.session.commit()
        assert b.qualitative_grade == "AD"

    def test_eda_grade(self, app, seed):
        eg = EdaGrade(student_id=seed["student_id"], course_id=seed["course_id"],
                      eda_id=seed["eda_id"], numeric_value=16)
        db.session.add(eg)
        db.session.commit()
        assert eg.qualitative_grade == "A"

    def test_registro_semana_promedio(self, app, seed):
        rs = RegistroSemana(
            student_id=seed["student_id"], course_id=seed["course_id"],
            eda_id=seed["eda_id"], semana=1,
            tarea=14, intervencion=16, fast_test=12, aptitudinal=18,
        )
        db.session.add(rs)
        db.session.commit()
        assert rs.promedio == 15

    def test_registro_semana3_includes_extras(self, app, seed):
        rs = RegistroSemana(
            student_id=seed["student_id"], course_id=seed["course_id"],
            eda_id=seed["eda_id"], semana=3,
            tarea=10, intervencion=10, fast_test=10, aptitudinal=10,
            rev_cuaderno=20, rev_libro=20,
        )
        db.session.add(rs)
        db.session.commit()
        # (10+10+10+10+20+20)/6 = 13.33 → 13
        assert rs.promedio == 13

    def test_registro_semana_promedio_none(self, app, seed):
        rs = RegistroSemana(
            student_id=seed["student_id"], course_id=seed["course_id"],
            eda_id=seed["eda_id"], semana=2,
        )
        db.session.add(rs)
        db.session.commit()
        assert rs.promedio is None

    def test_parent_responsibility_qualitative(self, app, seed):
        pr = ParentResponsibility(
            student_id=seed["student_id"], indicador="Reuniones",
            term_id=seed["term_id"], calificacion=12,
        )
        db.session.add(pr)
        db.session.commit()
        assert pr.qualitative_grade == "B"


# ─── 3. Tests del servicio de notas ─────────────────────────────────

class TestGradeService:
    def test_qualitative_ad(self):
        assert numeric_to_qualitative(20, "PRIMARIA") == "AD"
        assert numeric_to_qualitative(18, "SECUNDARIA") == "AD"

    def test_qualitative_a(self):
        assert numeric_to_qualitative(15, "PRIMARIA") == "A"
        assert numeric_to_qualitative(14, "PRIMARIA") == "A"

    def test_qualitative_b(self):
        assert numeric_to_qualitative(13, "PRIMARIA") == "B"
        assert numeric_to_qualitative(11, "PRIMARIA") == "B"

    def test_qualitative_c(self):
        assert numeric_to_qualitative(10, "PRIMARIA") == "C"
        assert numeric_to_qualitative(0, "PRIMARIA") == "C"

    def test_qualitative_none(self):
        assert numeric_to_qualitative(None) == "--"

    def test_qualitative_inicial_no_ad(self):
        assert numeric_to_qualitative(20, "INICIAL") == "A"
        assert numeric_to_qualitative(14, "INICIAL") == "A"
        assert numeric_to_qualitative(13, "INICIAL") == "B"
        assert numeric_to_qualitative(10, "INICIAL") == "C"

    def test_upsert_grade_create(self, app, seed):
        g = upsert_grade(seed["student_id"], seed["course_id"], seed["term_id"], 17)
        assert g.id is not None
        assert g.numeric_value == 17

    def test_upsert_grade_update(self, app, seed):
        upsert_grade(seed["student_id"], seed["course_id"], seed["term_id"], 14)
        g = upsert_grade(seed["student_id"], seed["course_id"], seed["term_id"], 19)
        assert g.numeric_value == 19
        count = Grade.query.filter_by(
            student_id=seed["student_id"], course_id=seed["course_id"]
        ).count()
        assert count == 1

    def test_upsert_grade_invalid_range(self, app, seed):
        with pytest.raises(ValueError):
            upsert_grade(seed["student_id"], seed["course_id"], seed["term_id"], 25)
        with pytest.raises(ValueError):
            upsert_grade(seed["student_id"], seed["course_id"], seed["term_id"], -1)

    def test_upsert_grade_none(self, app, seed):
        g = upsert_grade(seed["student_id"], seed["course_id"], seed["term_id"], None)
        assert g.numeric_value is None

    def test_grade_qualitative_property(self, app, seed):
        g = upsert_grade(seed["student_id"], seed["course_id"], seed["term_id"], 18)
        assert g.qualitative_grade == "AD"


# ─── 4. Tests de autenticación ──────────────────────────────────────

class TestAuth:
    def test_login_page_loads(self, client, seed):
        resp = client.get("/auth/login")
        assert resp.status_code == 200

    def test_login_valid(self, client, seed):
        resp = login(client, "admin", "admin1234")
        assert resp.status_code == 200

    def test_login_invalid_password(self, client, seed):
        resp = login(client, "admin", "wrongpass")
        assert "incorrectos" in resp.text

    def test_login_invalid_user(self, client, seed):
        resp = login(client, "noexiste", "pass")
        assert "incorrectos" in resp.text

    def test_logout(self, client, seed):
        login(client, "admin", "admin1234")
        resp = client.get("/auth/logout", follow_redirects=True)
        assert resp.status_code == 200

    def test_redirect_when_not_logged(self, client, seed):
        resp = client.get("/students/", follow_redirects=False)
        assert resp.status_code == 303


# ─── 5. Tests de permisos por rol ───────────────────────────────────

class TestPermissions:
    def test_admin_access_students(self, client, seed):
        login(client, "admin", "admin1234")
        resp = client.get("/students/")
        assert resp.status_code == 200

    def test_admin_access_admin_panel(self, client, seed):
        login(client, "admin", "admin1234")
        resp = client.get("/admin/users")
        assert resp.status_code == 200

    def test_docente_cannot_access_admin(self, client, seed):
        login(client, "docente", "docente1234")
        resp = client.get("/admin/users", follow_redirects=False)
        assert resp.status_code in (303, 403)

    def test_auxiliar_cannot_access_grades(self, client, seed):
        login(client, "auxiliar", "auxiliar1234")
        resp = client.get("/grades/matrix", follow_redirects=False)
        assert resp.status_code in (303, 403)


# ─── 6. Tests de rutas principales ──────────────────────────────────

class TestRoutes:
    def test_dashboard(self, client, seed):
        login(client, "admin", "admin1234")
        resp = client.get("/dashboard")
        assert resp.status_code == 200

    def test_students_list(self, client, seed):
        login(client, "admin", "admin1234")
        resp = client.get("/students/")
        assert resp.status_code == 200

    def test_grades_page(self, client, seed):
        login(client, "admin", "admin1234")
        resp = client.get("/grades/matrix")
        assert resp.status_code == 200

    def test_attendance_page(self, client, seed):
        login(client, "admin", "admin1234")
        resp = client.get("/attendance/")
        assert resp.status_code == 200

    def test_behavior_page(self, client, seed):
        login(client, "admin", "admin1234")
        resp = client.get("/behavior/")
        assert resp.status_code == 200

    def test_404_page(self, client, seed):
        login(client, "admin", "admin1234")
        resp = client.get("/ruta-inexistente")
        assert resp.status_code == 404


# ─── 7. Tests de cascada y relaciones ───────────────────────────────

class TestCascade:
    def test_delete_student_cascades_grades(self, app, seed):
        upsert_grade(seed["student_id"], seed["course_id"], seed["term_id"], 15)
        assert Grade.query.count() == 1
        student = db.session.get(Student, seed["student_id"])
        db.session.delete(student)
        db.session.commit()
        assert Grade.query.count() == 0

    def test_delete_student_cascades_attendance(self, app, seed):
        a = Attendance(student_id=seed["student_id"], mes="Abril", anio=2026, faltas=0, tardanzas=0)
        db.session.add(a)
        db.session.commit()
        student = db.session.get(Student, seed["student_id"])
        db.session.delete(student)
        db.session.commit()
        assert Attendance.query.count() == 0

    def test_delete_student_cascades_behavior(self, app, seed):
        b = Behavior(student_id=seed["student_id"], indicador="Orden",
                     eda_id=seed["eda_id"], calificacion=15)
        db.session.add(b)
        db.session.commit()
        student = db.session.get(Student, seed["student_id"])
        db.session.delete(student)
        db.session.commit()
        assert Behavior.query.count() == 0


# ─── 8. Tests de edge cases ─────────────────────────────────────────

class TestEdgeCases:
    def test_qualitative_boundary_values(self):
        assert numeric_to_qualitative(18, "PRIMARIA") == "AD"
        assert numeric_to_qualitative(17, "PRIMARIA") == "A"
        assert numeric_to_qualitative(14, "PRIMARIA") == "A"
        assert numeric_to_qualitative(13, "PRIMARIA") == "B"
        assert numeric_to_qualitative(11, "PRIMARIA") == "B"
        assert numeric_to_qualitative(10, "PRIMARIA") == "C"

    def test_behavior_qualitative_all_ranges(self, app, seed):
        cases = [(20, "AD"), (18, "AD"), (17, "A"), (15, "A"), (14, "B"), (11, "B"), (10, "C"), (0, "C")]
        for val, expected in cases:
            b = Behavior(student_id=seed["student_id"], indicador=f"Test{val}",
                         eda_id=seed["eda_id"], calificacion=val)
            assert b.qualitative_grade == expected

    def test_behavior_qualitative_none(self, app, seed):
        b = Behavior(student_id=seed["student_id"], indicador="X",
                     eda_id=seed["eda_id"], calificacion=None)
        assert b.qualitative_grade is None

    def test_user_inactive_cannot_login(self, app, client, seed):
        docente = db.session.get(User, seed["docente_id"])
        docente.is_active = False
        db.session.commit()
        resp = login(client, "docente", "docente1234")
        assert "incorrectos" in resp.text


# ─── 9. Endurecimiento (cabeceras, CSRF, redirects, IDOR) ─────────

class TestSecurityHardening:
    def test_security_headers_on_login_page(self, client):
        r = client.get("/auth/login")
        assert r.status_code == 200
        assert r.headers.get("x-frame-options", "").upper() == "DENY"
        assert "nosniff" in (r.headers.get("x-content-type-options") or "").lower()
        csp = r.headers.get("content-security-policy") or ""
        assert csp
        assert "cdn.jsdelivr.net" in csp  # Chart.js en dashboard / consolidado
        assert "strict-origin-when-cross-origin" in (r.headers.get("referrer-policy") or "").lower()

    def test_login_post_rejects_mismatched_csrf_header(self, client, seed):
        page = client.get("/auth/login")
        m = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text)
        token = m.group(1) if m else ""
        # Sin cabecera CSRF válida y con Origin ajeno al host, no aplica el bypass same-site.
        resp = client.post(
            "/auth/login",
            data={"username": "admin", "password": "admin1234", "csrf_token": token},
            headers={
                "X-CSRFToken": "token-invalido-forzado",
                "Origin": "https://evil.example",
            },
        )
        assert resp.status_code == 403

    def test_login_redirect_ignores_external_next(self, client, seed):
        page = client.get("/auth/login")
        m = re.search(r'name="csrf_token"\s+value="([^"]+)"', page.text)
        token = m.group(1) if m else ""
        resp = client.post(
            "/auth/login?next=https://evil.example/phish",
            data={"username": "admin", "password": "admin1234", "csrf_token": token},
            headers={"X-CSRFToken": token},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        loc = resp.headers.get("location", "")
        assert loc.startswith("/")
        assert "evil.example" not in loc

    def test_docente_idor_cannot_open_secundaria_student_grades(self, app, client, seed):
        from app.utils.id_mask import encode_id

        s2 = Student(
            codigo="2026-SEC-01",
            nombres="Ana",
            apellido_paterno="LOPEZ",
            apellido_materno="RUIZ",
            nivel="SECUNDARIA",
            grado="1",
            seccion="A",
            estado="ACTIVO",
        )
        db.session.add(s2)
        db.session.commit()

        login(client, "docente", "docente1234")
        token = encode_id(s2.id)
        resp = client.get(f"/grades/student/{token}")
        assert resp.status_code == 403
