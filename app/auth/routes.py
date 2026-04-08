from fastapi import APIRouter, Request, Depends, Form
from app.database import db
from app.models.user import User
from app.auth.dependencies import require_login
from app.security.csrf import ensure_csrf_token
from app.security.redirects import safe_next_url
from app.security.rate_limit import get_login_limiter, client_key
from app import render, flash, redirect_to

router = APIRouter(tags=["auth"])


@router.get("/login", name="auth.login")
async def login_page(request: Request):
    from app.auth.dependencies import get_current_user
    user = get_current_user(request)
    if user.is_authenticated:
        return redirect_to("/dashboard")
    return render(request, "auth/login.html")


@router.post("/login", name="auth.login_post")
async def login_submit(
    request: Request,
    username: str = Form(..., max_length=128),
    password: str = Form(..., max_length=256),
    remember_me: bool = Form(False),
):
    limiter = get_login_limiter()
    key = client_key(request)
    if limiter and limiter.is_blocked(key):
        flash(
            request,
            "Demasiados intentos fallidos. Espere unos minutos e intente de nuevo.",
            "danger",
        )
        return render(request, "auth/login.html")

    user = User.query.filter_by(username=username.strip()).first()
    if user and user.is_active and user.check_password(password):
        if limiter:
            limiter.reset(key)
        request.session.clear()
        request.session["user_id"] = user.id
        ensure_csrf_token(request)
        next_page = safe_next_url(request.query_params.get("next"))
        return redirect_to(next_page)

    if limiter:
        limiter.record_failure(key)
    flash(request, "Usuario o contraseña incorrectos.", "danger")
    return render(request, "auth/login.html")


@router.get("/logout", name="auth.logout")
async def logout(request: Request):
    """Invalida la sesión por completo (mitiga fijación de sesión en nuevos logins)."""
    request.session.clear()
    flash(request, "Sesión cerrada correctamente.", "info")
    return redirect_to("/auth/login")


@router.get("/change-password", name="auth.change_password")
async def change_password_page(request: Request, current_user: User = Depends(require_login)):
    return render(request, "auth/change_password.html")


@router.post("/change-password", name="auth.change_password_post")
async def change_password_submit(
    request: Request,
    current_password: str = Form(..., max_length=256),
    new_password: str = Form(..., max_length=256),
    confirm_password: str = Form(..., max_length=256),
    current_user: User = Depends(require_login),
):
    errors = {}
    if not current_user.check_password(current_password):
        errors["current_password"] = "La contraseña actual es incorrecta."
    if len(new_password) < 6:
        errors["new_password"] = "Mínimo 6 caracteres."
    if new_password != confirm_password:
        errors["confirm_password"] = "Las contraseñas no coinciden."

    if errors:
        return render(request, "auth/change_password.html", errors=errors)

    current_user.set_password(new_password)
    db.session.commit()
    flash(request, "Contraseña actualizada correctamente.", "success")
    return redirect_to("/dashboard")
