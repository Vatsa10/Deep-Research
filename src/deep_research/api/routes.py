"""Core research API routes with DB persistence and auth."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from ..auth.middleware import get_current_user, get_optional_user
from ..db.sessions import (
    create_session,
    update_session_result,
    update_session_failed,
    get_session,
    list_user_sessions,
)
from ..pipeline.research_pipeline import run_research
from ..vector.memory import store_research_memory, search_similar_research
from .sse import sse_manager, format_sse_event

router = APIRouter(prefix="/api", tags=["research"])


class ResearchRequest(BaseModel):
    query: str = Field(description="The research query")
    depth: str = Field(default="standard")
    template_id: str | None = Field(default=None)


class ResearchStartResponse(BaseModel):
    session_id: str


@router.post("/research", response_model=ResearchStartResponse)
async def start_research(
    req: ResearchRequest,
    user: dict = Depends(get_current_user),
) -> ResearchStartResponse:
    """Start a new research task. Persists to database."""
    if req.depth not in ("quick", "standard", "deep"):
        raise HTTPException(status_code=400, detail="Invalid depth")

    session_id = str(uuid.uuid4())
    sse_manager.create_session(session_id)

    # Persist to Turso
    create_session(
        session_id=session_id,
        user_id=user["id"],
        query=req.query,
        depth=req.depth,
        template_id=req.template_id,
    )

    asyncio.create_task(
        _run_research_task(session_id, user["id"], req.query, req.depth)
    )

    return ResearchStartResponse(session_id=session_id)


async def _run_research_task(
    session_id: str, user_id: str, query: str, depth: str
) -> None:
    """Background task: run pipeline, persist results to DB + Qdrant."""

    async def on_progress(event_type: str, data: dict) -> None:
        await sse_manager.send_event(session_id, event_type, data)

    try:
        result = await run_research(
            query=query,
            depth=depth,
            on_progress=on_progress,
        )

        # Persist to Turso
        update_session_result(session_id, result)

        # Store in Qdrant for semantic search (non-blocking, non-critical)
        try:
            plan = result.get("validation", {})
            await store_research_memory(
                session_id=session_id,
                user_id=user_id,
                query=query,
                distilled_summary=result.get("distilled_summary", ""),
                domain=plan.get("domain", "general"),
                query_type=plan.get("query_type", "exploratory"),
            )
        except Exception:
            pass  # Vector store is optional

        await sse_manager.send_done(session_id, {
            "report": result["report"],
            "distilled": result.get("distilled_summary", ""),
            "iterations": result["iterations"],
            "fact_check": result.get("fact_check", {}),
        })

    except Exception as exc:
        update_session_failed(session_id, str(exc))
        await sse_manager.send_event(session_id, "error", {"message": str(exc)})


@router.get("/research/{session_id}/stream")
async def stream_progress(session_id: str) -> StreamingResponse:
    """SSE endpoint for real-time research progress."""
    queue = sse_manager.get_queue(session_id)
    if not queue:
        raise HTTPException(status_code=404, detail="Session not found")

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=300.0)
                yield format_sse_event(event)
                if event.get("type") in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                yield format_sse_event({"type": "keepalive"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/research/{session_id}")
async def get_result(
    session_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Get completed research result from database."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your session")

    return {
        "status": session["status"],
        "query": session["query"],
        "report": session.get("report", ""),
        "distilled_summary": session.get("distilled_summary", ""),
        "validation": session.get("validation", {}),
        "fact_check": session.get("fact_check", {}),
        "reasoning_trace": session.get("reasoning_trace", []),
        "iterations": session.get("iterations", 0),
        "dag_trace": session.get("dag_trace", {}),
        "created_at": session.get("created_at"),
        "completed_at": session.get("completed_at"),
    }


@router.get("/research/{session_id}/trace")
async def get_reasoning_trace(
    session_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Get the reasoning trace for a completed session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your session")

    return {
        "session_id": session_id,
        "query": session["query"],
        "validation": session.get("validation", {}),
        "reasoning_trace": session.get("reasoning_trace", []),
        "fact_check": session.get("fact_check", {}),
        "dag_trace": session.get("dag_trace", {}),
    }


@router.get("/research/{session_id}/export")
async def export_research(
    session_id: str,
    user: dict = Depends(get_current_user),
) -> JSONResponse:
    """Export a complete research artifact as JSON."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your session")
    if session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Research not yet complete")

    artifact = {
        "version": "1.0",
        "session_id": session_id,
        "query": session["query"],
        "depth": session["depth"],
        "report": session.get("report", ""),
        "distilled_summary": session.get("distilled_summary", ""),
        "validation": session.get("validation", {}),
        "fact_check": session.get("fact_check", {}),
        "reasoning_trace": session.get("reasoning_trace", []),
        "iterations": session.get("iterations", 0),
        "dag_trace": session.get("dag_trace", {}),
        "created_at": session.get("created_at"),
        "completed_at": session.get("completed_at"),
    }

    return JSONResponse(
        content=artifact,
        headers={
            "Content-Disposition": f'attachment; filename="research-{session_id[:8]}.json"',
        },
    )


@router.post("/research/{session_id}/continue", response_model=ResearchStartResponse)
async def continue_research(
    session_id: str,
    req: ResearchRequest,
    user: dict = Depends(get_current_user),
) -> ResearchStartResponse:
    """Continue a previous research session with a follow-up question."""
    original = get_session(session_id)
    if not original:
        raise HTTPException(status_code=404, detail="Session not found")
    if original["user_id"] != user["id"]:
        raise HTTPException(status_code=403, detail="Not your session")
    if original["status"] != "completed":
        raise HTTPException(status_code=400, detail="Original research not yet complete")

    # Build enriched query with previous context
    enriched_query = (
        f"Previous research on: {original['query']}\n\n"
        f"Key findings:\n{(original.get('report') or '')[:2000]}\n\n"
        f"Follow-up question: {req.query}"
    )

    new_session_id = str(uuid.uuid4())
    sse_manager.create_session(new_session_id)

    create_session(
        session_id=new_session_id,
        user_id=user["id"],
        query=req.query,
        depth=req.depth,
        continued_from=session_id,
    )

    asyncio.create_task(
        _run_research_task(new_session_id, user["id"], enriched_query, req.depth)
    )

    return ResearchStartResponse(session_id=new_session_id)


@router.get("/history")
async def list_history(
    user: dict = Depends(get_current_user),
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict:
    """List user's research history with pagination."""
    sessions = list_user_sessions(user["id"], limit=limit, offset=offset)
    return {
        "sessions": [
            {
                "session_id": s["id"],
                "query": s["query"],
                "depth": s["depth"],
                "status": s["status"],
                "created_at": s["created_at"],
                "completed_at": s["completed_at"],
                "continued_from": s["continued_from"],
            }
            for s in sessions
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/search")
async def semantic_search(
    q: str = Query(description="Search query"),
    user: dict = Depends(get_current_user),
    top_k: int = Query(default=5, le=20),
) -> dict:
    """Semantic search across past research using Qdrant."""
    results = await search_similar_research(
        query=q,
        user_id=user["id"],
        top_k=top_k,
    )
    return {"query": q, "results": results}
