from functools import wraps
from flask import abort
from flask_login import current_user


def role_required(*roles):
    """Permite acceso solo a los roles especificados. ADMIN siempre tiene acceso total."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.is_active:
                abort(403)
            # ADMIN bypassa todo
            if current_user.role.value == "ADMIN":
                return f(*args, **kwargs)
            if current_user.role.value not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
