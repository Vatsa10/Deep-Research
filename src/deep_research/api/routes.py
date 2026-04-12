"""API routes for the deep research service."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..pipeline.research_pipeline import run_research
from .sse import sse_manager, format_sse_event

router = APIRouter(prefix="/api")

# In-memory session storage (MVP)
_sessions: dict[str, dict[str, Any]] = {}


class ResearchRequest(BaseModel):
    query: str = Field(description="The research query")
    depth: str = Field(
        default="standard",
        description="Research depth: quick, standard, or deep",
    )


class ResearchStartResponse(BaseModel):
    session_id: str


@router.post("/research", response_model=ResearchStartResponse)
async def start_research(req: ResearchRequest) -> ResearchStartResponse:
    """Start a new research task. Returns a session_id for SSE streaming."""
    if req.depth not in ("quick", "standard", "deep"):
        raise HTTPException(status_code=400, detail="Invalid depth. Use: quick, standard, deep")

    session_id = str(uuid.uuid4())
    queue = sse_manager.create_session(session_id)

    _sessions[session_id] = {
        "query": req.query,
        "depth": req.depth,
        "status": "running",
        "result": None,
    }

    # Launch research in background
    asyncio.create_task(
        _run_research_task(session_id, req.query, req.depth)
    )

    return ResearchStartResponse(session_id=session_id)


async def _run_research_task(
    session_id: str, query: str, depth: str
) -> None:
    """Background task that runs the research pipeline."""

    async def on_progress(event_type: str, data: dict) -> None:
        await sse_manager.send_event(session_id, event_type, data)

    try:
        result = await run_research(
            query=query,
            depth=depth,
            on_progress=on_progress,
        )
        _sessions[session_id]["status"] = "completed"
        _sessions[session_id]["result"] = result
        await sse_manager.send_done(session_id, {
            "report": result["report"],
            "iterations": result["iterations"],
        })
    except Exception as exc:
        _sessions[session_id]["status"] = "failed"
        _sessions[session_id]["error"] = str(exc)
        await sse_manager.send_event(session_id, "error", {
            "message": str(exc),
        })


@router.get("/research/{session_id}/stream")
async def stream_progress(session_id: str) -> StreamingResponse:
    """SSE endpoint for real-time research progress updates."""
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
                # Send keepalive
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
async def get_result(session_id: str) -> dict:
    """Get the completed research result."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] == "running":
        return {"status": "running", "query": session["query"]}

    if session["status"] == "failed":
        raise HTTPException(status_code=500, detail=session.get("error", "Unknown error"))

    return {
        "status": "completed",
        "query": session["query"],
        "result": session["result"],
    }


@router.get("/history")
async def list_history() -> list[dict]:
    """List past research sessions."""
    return [
        {
            "session_id": sid,
            "query": data["query"],
            "depth": data["depth"],
            "status": data["status"],
        }
        for sid, data in _sessions.items()
    ]
