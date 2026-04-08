import enum
from app.database import db
from werkzeug.security import generate_password_hash, check_password_hash


class RoleEnum(str, enum.Enum):
    ADMIN = "ADMIN"
    DOCENTE = "DOCENTE"
    AUXILIAR = "AUXILIAR"


class TeacherCourse(db.Model):
    """Asignación de cursos a docentes. ADMIN ignora esta tabla."""
    __tablename__ = "teacher_courses"
    __table_args__ = (
        db.UniqueConstraint("user_id", "course_id", name="uq_teacher_course"),
    )

    id        = db.Column(db.Integer, primary_key=True)
    user_id   = db.Column(db.Integer, db.ForeignKey("users.id",   ondelete="CASCADE"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)


class User(db.Model):
    __tablename__ = "users"

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name     = db.Column(db.String(128), nullable=False)
    role          = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.DOCENTE)
    is_active     = db.Column(db.Boolean, default=True, nullable=False)
    nivel         = db.Column(db.String(20), nullable=True)   # INICIAL, PRIMARIA, SECUNDARIA
    grado         = db.Column(db.String(10), nullable=True)   # "1"-"6" o None

    assigned_courses = db.relationship(
        "TeacherCourse", backref="teacher",
        cascade="all, delete-orphan", lazy="dynamic"
    )

    # --- Compat con templates (simulamos propiedades de Flask-Login) ---
    @property
    def is_authenticated(self):
        return True

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def has_role(self, *roles) -> bool:
        return self.role.value in roles

    def can_grade_course(self, course_id: int) -> bool:
        """ADMIN puede todo; DOCENTE solo sus cursos asignados."""
        if self.role == RoleEnum.ADMIN:
            return True
        return self.assigned_courses.filter_by(course_id=course_id).first() is not None

    def assigned_course_ids(self) -> set[int]:
        """Conjunto de course_id asignados al docente."""
        return {tc.course_id for tc in self.assigned_courses.all()}

    def __repr__(self):
        return f"<User {self.username} [{self.role.value}]>"
