"""Share link CRUD operations."""

from __future__ import annotations

import secrets

from .client import get_db


def create_share_link(session_id: str, user_id: str, expires_at: str | None = None) -> str:
    """Create a shareable link for a research session. Returns the token."""
    db = get_db()

    # Check if a share link already exists for this session
    existing = db.execute(
        "SELECT token FROM share_links WHERE session_id = ? AND created_by = ?",
        (session_id, user_id),
    ).fetchone()
    if existing:
        return existing[0]

    token = secrets.token_urlsafe(16)
    db.execute(
        """INSERT INTO share_links (token, session_id, created_by, expires_at)
        VALUES (?, ?, ?, ?)""",
        (token, session_id, user_id, expires_at),
    )
    db.commit()
    return token


def get_share_link(token: str) -> dict | None:
    """Get a share link by token."""
    db = get_db()
    row = db.execute(
        """SELECT token, session_id, created_by, created_at, expires_at, view_count
        FROM share_links WHERE token = ?""",
        (token,),
    ).fetchone()
    if not row:
        return None
    return {
        "token": row[0],
        "session_id": row[1],
        "created_by": row[2],
        "created_at": row[3],
        "expires_at": row[4],
        "view_count": row[5],
    }


def increment_view_count(token: str) -> None:
    """Increment the view count for a share link."""
    db = get_db()
    db.execute(
        "UPDATE share_links SET view_count = view_count + 1 WHERE token = ?",
        (token,),
    )
    db.commit()
