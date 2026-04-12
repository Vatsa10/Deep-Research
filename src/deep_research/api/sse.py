"""SSE (Server-Sent Events) helpers for streaming research progress."""

from __future__ import annotations

import asyncio
import json
from typing import Any


class SSEManager:
    """Manages SSE event queues for active research sessions."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}

    def create_session(self, session_id: str) -> asyncio.Queue:
        """Create an event queue for a new research session."""
        queue: asyncio.Queue = asyncio.Queue()
        self._queues[session_id] = queue
        return queue

    def get_queue(self, session_id: str) -> asyncio.Queue | None:
        """Get the event queue for a session."""
        return self._queues.get(session_id)

    def remove_session(self, session_id: str) -> None:
        """Clean up a completed session's queue."""
        self._queues.pop(session_id, None)

    async def send_event(
        self, session_id: str, event_type: str, data: dict[str, Any]
    ) -> None:
        """Push an event to a session's queue."""
        queue = self._queues.get(session_id)
        if queue:
            await queue.put({"type": event_type, **data})

    async def send_done(self, session_id: str, data: dict[str, Any]) -> None:
        """Push the final 'done' event and clean up."""
        await self.send_event(session_id, "done", data)


def format_sse_event(data: dict[str, Any]) -> str:
    """Format a dict as an SSE event string."""
    return f"data: {json.dumps(data)}\n\n"


# Global SSE manager instance
sse_manager = SSEManager()
