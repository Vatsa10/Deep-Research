"""Turso/libSQL database client initialization."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import libsql_experimental as libsql

logger = logging.getLogger(__name__)

_db: libsql.Connection | None = None

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_db() -> libsql.Connection:
    """Get the database connection (singleton)."""
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


def init_db() -> libsql.Connection:
    """Initialize the Turso database connection and create tables.

    Reads TURSO_DATABASE_URL and TURSO_AUTH_TOKEN from environment.
    Falls back to a local SQLite file for development.
    """
    global _db

    url = os.environ.get("TURSO_DATABASE_URL", "")
    auth_token = os.environ.get("TURSO_AUTH_TOKEN", "")

    if url and auth_token:
        logger.info("Connecting to Turso: %s", url)
        _db = libsql.connect(
            database=url,
            auth_token=auth_token,
        )
    else:
        local_path = os.environ.get("LOCAL_DB_PATH", "data/deep_research.db")
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        logger.info("Using local SQLite: %s", local_path)
        _db = libsql.connect(database=local_path)

    # Run schema
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    for statement in schema_sql.split(";"):
        statement = statement.strip()
        if statement:
            _db.execute(statement)
    _db.commit()

    logger.info("Database initialized successfully")
    return _db


def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        _db.close()
        _db = None
