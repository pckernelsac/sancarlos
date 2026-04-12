#!/usr/bin/env python3
"""
Crea todas las tablas en la base configurada (DATABASE_URL / .env).
Uso en Docker:
  docker compose exec <servicio> python scripts/init_db.py
O local:
  python scripts/init_db.py
Después, para datos demo (admin, cursos, etc.): python seed.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import get_config  # noqa: E402
from app.database import db  # noqa: E402


def main():
    db.init(get_config().DATABASE_URL)
    import app.models  # noqa: F401, E402
    db.ensure_schema()
    print("OK: esquema creado o verificado (tabla users presente).")


if __name__ == "__main__":
    main()
