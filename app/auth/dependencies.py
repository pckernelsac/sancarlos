"""
Dependencias de autenticación para FastAPI.
Reemplaza Flask-Login y el decorador role_required.
"""
from fastapi import Request, HTTPException
from app.database import db
from app.models.user import User


class AnonymousUser:
    """Usuario anónimo (no autenticado) — imita la interfaz de User."""
    is_authenticated = False
    is_active = False
    id = None
    username = None
    full_name = "Anónimo"
    role = None

    def has_role(self, *roles):
        return False

    def can_grade_course(self, course_id):
        return False


_anonymous = AnonymousUser()


def get_current_user(request: Request) -> User | AnonymousUser:
    """Obtiene el usuario actual de la sesión. No lanza excepción si no hay sesión."""
    user_id = request.session.get("user_id")
    if not user_id:
        return _anonymous
    user = db.session.get(User, int(user_id))
    if not user or not user.is_active:
        return _anonymous
    return user


def require_login(request: Request) -> User:
    """Dependencia que requiere autenticación. Redirige a login si no está autenticado."""
    user = get_current_user(request)
    if not user.is_authenticated:
        from fastapi.responses import RedirectResponse
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    return user


def require_role(*roles):
    """Factory de dependencias que requiere roles específicos. ADMIN siempre tiene acceso."""
    def dependency(request: Request) -> User:
        user = require_login(request)
        if user.role.value == "ADMIN":
            return user
        if user.role.value not in roles:
            raise HTTPException(status_code=403, detail="No tienes permiso para acceder a esta página.")
        return user
    return dependency
