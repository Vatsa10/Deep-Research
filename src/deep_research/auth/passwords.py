"""Password hashing with bcrypt (direct, no passlib)."""

from __future__ import annotations

import bcrypt


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    pwd_bytes = password.encode("utf-8")[:72]  # bcrypt max 72 bytes
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain.encode("utf-8")[:72],
        hashed.encode("utf-8"),
    )
