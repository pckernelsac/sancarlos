# Importar todos los modelos para que Base.metadata los registre
from app.models.user import User, RoleEnum, TeacherCourse  # noqa
from app.models.student import Student  # noqa
from app.models.boleta_staff import BoletaStaffConfig  # noqa
from app.models.academic import (  # noqa
    Course, Term, EDA, EdaGrade, EdaComment, Grade,
    Attendance, RegistroSemana, RegistroExamen,
    Behavior, ParentResponsibility, RegistroHeaderConfig,
)
