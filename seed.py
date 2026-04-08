# -*- coding: utf-8 -*-
"""
seed.py — Crea datos iniciales: admin, bimestres y cursos base.
Ejecutar UNA sola vez después de crear las tablas.
"""
import sys
import datetime

# Fuerza UTF-8 en la salida de consola (Windows cp1252 no soporta algunos caracteres)
if sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.database import db
from config.settings import get_config

# Inicializar la BD
cfg = get_config()
db.init(cfg.DATABASE_URL)

# Importar modelos (registra las tablas en Base.metadata)
import app.models  # noqa

from app.models.user import User, RoleEnum
from app.models.academic import Course, Term

# Crear tablas
db.create_all()

# -- Usuario ADMIN --------------------------------------------------------
if not User.query.filter_by(username="admin").first():
    admin = User(username="admin", full_name="Administrador", role=RoleEnum.ADMIN, is_active=True)
    admin.set_password("admin1234")
    db.session.add(admin)
    print("[OK] Usuario admin creado (password: admin1234)")

# -- Usuario DOCENTE ------------------------------------------------------
if not User.query.filter_by(username="docente1").first():
    doc = User(username="docente1", full_name="Maria Garcia", role=RoleEnum.DOCENTE, is_active=True)
    doc.set_password("docente1234")
    db.session.add(doc)
    print("[OK] Usuario docente1 creado (password: docente1234)")

# -- Usuario AUXILIAR -----------------------------------------------------
if not User.query.filter_by(username="auxiliar1").first():
    aux = User(username="auxiliar1", full_name="Juan Perez", role=RoleEnum.AUXILIAR, is_active=True)
    aux.set_password("auxiliar1234")
    db.session.add(aux)
    print("[OK] Usuario auxiliar1 creado (password: auxiliar1234)")

# -- Bimestres ------------------------------------------------------------
anio = datetime.date.today().year
for orden, nombre in enumerate(["I Bimestre", "II Bimestre", "III Bimestre", "IV Bimestre"], 1):
    if not Term.query.filter_by(nombre=nombre, anio=anio).first():
        db.session.add(Term(nombre=nombre, orden=orden, anio=anio))
print(f"[OK] Bimestres {anio} configurados")

# -- Cursos INICIAL --------------------------------------------------------
cursos_inicial = [
    ("COMUNICACIÓN",          "Comunicación"),
    ("RAZ. VERBAL",           "Comunicación"),
    ("PLAN LECTOR",           "Comunicación"),
    ("MATEMÁTICA",            "Matemática"),
    ("RAZ. MATEMÁTICO",       "Matemática"),
    ("PERSONAL SOCIAL",       "Personal Social"),
    ("CIENCIA Y TECNOLOGÍA",  "Ciencia y Tecnología"),
    ("EDUCACIÓN RELIGIOSA",   "Educación Religiosa"),
    ("ED. FISICA",            "Educación Física"),
    ("ARTE Y CULTURA",        "Arte y Cultura"),
    ("INGLÉS",                "Idioma Inglés"),
]
for nombre, area in cursos_inicial:
    if not Course.query.filter_by(nombre=nombre, nivel="INICIAL", grado=None).first():
        db.session.add(Course(nombre=nombre, area=area, nivel="INICIAL", grado=None))
print("[OK] Cursos INICIAL creados/verificados (11 cursos)")

# -- Cursos PRIMARIA (por grado) -------------------------------------------
# Cursos comunes a TODOS los grados de primaria (1° a 6°)
cursos_primaria_comunes = [
    ("ARITMÉTICA",           "Matemática"),
    ("GEOMETRÍA",            "Matemática"),
    ("RAZ. MATEMÁTICO",      "Matemática"),
    ("COMUNICACIÓN",         "Comunicación"),
    ("RAZ. VERBAL",          "Comunicación"),
    ("PLAN LECTOR",          "Comunicación"),
    ("PERSONAL SOCIAL",      "Personal Social"),
    ("EDUCACIÓN RELIGIOSA",  "Educación Religiosa"),
    ("INFORMÁTICA",          "Informática"),
    ("EDUCACIÓN FÍSICA",     "Educación Física"),
    ("INGLÉS",               "Idioma Inglés"),
    ("ARTE Y CULTURA",       "Arte y Cultura"),
]

# Cursos específicos por grado
cursos_primaria_por_grado = {
    # 1° y 2°: comunes + ESTADÍSTICA, CIENCIA Y TECNOLOGÍA
    "1": [
        ("ESTADÍSTICA",          "Matemática"),
        ("CIENCIA Y TECNOLOGÍA", "Ciencia y Tecnología"),
    ],
    "2": [
        ("ESTADÍSTICA",          "Matemática"),
        ("CIENCIA Y TECNOLOGÍA", "Ciencia y Tecnología"),
    ],
    # 3°: comunes + ÁLGEBRA
    "3": [
        ("ÁLGEBRA",              "Matemática"),
    ],
    # 4°: comunes + ÁLGEBRA, ESTADÍSTICA, CIENCIA Y TECNOLOGÍA
    "4": [
        ("ÁLGEBRA",              "Matemática"),
        ("ESTADÍSTICA",          "Matemática"),
        ("CIENCIA Y TECNOLOGÍA", "Ciencia y Tecnología"),
    ],
    # 5°: comunes + ÁLGEBRA, ESTADÍSTICA, METODOLOGÍA, BIOLOGÍA
    "5": [
        ("ÁLGEBRA",              "Matemática"),
        ("ESTADÍSTICA",          "Matemática"),
        ("METODOLOGÍA",          "Ciencia y Tecnología"),
        ("BIOLOGÍA",             "Ciencia y Tecnología"),
    ],
    # 6°: comunes + ÁLGEBRA, ESTADÍSTICA, METODOLOGÍA, BIOLOGÍA, FÍSICA, QUÍMICA
    "6": [
        ("ÁLGEBRA",              "Matemática"),
        ("ESTADÍSTICA",          "Matemática"),
        ("METODOLOGÍA",          "Ciencia y Tecnología"),
        ("BIOLOGÍA",             "Ciencia y Tecnología"),
        ("FÍSICA",               "Ciencia y Tecnología"),
        ("QUÍMICA",              "Ciencia y Tecnología"),
    ],
}

total_primaria = 0
for grado in ["1", "2", "3", "4", "5", "6"]:
    todos = cursos_primaria_comunes + cursos_primaria_por_grado[grado]
    for nombre, area in todos:
        if not Course.query.filter_by(nombre=nombre, nivel="PRIMARIA", grado=grado).first():
            db.session.add(Course(nombre=nombre, area=area, nivel="PRIMARIA", grado=grado))
    total_primaria += len(todos)
    print(f"  {grado}° primaria: {len(todos)} cursos")
print(f"[OK] Cursos PRIMARIA creados/verificados ({total_primaria} registros total)")

# -- Cursos SECUNDARIA -----------------------------------------------------
cursos_secundaria = [
    ("ARITMÉTICA",         "Matemática"),
    ("ÁLGEBRA",            "Matemática"),
    ("GEOMETRÍA",          "Matemática"),
    ("TRIGONOMETRÍA",      "Matemática"),
    ("RAZ. MATEMÁTICO",    "Matemática"),
    ("ESTADÍSTICA",        "Matemática"),
    ("LENGUAJE",           "Comunicación"),
    ("LITERATURA",         "Comunicación"),
    ("RAZ. VERBAL",        "Comunicación"),
    ("EDUCACIÓN CIVICA",   "DPCC"),
    ("FILOSOFÍA",          "DPCC"),
    ("PSICOLOGÍA",         "DPCC"),
    ("HISTORIA DEL PERÚ",  "Ciencias Sociales"),
    ("HISTORIA UNIVERSAL", "Ciencias Sociales"),
    ("GEOGRAFÍA",          "Ciencias Sociales"),
    ("ECONOMÍA",           "Ciencias Sociales"),
    ("FÍSICA",             "Ciencia y Tecnología"),
    ("QUÍMICA",            "Ciencia y Tecnología"),
    ("BIOLOGÍA",           "Ciencia y Tecnología"),
    ("ECOLOGÍA",           "Ciencia y Tecnología"),
    ("EDUCACIÓN FÍSICA",   "Educación Física"),
    ("INGLÉS",             "Idioma Inglés"),
    ("ROBÓTICA",           "Robótica"),
    ("ITALIANO",           "Idioma Italiano"),
]
for nombre, area in cursos_secundaria:
    existing = Course.query.filter_by(nombre=nombre, nivel="SECUNDARIA", grado=None).first()
    if existing:
        if existing.area != area:
            existing.area = area
    else:
        db.session.add(Course(nombre=nombre, area=area, nivel="SECUNDARIA", grado=None))
print("[OK] Cursos SECUNDARIA creados/verificados (24 cursos)")

db.session.commit()
print("\n[DONE] Seed completado exitosamente.")
