from app.database import db


NIVELES = ["INICIAL", "PRIMARIA", "SECUNDARIA"]
GRADOS_INICIAL = ["3", "4", "5"]
GRADOS_PRIMARIA = ["1", "2", "3", "4", "5", "6"]
GRADOS_SECUNDARIA = ["1", "2", "3", "4", "5"]
GRADOS = ["1", "2", "3", "4", "5", "6"]
SECCIONES = ["A"]
ESTADOS = ["ACTIVO", "RETIRADO", "TRASLADADO"]


class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False, index=True)
    nombres = db.Column(db.String(128), nullable=False)
    apellido_paterno = db.Column(db.String(64), nullable=False)
    apellido_materno = db.Column(db.String(64), nullable=False, default="", server_default="")
    nivel = db.Column(db.String(20), nullable=False, default="PRIMARIA", server_default="PRIMARIA")
    grado = db.Column(db.String(10), nullable=False)
    seccion = db.Column(db.String(5), nullable=False, default="A", server_default="A")
    estado = db.Column(db.String(20), nullable=False, default="ACTIVO")
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    dni = db.Column(db.String(8), nullable=True)

    # Relaciones
    grades = db.relationship("Grade", backref="student", lazy="dynamic", cascade="all, delete-orphan")
    attendance = db.relationship("Attendance", backref="student", lazy="dynamic", cascade="all, delete-orphan")
    behavior = db.relationship("Behavior", backref="student", lazy="dynamic", cascade="all, delete-orphan")
    behavior_monthly = db.relationship("BehaviorMonthly", backref="student", lazy="dynamic", cascade="all, delete-orphan")
    parent_responsibility = db.relationship("ParentResponsibility", backref="student", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def apellidos(self):
        """Compatibilidad: retorna apellido paterno + materno concatenados."""
        if self.apellido_materno:
            return f"{self.apellido_paterno} {self.apellido_materno}"
        return self.apellido_paterno

    @property
    def full_name(self):
        return f"{self.apellidos}, {self.nombres}"

    @property
    def aula(self):
        return f"{self.grado} {self.seccion}"

    def __repr__(self):
        return f"<Student {self.codigo} - {self.full_name}>"
