"""Research session CRUD operations."""

from __future__ import annotations

import json
from typing import Any

from .client import get_db


def create_session(
    session_id: str,
    user_id: str,
    query: str,
    depth: str,
    continued_from: str | None = None,
    template_id: str | None = None,
) -> None:
    """Create a new research session record."""
    db = get_db()
    db.execute(
        """INSERT INTO sessions (id, user_id, query, depth, status, continued_from, template_id)
        VALUES (?, ?, ?, ?, 'running', ?, ?)""",
        (session_id, user_id, query, depth, continued_from, template_id),
    )
    db.commit()


def update_session_result(session_id: str, result: dict[str, Any]) -> None:
    """Update a session with completed research results."""
    db = get_db()
    db.execute(
        """UPDATE sessions SET
            status = 'completed',
            report = ?,
            distilled_summary = ?,
            validation_json = ?,
            fact_check_json = ?,
            reasoning_trace_json = ?,
            dag_trace_json = ?,
            iterations = ?,
            completed_at = datetime('now')
        WHERE id = ?""",
        (
            result.get("report", ""),
            result.get("distilled_summary", ""),
            json.dumps(result.get("validation", {})),
            json.dumps(result.get("fact_check", {})),
            json.dumps(result.get("reasoning_trace", [])),
            json.dumps(result.get("dag_trace", {})),
            result.get("iterations", 0),
            session_id,
        ),
    )
    db.commit()


def update_session_failed(session_id: str, error: str) -> None:
    """Mark a session as failed."""
    db = get_db()
    db.execute(
        "UPDATE sessions SET status = 'failed', completed_at = datetime('now') WHERE id = ?",
        (session_id,),
    )
    db.commit()


def get_session(session_id: str) -> dict | None:
    """Get a session by ID."""
    db = get_db()
    row = db.execute(
        """SELECT id, user_id, query, depth, status, report, distilled_summary,
                  validation_json, fact_check_json, reasoning_trace_json,
                  dag_trace_json, iterations, continued_from, template_id,
                  created_at, completed_at
        FROM sessions WHERE id = ?""",
        (session_id,),
    ).fetchone()
    if not row:
        return None
    return _row_to_session(row)


def list_user_sessions(
    user_id: str, limit: int = 20, offset: int = 0
) -> list[dict]:
    """List sessions for a user, newest first."""
    db = get_db()
    rows = db.execute(
        """SELECT id, user_id, query, depth, status, report, distilled_summary,
                  validation_json, fact_check_json, reasoning_trace_json,
                  dag_trace_json, iterations, continued_from, template_id,
                  created_at, completed_at
        FROM sessions WHERE user_id = ?
        ORDER BY created_at DESC LIMIT ? OFFSET ?""",
        (user_id, limit, offset),
    ).fetchall()
    return [_row_to_session(row) for row in rows]


def _row_to_session(row: tuple) -> dict:
    """Convert a database row to a session dict."""
    return {
        "id": row[0],
        "user_id": row[1],
        "query": row[2],
        "depth": row[3],
        "status": row[4],
        "report": row[5],
        "distilled_summary": row[6],
        "validation": json.loads(row[7]) if row[7] else {},
        "fact_check": json.loads(row[8]) if row[8] else {},
        "reasoning_trace": json.loads(row[9]) if row[9] else [],
        "dag_trace": json.loads(row[10]) if row[10] else {},
        "iterations": row[11] or 0,
        "continued_from": row[12],
        "template_id": row[13],
        "created_at": row[14],
        "completed_at": row[15],
    }
