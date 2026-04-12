"""Share link API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..auth.middleware import get_current_user
from ..db.shares import create_share_link, get_share_link, increment_view_count
from ..db.sessions import get_session

router = APIRouter(prefix="/api", tags=["share"])


@router.post("/research/{session_id}/share")
async def share_research(
    session_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Generate a shareable link for a research session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your session")
    if session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Research not yet complete")

    token = create_share_link(session_id, user["id"])
    return {"share_token": token, "share_url": f"/shared/{token}"}


@router.get("/shared/{token}")
async def view_shared_research(token: str) -> dict:
    """View a shared research report. No authentication required."""
    share = get_share_link(token)
    if not share:
        raise HTTPException(status_code=404, detail="Share link not found")

    session = get_session(share["session_id"])
    if not session:
        raise HTTPException(status_code=404, detail="Research not found")

    increment_view_count(token)

    return {
        "query": session["query"],
        "report": session["report"],
        "distilled_summary": session["distilled_summary"],
        "fact_check": session["fact_check"],
        "iterations": session["iterations"],
        "created_at": session["created_at"],
        "view_count": share["view_count"] + 1,
    }
