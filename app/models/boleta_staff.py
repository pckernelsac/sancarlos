"""Nombres configurables para firmas en boletas (coordinadores y tutores por grado)."""
from app.database import db


class BoletaStaffConfig(db.Model):
    __tablename__ = "boleta_staff_config"

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(64), unique=True, nullable=False, index=True)
    nombre_completo = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f"<BoletaStaffConfig {self.clave}>"
