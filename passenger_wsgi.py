"""
Punto de entrada Phusion Passenger (cPanel).
Usa un adaptador ASGI → WSGI propio (wsgi_adapter.py) en vez de a2wsgi.
"""
import os
import sys
import datetime
import traceback

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(PROJECT_DIR, "startup_log.txt")


def _log(msg):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"[{datetime.datetime.now()}] {msg}\n")
    except Exception:
        pass


if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_DIR, ".env"))

# Fix DATABASE_URL relativa → absoluta
_db_url = os.environ.get("DATABASE_URL", "")
if _db_url.startswith("sqlite:///") and not _db_url.startswith("sqlite:////"):
    relative_path = _db_url.replace("sqlite:///", "")
    os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(PROJECT_DIR, relative_path)}"

_log(f"=== INICIO ===")
_log(f"PROJECT_DIR={PROJECT_DIR}")
_log(f"DATABASE_URL={os.environ.get('DATABASE_URL')}")

try:
    from wsgi_adapter import asgi_to_wsgi
    from app import create_app

    _asgi_app = create_app()
    application = asgi_to_wsgi(_asgi_app)
    _log("OK: application lista (wsgi_adapter)")
except Exception as e:
    _log(f"FALLO: {e}")
    _log(traceback.format_exc())
    raise

_log("=== passenger_wsgi listo ===")
