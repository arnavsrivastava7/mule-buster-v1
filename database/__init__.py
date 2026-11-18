"""SQLite storage for Mule Buster records, accounts, and fraud alerts."""

from database.db import get_connection, init_db, connect, DB_PATH

MODULE_NAME = "Database"
STATUS = "ready"

__all__ = ["MODULE_NAME", "STATUS", "get_connection", "init_db", "connect", "DB_PATH"]
