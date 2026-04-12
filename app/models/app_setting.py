"""Configuración clave-valor persistente (flags y ajustes del sistema)."""
from app.database import db


class AppSetting(db.Model):
    __tablename__ = "app_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False, index=True)
    value = db.Column(db.String(256), nullable=False)

    def __repr__(self):
        return f"<AppSetting {self.key}={self.value!r}>"
