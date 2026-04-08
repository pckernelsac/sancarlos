from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo


class LoginForm(FlaskForm):
    username = StringField("Usuario", validators=[DataRequired(), Length(3, 64)])
    password = PasswordField("Contraseña", validators=[DataRequired()])
    remember_me = BooleanField("Mantener sesión")
    submit = SubmitField("Ingresar")


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField("Contraseña actual", validators=[DataRequired()])
    new_password = PasswordField("Nueva contraseña", validators=[DataRequired(), Length(min=6, message="Mínimo 6 caracteres.")])
    confirm_password = PasswordField("Confirmar nueva contraseña",
                                     validators=[DataRequired(), EqualTo("new_password", message="Las contraseñas no coinciden.")])
    submit = SubmitField("Cambiar contraseña")
