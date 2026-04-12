"""FastAPI authentication dependency."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from .jwt import verify_access_token
from ..db.users import get_user_by_id

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """FastAPI dependency that extracts and validates the JWT.

    Returns the user dict from the database.
    Raises 401 if the token is missing, invalid, or the user doesn't exist.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = verify_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict | None:
    """Like get_current_user but returns None instead of 401 for unauthenticated requests."""
    if credentials is None:
        return None
    try:
        payload = verify_access_token(credentials.credentials)
        user_id = payload.get("sub")
        if user_id:
            return get_user_by_id(user_id)
    except JWTError:
        pass
    return None
