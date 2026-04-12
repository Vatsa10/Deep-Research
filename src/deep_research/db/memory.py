"""Long-term memory buffer in Turso — rolling context window for users."""

from __future__ import annotations

import uuid

from .client import get_db


def store_memory(
    user_id: str,
    session_id: str,
    summary: str,
    domain: str = "general",
    query_type: str = "exploratory",
) -> None:
    """Store a research summary in the memory buffer."""
    db = get_db()
    db.execute(
        """INSERT INTO memory_buffer (id, user_id, session_id, summary, domain, query_type)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), user_id, session_id, summary, domain, query_type),
    )
    db.commit()


def get_recent_memories(user_id: str, limit: int = 10) -> list[dict]:
    """Get the most recent memory entries for a user (rolling buffer)."""
    db = get_db()
    rows = db.execute(
        """SELECT id, session_id, summary, domain, query_type, created_at
        FROM memory_buffer WHERE user_id = ?
        ORDER BY created_at DESC LIMIT ?""",
        (user_id, limit),
    ).fetchall()
    return [
        {
            "id": r[0],
            "session_id": r[1],
            "summary": r[2],
            "domain": r[3],
            "query_type": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]


def build_context_from_memory(user_id: str, limit: int = 5) -> str:
    """Build a context string from recent memories for the planner.

    Returns a text block summarizing what the user has researched recently,
    which the planner can use for better intent understanding.
    """
    memories = get_recent_memories(user_id, limit)
    if not memories:
        return ""

    lines = ["## Recent Research Context (from your past sessions)\n"]
    for m in memories:
        lines.append(f"- **{m['domain']}** ({m['query_type']}): {m['summary'][:200]}")

    return "\n".join(lines)


def prune_old_memories(user_id: str, keep: int = 50) -> None:
    """Keep only the most recent `keep` memories per user."""
    db = get_db()
    db.execute(
        """DELETE FROM memory_buffer WHERE user_id = ? AND id NOT IN (
            SELECT id FROM memory_buffer WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        )""",
        (user_id, user_id, keep),
    )
    db.commit()
