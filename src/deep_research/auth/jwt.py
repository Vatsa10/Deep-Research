"""JWT token creation and verification."""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

ALGORITHM = "HS256"


def _get_secret() -> str:
    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise ValueError("JWT_SECRET environment variable not set")
    return secret


def create_access_token(user_id: str, expires_hours: int = 24) -> str:
    """Create a JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    payload = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, _get_secret(), algorithm=ALGORITHM)


def create_refresh_token() -> tuple[str, str]:
    """Create a refresh token. Returns (token, expires_at ISO string)."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    return token, expires_at


def verify_access_token(token: str) -> dict:
    """Verify a JWT access token. Returns the payload or raises.

    Returns:
        Dict with 'sub' (user_id) and 'exp'.

    Raises:
        JWTError: If the token is invalid or expired.
    """
    payload = jwt.decode(token, _get_secret(), algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise JWTError("Not an access token")
    return payload
