"""API routes for the deep research service."""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
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
    sse_manager.create_session(session_id)

    _sessions[session_id] = {
        "query": req.query,
        "depth": req.depth,
        "status": "running",
        "result": None,
    }

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
            "distilled": result.get("distilled_summary", ""),
            "iterations": result["iterations"],
            "fact_check": result.get("fact_check", {}),
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
    """Get the completed research result with all metadata."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] == "running":
        return {"status": "running", "query": session["query"]}

    if session["status"] == "failed":
        raise HTTPException(status_code=500, detail=session.get("error", "Unknown error"))

    result = session["result"]
    return {
        "status": "completed",
        "query": session["query"],
        "report": result.get("report", ""),
        "distilled_summary": result.get("distilled_summary", ""),
        "validation": result.get("validation", {}),
        "fact_check": result.get("fact_check", {}),
        "reasoning_trace": result.get("reasoning_trace", []),
        "iterations": result.get("iterations", 0),
        "dag_trace": result.get("dag_trace", {}),
    }


@router.get("/research/{session_id}/trace")
async def get_reasoning_trace(session_id: str) -> dict:
    """Get the transparent reasoning trace for a completed research session."""
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Research not yet complete")

    result = session["result"]
    return {
        "session_id": session_id,
        "query": session["query"],
        "validation": result.get("validation", {}),
        "reasoning_trace": result.get("reasoning_trace", []),
        "fact_check": result.get("fact_check", {}),
        "dag_trace": result.get("dag_trace", {}),
    }


@router.get("/research/{session_id}/export")
async def export_research(session_id: str) -> JSONResponse:
    """Export a complete, self-contained research artifact as JSON.

    This is the "reproducibility" endpoint — everything needed to
    understand and verify the research is included.
    """
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] != "completed":
        raise HTTPException(status_code=400, detail="Research not yet complete")

    result = session["result"]
    artifact = {
        "version": "1.0",
        "session_id": session_id,
        "query": session["query"],
        "depth": session["depth"],
        "validation": result.get("validation", {}),
        "report": result.get("report", ""),
        "distilled_summary": result.get("distilled_summary", ""),
        "fact_check": result.get("fact_check", {}),
        "reasoning_trace": result.get("reasoning_trace", []),
        "iterations": result.get("iterations", 0),
        "dag_trace": result.get("dag_trace", {}),
    }

    return JSONResponse(
        content=artifact,
        headers={
            "Content-Disposition": f'attachment; filename="research-{session_id[:8]}.json"',
        },
    )


@router.post("/research/{session_id}/continue")
async def continue_research(session_id: str, req: ResearchRequest) -> ResearchStartResponse:
    """Continue a previous research session with a follow-up question.

    Creates a new session that carries forward context from the original.
    """
    original = _sessions.get(session_id)
    if not original:
        raise HTTPException(status_code=404, detail="Original session not found")
    if original["status"] != "completed":
        raise HTTPException(status_code=400, detail="Original research not yet complete")

    # Build context-enriched query
    original_report = original["result"].get("report", "")
    enriched_query = (
        f"Previous research on: {original['query']}\n\n"
        f"Key findings:\n{original_report[:2000]}\n\n"
        f"Follow-up question: {req.query}"
    )

    new_session_id = str(uuid.uuid4())
    sse_manager.create_session(new_session_id)

    _sessions[new_session_id] = {
        "query": req.query,
        "depth": req.depth,
        "status": "running",
        "result": None,
        "continued_from": session_id,
    }

    asyncio.create_task(
        _run_research_task(new_session_id, enriched_query, req.depth)
    )

    return ResearchStartResponse(session_id=new_session_id)


@router.get("/history")
async def list_history() -> list[dict]:
    """List past research sessions."""
    return [
        {
            "session_id": sid,
            "query": data["query"],
            "depth": data["depth"],
            "status": data["status"],
            "continued_from": data.get("continued_from"),
        }
        for sid, data in _sessions.items()
    ]
