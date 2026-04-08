from sqlalchemy import text

from app.database import db


AREAS = [
    "Comunicación",
    "Matemática",
    "DPCC",
    "Ciencias Sociales",
    "Ciencia y Tecnología",
    "Personal Social",
    "Arte y Cultura",
    "Educación Física",
    "Educación Religiosa",
    "Idioma Inglés",
    "Tutoría",
    "Informática",
]

INDICADORES_CONDUCTA = [
    "Responsabilidad", "Respeto", "Solidaridad", "Puntualidad", "Orden"
]

INDICADORES_CONDUCTA_SECUNDARIA = [
    "Puntualidad", "Higiene", "Disciplina - Respeto",
    "Uniforme", "Cabello", "Cumple con el Reglamento", "No porta celular"
]

INDICADORES_PPFF = [
    "Reuniones", "Colabora", "Normas"
]

INDICADORES_PPFF_SECUNDARIA = [
    "Respeta el Reglamento Interno.",
    "Es responsable con su hijo(a).",
    "No permite el uso del celular a su hijo(a).",
]

MESES = [
    "Marzo", "Abril", "Mayo", "Junio", "Julio",
    "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    area = db.Column(db.String(80), nullable=False)
    nivel = db.Column(db.String(20), nullable=False, default="PRIMARIA", server_default="PRIMARIA")
    grado = db.Column(db.String(10), nullable=True)  # None = todos los grados del nivel

    grades = db.relationship("Grade", backref="course", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Course {self.nombre}>"


class Term(db.Model):
    __tablename__ = "terms"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(30), nullable=False)   # "I Bimestre", etc.
    orden = db.Column(db.Integer, nullable=False)        # 1, 2, 3, 4
    anio = db.Column(db.Integer, nullable=False)
    locked = db.Column(db.Boolean, default=False, nullable=False, server_default=text("false"))

    grades = db.relationship("Grade", backref="term", lazy="dynamic", cascade="all, delete-orphan")
    edas   = db.relationship("EDA",   backref="term", lazy="dynamic", cascade="all, delete-orphan",
                             order_by="EDA.orden")


class EDA(db.Model):
    """Evaluación de Desempeño del Aprendizaje — 2 por bimestre, 8 por año."""
    __tablename__ = "edas"
    __table_args__ = (
        db.UniqueConstraint("term_id", "orden", name="uq_eda"),
    )

    id      = db.Column(db.Integer, primary_key=True)
    term_id = db.Column(db.Integer, db.ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    nombre  = db.Column(db.String(20), nullable=False)  # "EDA 1", "EDA 2"
    orden   = db.Column(db.Integer,    nullable=False)   # 1, 2
    locked  = db.Column(db.Boolean, default=False, nullable=False, server_default=text("false"))

    eda_grades   = db.relationship("EdaGrade",   backref="eda", lazy="dynamic", cascade="all, delete-orphan")
    eda_comments = db.relationship("EdaComment", backref="eda", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<EDA {self.nombre} term={self.term_id}>"


class EdaGrade(db.Model):
    """Nota individual por EDA (estudiante × curso × EDA)."""
    __tablename__ = "eda_grades"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", "eda_id", name="uq_eda_grade"),
    )

    id            = db.Column(db.Integer, primary_key=True)
    student_id    = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id     = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    eda_id        = db.Column(db.Integer, db.ForeignKey("edas.id",    ondelete="CASCADE"), nullable=False)
    numeric_value = db.Column(db.Integer, nullable=True)   # 0-20

    course_rel = db.relationship("Course", foreign_keys=[course_id], lazy="joined")

    @property
    def qualitative_grade(self) -> str:
        from app.services.grade_service import numeric_to_qualitative
        nivel = self.course_rel.nivel if self.course_rel else "PRIMARIA"
        return numeric_to_qualitative(self.numeric_value, nivel)

    def __repr__(self):
        return f"<EdaGrade st={self.student_id} c={self.course_id} eda={self.eda_id} val={self.numeric_value}>"


class EdaComment(db.Model):
    """Observación / comentario general del docente por estudiante por EDA."""
    __tablename__ = "eda_comments"
    __table_args__ = (
        db.UniqueConstraint("student_id", "eda_id", name="uq_eda_comment"),
    )

    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    eda_id     = db.Column(db.Integer, db.ForeignKey("edas.id",     ondelete="CASCADE"), nullable=False)
    comentario = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<EdaComment st={self.student_id} eda={self.eda_id}>"


class Grade(db.Model):
    __tablename__ = "grades"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", "term_id", name="uq_grade"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    term_id = db.Column(db.Integer, db.ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    numeric_value = db.Column(db.Integer, nullable=True)  # 0-20 — None = sin calificar

    @property
    def qualitative_grade(self) -> str:
        """Mapeo según escala del nivel (INICIAL / PRIMARIA / SECUNDARIA)."""
        from app.services.grade_service import numeric_to_qualitative
        nivel = self.course.nivel if self.course else "PRIMARIA"
        return numeric_to_qualitative(self.numeric_value, nivel)

    def __repr__(self):
        return f"<Grade st={self.student_id} course={self.course_id} term={self.term_id} val={self.numeric_value}>"


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint("student_id", "mes", "anio", name="uq_attendance"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    mes = db.Column(db.String(20), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    faltas = db.Column(db.Integer, default=0, nullable=False)
    tardanzas = db.Column(db.Integer, default=0, nullable=False)

    def __repr__(self):
        return f"<Attendance st={self.student_id} {self.mes}/{self.anio}>"


class RegistroSemana(db.Model):
    """Registro auxiliar semanal — ítems de evaluación por (estudiante, curso, EDA, semana)."""
    __tablename__ = "registro_semanas"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", "eda_id", "semana", name="uq_reg_semana"),
    )

    id         = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id  = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    eda_id     = db.Column(db.Integer, db.ForeignKey("edas.id",    ondelete="CASCADE"), nullable=False)
    semana     = db.Column(db.Integer, nullable=False)   # 1, 2, 3, 4

    tarea        = db.Column(db.Integer, nullable=True)  # 0-20
    intervencion = db.Column(db.Integer, nullable=True)  # 0-20
    fast_test    = db.Column(db.Integer, nullable=True)  # 0-20
    aptitudinal  = db.Column(db.Integer, nullable=True)  # 0-20
    rev_cuaderno = db.Column(db.Integer, nullable=True)  # 0-20  (solo semana 3)
    rev_libro    = db.Column(db.Integer, nullable=True)  # 0-20  (solo semana 3)

    @property
    def promedio(self):
        """Promedio de los ítems no nulos de esta semana (redondeo .5 hacia arriba)."""
        items = [self.tarea, self.intervencion, self.fast_test, self.aptitudinal]
        if self.semana == 3:
            items += [self.rev_cuaderno, self.rev_libro]
        vals = [v for v in items if v is not None]
        if not vals:
            return None
        return int(sum(vals) / len(vals) + 0.5)

    def __repr__(self):
        return f"<RegistroSemana st={self.student_id} c={self.course_id} eda={self.eda_id} sem={self.semana}>"


class RegistroExamen(db.Model):
    """Examen bimestral del registro auxiliar por (estudiante, curso, EDA)."""
    __tablename__ = "registro_examenes"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", "eda_id", name="uq_reg_examen"),
    )

    id               = db.Column(db.Integer, primary_key=True)
    student_id       = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    course_id        = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    eda_id           = db.Column(db.Integer, db.ForeignKey("edas.id",    ondelete="CASCADE"), nullable=False)
    examen_bimestral = db.Column(db.Integer, nullable=True)   # 0-20

    def __repr__(self):
        return f"<RegistroExamen st={self.student_id} c={self.course_id} eda={self.eda_id} ex={self.examen_bimestral}>"


class Behavior(db.Model):
    __tablename__ = "behavior"
    __table_args__ = (
        db.UniqueConstraint("student_id", "indicador", "eda_id", name="uq_behavior_eda"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    indicador = db.Column(db.String(80), nullable=False)
    eda_id = db.Column(db.Integer, db.ForeignKey("edas.id", ondelete="CASCADE"), nullable=False)
    # Nota numérica 0-20
    calificacion = db.Column(db.Integer, nullable=True)

    eda = db.relationship("EDA", foreign_keys=[eda_id], lazy="joined")

    @property
    def qualitative_grade(self):
        """Convierte nota numérica a escala cualitativa: AD/A/B/C."""
        v = self.calificacion
        if v is None:
            return None
        if v >= 18:
            return "AD"
        if v >= 15:
            return "A"
        if v >= 11:
            return "B"
        return "C"

    def __repr__(self):
        return f"<Behavior st={self.student_id} {self.indicador} eda={self.eda_id}: {self.calificacion}>"


class ParentResponsibility(db.Model):
    __tablename__ = "parent_responsibility"
    __table_args__ = (
        db.UniqueConstraint("student_id", "indicador", "term_id", name="uq_parent_resp"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    indicador = db.Column(db.String(80), nullable=False)
    term_id = db.Column(db.Integer, db.ForeignKey("terms.id", ondelete="CASCADE"), nullable=False)
    calificacion = db.Column(db.Integer, nullable=True)

    term = db.relationship("Term", foreign_keys=[term_id], lazy="joined")

    @property
    def qualitative_grade(self):
        v = self.calificacion
        if v is None:
            return None
        if v >= 18:
            return "AD"
        if v >= 15:
            return "A"
        if v >= 11:
            return "B"
        return "C"

    def __repr__(self):
        return f"<ParentResponsibility st={self.student_id} {self.indicador} term={self.term_id}: {self.calificacion}>"


class RegistroHeaderConfig(db.Model):
    """Nombres personalizados para las columnas del Registro Auxiliar por curso."""
    __tablename__ = "registro_header_config"
    __table_args__ = (
        db.UniqueConstraint("course_id", "field_name", name="uq_header_config"),
    )

    id           = db.Column(db.Integer, primary_key=True)
    course_id    = db.Column(db.Integer, db.ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    field_name   = db.Column(db.String(30), nullable=False)   # tarea, intervencion, fast_test, ...
    display_name = db.Column(db.String(60), nullable=False)

    def __repr__(self):
        return f"<RegistroHeaderConfig course={self.course_id} {self.field_name}={self.display_name}>"
