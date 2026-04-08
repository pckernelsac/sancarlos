# -*- coding: utf-8 -*-
"""
Copia todos los datos de un archivo SQLite a una base PostgreSQL vacía
(misma estructura que define la app).

Requisitos: PostgreSQL creado y vacío (o sin tablas). La URL de destino debe
apuntar a la BD PostgreSQL (misma que usará la aplicación).

Uso (PowerShell):
  $env:SQLITE_SOURCE="sqlite:///D:/ruta/sancarlos.db"
  $env:DATABASE_URL="postgresql+psycopg2://usuario:clave@127.0.0.1:5432/sancarlos"
  python scripts/migrate_sqlite_to_postgres.py

Variables:
  SQLITE_SOURCE — URL SQLite (por defecto sqlite:///sancarlos.db relativo al cwd)
  DATABASE_URL  — URL PostgreSQL (obligatoria si no está en .env)
"""
from __future__ import annotations

import os
import sys

# Raíz del proyecto (padre de scripts/)
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))

from sqlalchemy import create_engine, insert, inspect, select, text

from app.database import Base, db
import app.models  # noqa: F401 — registra tablas en Base.metadata
from config.settings import _normalize_database_url, get_config


def _reset_serial(conn, table_name: str, pk_name: str) -> None:
    r = conn.execute(
        text(
            "SELECT COALESCE(MAX(" + pk_name + "), 0) FROM " + table_name
        )
    ).scalar()
    if r is None or r < 1:
        return
    seq = conn.execute(
        text("SELECT pg_get_serial_sequence(:t, :c)"),
        {"t": table_name, "c": pk_name},
    ).scalar()
    if not seq:
        return
    conn.execute(text("SELECT setval(:seq, :mx, true)"), {"seq": seq, "mx": r})


def main() -> None:
    sqlite_url = os.environ.get("SQLITE_SOURCE", "sqlite:///sancarlos.db")
    cfg = get_config()
    pg_url = _normalize_database_url(os.environ.get("DATABASE_URL") or cfg.DATABASE_URL)
    if not pg_url.startswith("postgresql"):
        print("ERROR: DATABASE_URL debe ser una URL PostgreSQL.", file=sys.stderr)
        sys.exit(1)

    src = create_engine(
        sqlite_url,
        connect_args={"check_same_thread": False},
    )

    db.init(pg_url)
    insp = inspect(db.engine)
    if insp.has_table("users"):
        with db.engine.connect() as c:
            n = c.execute(text("SELECT COUNT(*) FROM users")).scalar()
        if n and n > 0:
            print(
                "ERROR: La base PostgreSQL ya tiene datos en 'users'. "
                "Vacía la BD o usa otra DATABASE_URL antes de migrar.",
                file=sys.stderr,
            )
            sys.exit(1)

    db.create_all()

    tables = list(Base.metadata.sorted_tables)
    with src.connect() as sconn, db.engine.begin() as dconn:
        for table in tables:
            rows = sconn.execute(select(table)).mappings().all()
            if not rows:
                continue
            dconn.execute(insert(table), [dict(r) for r in rows])
            print(f"  Copiados {len(rows)} filas → {table.name}")

        for table in tables:
            pks = list(table.primary_key.columns)
            if len(pks) != 1:
                continue
            col = pks[0]
            if col.autoincrement is False:
                continue
            _reset_serial(dconn, table.name, col.name)

    print("Migración SQLite → PostgreSQL completada.")


if __name__ == "__main__":
    main()
