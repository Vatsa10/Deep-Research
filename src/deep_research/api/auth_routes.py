"""Authentication API routes: register, login, refresh, me."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from ..auth.passwords import hash_password, verify_password
from ..auth.jwt import create_access_token, create_refresh_token
from ..auth.middleware import get_current_user
from ..db.users import (
    create_user,
    get_user_by_email,
    store_refresh_token,
    get_refresh_token,
    delete_refresh_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str = Field(description="User email")
    password: str = Field(min_length=6, description="Password (min 6 chars)")
    name: str = Field(default="", description="Display name")


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict


@router.post("/register", response_model=AuthResponse)
async def register(req: RegisterRequest) -> AuthResponse:
    """Create a new account."""
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    hashed = hash_password(req.password)
    user = create_user(email=req.email, password_hash=hashed, name=req.name)

    access_token = create_access_token(user["id"])
    refresh_tok, refresh_exp = create_refresh_token()
    store_refresh_token(refresh_tok, user["id"], refresh_exp)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_tok,
        user={"id": user["id"], "email": user["email"], "name": user["name"]},
    )


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest) -> AuthResponse:
    """Login with email and password."""
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(user["id"])
    refresh_tok, refresh_exp = create_refresh_token()
    store_refresh_token(refresh_tok, user["id"], refresh_exp)

    return AuthResponse(
        access_token=access_token,
        refresh_token=refresh_tok,
        user={"id": user["id"], "email": user["email"], "name": user["name"]},
    )


@router.post("/refresh")
async def refresh(req: RefreshRequest) -> dict:
    """Exchange a refresh token for a new access token."""
    stored = get_refresh_token(req.refresh_token)
    if not stored:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if datetime.fromisoformat(stored["expires_at"]) < datetime.now(timezone.utc):
        delete_refresh_token(req.refresh_token)
        raise HTTPException(status_code=401, detail="Refresh token expired")

    # Rotate: delete old, create new
    delete_refresh_token(req.refresh_token)
    new_access = create_access_token(stored["user_id"])
    new_refresh, new_exp = create_refresh_token()
    store_refresh_token(new_refresh, stored["user_id"], new_exp)

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
    }


@router.get("/me")
async def me(user: dict = Depends(get_current_user)) -> dict:
    """Get current user info."""
    return {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
    }
