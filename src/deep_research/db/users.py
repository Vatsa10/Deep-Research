"""User CRUD operations."""

from __future__ import annotations

import uuid

from .client import get_db


def create_user(email: str, password_hash: str, name: str = "") -> dict:
    """Create a new user and return their record."""
    db = get_db()
    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, email, password_hash, name) VALUES (?, ?, ?, ?)",
        (user_id, email, password_hash, name),
    )
    db.commit()
    return {"id": user_id, "email": email, "name": name}


def get_user_by_email(email: str) -> dict | None:
    """Find a user by email."""
    db = get_db()
    row = db.execute(
        "SELECT id, email, password_hash, name, created_at FROM users WHERE email = ?",
        (email,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "email": row[1],
        "password_hash": row[2],
        "name": row[3],
        "created_at": row[4],
    }


def get_user_by_id(user_id: str) -> dict | None:
    """Find a user by ID."""
    db = get_db()
    row = db.execute(
        "SELECT id, email, name, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return None
    return {"id": row[0], "email": row[1], "name": row[2], "created_at": row[3]}


def store_refresh_token(token: str, user_id: str, expires_at: str) -> None:
    """Store a refresh token."""
    db = get_db()
    db.execute(
        "INSERT INTO refresh_tokens (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user_id, expires_at),
    )
    db.commit()


def get_refresh_token(token: str) -> dict | None:
    """Get a refresh token record."""
    db = get_db()
    row = db.execute(
        "SELECT token, user_id, expires_at FROM refresh_tokens WHERE token = ?",
        (token,),
    ).fetchone()
    if not row:
        return None
    return {"token": row[0], "user_id": row[1], "expires_at": row[2]}


def delete_refresh_token(token: str) -> None:
    """Delete a refresh token (on logout or refresh)."""
    db = get_db()
    db.execute("DELETE FROM refresh_tokens WHERE token = ?", (token,))
    db.commit()
