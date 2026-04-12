"""Database client using Turso HTTP API directly via httpx.

Uses Turso's /v2/pipeline HTTP endpoint — no WebSocket, no libsql-client.
Falls back to local SQLite only if TURSO_DATABASE_URL is not set.

Env vars:
    TURSO_DATABASE_URL: e.g. https://deep-research-vatsa.turso.io (use https://, not libsql://)
    TURSO_AUTH_TOKEN: your Turso database auth token
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

_db: "TursoHTTPClient | sqlite3.Connection | None" = None


class TursoHTTPClient:
    """Turso database client using the HTTP /v2/pipeline API.

    Exposes .execute() / .fetchone() / .fetchall() that match sqlite3 usage,
    so all CRUD modules work unchanged.
    """

    def __init__(self, url: str, auth_token: str) -> None:
        # Normalize URL: strip trailing slash, ensure https://
        url = url.rstrip("/")
        if url.startswith("libsql://"):
            url = url.replace("libsql://", "https://", 1)
        if not url.startswith("https://") and not url.startswith("http://"):
            url = f"https://{url}"
        self._url = f"{url}/v2/pipeline"
        self._auth_token = auth_token

    def execute(self, sql: str, params: tuple = ()) -> "TursoCursor":
        """Execute a SQL statement and return a cursor-like object."""
        args = [_convert_value(p) for p in params]
        body = {
            "requests": [
                {"type": "execute", "stmt": {"sql": sql, "args": args}},
                {"type": "close"},
            ]
        }
        resp = httpx.post(
            self._url,
            json=body,
            headers={
                "Authorization": f"Bearer {self._auth_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract rows from the response
        results = data.get("results", [])
        if results and results[0].get("type") == "ok":
            response_result = results[0]["response"]["result"]
            rows = _parse_rows(response_result)
            return TursoCursor(rows)

        # Check for error
        if results and results[0].get("type") == "error":
            error = results[0].get("error", {})
            raise RuntimeError(f"Turso error: {error.get('message', str(error))}")

        return TursoCursor([])

    def executescript(self, sql: str) -> None:
        """Execute multiple SQL statements."""
        requests = []
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                requests.append({"type": "execute", "stmt": {"sql": statement}})
        requests.append({"type": "close"})

        resp = httpx.post(
            self._url,
            json={"requests": requests},
            headers={
                "Authorization": f"Bearer {self._auth_token}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )
        resp.raise_for_status()

    def commit(self) -> None:
        pass  # Turso auto-commits

    def close(self) -> None:
        pass  # HTTP client is stateless


class TursoCursor:
    """Mimics sqlite3.Cursor for Turso results."""

    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows

    def fetchone(self) -> tuple | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[tuple]:
        return list(self._rows)


def _convert_value(val: Any) -> dict:
    """Convert a Python value to Turso's typed argument format."""
    if val is None:
        return {"type": "null", "value": None}
    if isinstance(val, int):
        return {"type": "integer", "value": str(val)}
    if isinstance(val, float):
        return {"type": "float", "value": val}
    return {"type": "text", "value": str(val)}


def _parse_rows(result: dict) -> list[tuple]:
    """Parse rows from Turso's response format into tuples."""
    rows = []
    for row in result.get("rows", []):
        parsed = []
        for cell in row:
            if cell.get("type") == "null":
                parsed.append(None)
            elif cell.get("type") == "integer":
                parsed.append(int(cell["value"]))
            elif cell.get("type") == "float":
                parsed.append(float(cell["value"]))
            else:
                parsed.append(cell.get("value", ""))
        rows.append(tuple(parsed))
    return rows


def get_db() -> TursoHTTPClient | sqlite3.Connection:
    """Get the database connection (singleton)."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


def init_db() -> TursoHTTPClient | sqlite3.Connection:
    """Initialize the database and create tables.

    If TURSO_DATABASE_URL is set → uses Turso HTTP API.
    Otherwise → falls back to local SQLite.
    """
    global _db

    turso_url = os.environ.get("TURSO_DATABASE_URL", "")
    turso_token = os.environ.get("TURSO_AUTH_TOKEN", "")
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    if turso_url and turso_token:
        logger.info("Connecting to Turso: %s", turso_url)
        _db = TursoHTTPClient(url=turso_url, auth_token=turso_token)

        # Run schema via executescript
        try:
            _db.executescript(schema_sql)
            logger.info("Turso database initialized")
        except Exception as exc:
            # Tables might already exist — that's fine
            logger.info("Schema init (may already exist): %s", exc)

        return _db
    else:
        db_path = os.environ.get("LOCAL_DB_PATH", "data/deep_research.db")
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

        logger.info("Using local SQLite: %s", db_path)
        _db = sqlite3.connect(db_path, check_same_thread=False)
        _db.execute("PRAGMA journal_mode=WAL")
        _db.execute("PRAGMA foreign_keys=ON")
        _db.executescript(schema_sql)
        _db.commit()

        logger.info("Local database initialized")
        return _db


def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db is not None:
        _db.close()
        _db = None
