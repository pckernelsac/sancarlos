#!/bin/bash
# =============================================================
#  Script de despliegue — Colegio San Carlos
#  Ejecutar desde SSH en cPanel:
#    bash /home/najmhqti/colegiosancarlos/deploy.sh
# =============================================================

set -e

PROJECT_DIR="/home/najmhqti/colegiosancarlos"
VENV_ACTIVATE="/home/najmhqti/virtualenv/colegiosancarlos/3.12/bin/activate"

echo "========================================="
echo "  Colegio San Carlos — Deploy"
echo "========================================="

# 1. Activar entorno virtual
echo "[1/6] Activando entorno virtual..."
source "$VENV_ACTIVATE"
python --version

# 2. Ir al directorio del proyecto
cd "$PROJECT_DIR"

# 3. Instalar/actualizar dependencias
echo "[2/6] Instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Configurar .env de producción (solo la primera vez)
if [ ! -f .env ]; then
    echo "[3/6] Creando .env desde .env.production..."
    cp .env.production .env
    echo "  ⚠  IMPORTANTE: Edita .env y cambia SECRET_KEY por una clave segura"
    echo "     nano /home/najmhqti/colegiosancarlos/.env"
else
    echo "[3/6] .env ya existe, se conserva."
fi

# 5. Crear directorio instance si no existe
mkdir -p instance

# 6. Ejecutar migraciones
echo "[4/6] Ejecutando migraciones de base de datos..."
if [ ! -d "migrations" ]; then
    flask db init
fi
flask db migrate -m "deploy" 2>/dev/null || true
flask db upgrade

# 7. Ejecutar seed (solo si la BD está vacía)
echo "[5/6] Verificando datos iniciales..."
python -c "
from app import create_app, db
from app.models.user import User
app = create_app()
with app.app_context():
    if User.query.count() == 0:
        print('  BD vacía, ejecutando seed...')
        exec(open('seed.py').read())
    else:
        print('  BD ya tiene datos, omitiendo seed.')
"

# 8. Reiniciar Passenger
echo "[6/6] Reiniciando aplicación..."
mkdir -p tmp
touch tmp/restart.txt

echo ""
echo "========================================="
echo "  Deploy completado exitosamente"
echo "========================================="
echo "  URL: https://colegiosancarlos.tudominio.com"
echo "  Logs: tail -f /home/najmhqti/logs/error.log"
echo "========================================="
