"""SQLite database engine for Mule Buster.

Provides real persistent storage for simulated accounts, transactions,
fraud alerts, investigation cases, and audit logs.
"""

import sqlite3
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "database" / "mule_buster.db"
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"

STATUS = "ready"
MODULE_NAME = "Database"


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Return an active connection to the SQLite database with Row factory."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize database tables from schema.sql."""
    conn = get_connection(db_path)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()


def connect():
    """Scaffold compatibility function for placeholder checks."""
    return {
        "ready": False,
        "message": "Use get_connection() and init_db() for active database operations.",
        "planned_path": str(DB_PATH),
    }


__all__ = ["get_connection", "init_db", "connect", "DB_PATH", "STATUS", "MODULE_NAME"]
