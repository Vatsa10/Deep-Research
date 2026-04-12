"""Research template API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.middleware import get_current_user
from ..db.templates import create_template, list_templates, get_template

router = APIRouter(prefix="/api/templates", tags=["templates"])


class CreateTemplateRequest(BaseModel):
    name: str = Field(description="Template name")
    query_pattern: str = Field(description="Query pattern with {topic} placeholder")
    description: str = Field(default="")
    depth: str = Field(default="standard")
    domain: str = Field(default="general")


@router.get("/public")
async def list_public_templates() -> list[dict]:
    """List built-in templates (no auth needed)."""
    return list_templates(user_id=None)


@router.get("")
async def list_user_templates(user: dict = Depends(get_current_user)) -> list[dict]:
    """List all templates available to the user (built-in + custom)."""
    return list_templates(user_id=user["id"])


@router.post("")
async def create_user_template(
    req: CreateTemplateRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """Save a research pattern as a reusable template."""
    template_id = create_template(
        user_id=user["id"],
        name=req.name,
        query_pattern=req.query_pattern,
        description=req.description,
        depth=req.depth,
        domain=req.domain,
    )
    return {"template_id": template_id}


@router.get("/{template_id}")
async def get_template_detail(template_id: str) -> dict:
    """Get a single template."""
    template = get_template(template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template
