"""Research template CRUD operations."""

from __future__ import annotations

import uuid

from .client import get_db

BUILTIN_TEMPLATES = [
    {
        "id": "market-analysis",
        "user_id": "system",
        "name": "Market Analysis",
        "description": "Competitive landscape, market size, key players, trends",
        "query_pattern": "Market analysis for {topic}: size, growth, key players, trends, and opportunities",
        "depth": "deep",
        "domain": "financial",
    },
    {
        "id": "literature-review",
        "user_id": "system",
        "name": "Literature Review",
        "description": "Academic deep dive with citations and methodology",
        "query_pattern": "Literature review on {topic}: key papers, methodologies, findings, and gaps",
        "depth": "deep",
        "domain": "scientific",
    },
    {
        "id": "tech-comparison",
        "user_id": "system",
        "name": "Tech Comparison",
        "description": "Framework/tool comparison with benchmarks",
        "query_pattern": "Compare {topic}: features, performance, ecosystem, learning curve, and recommendation",
        "depth": "standard",
        "domain": "technical",
    },
    {
        "id": "due-diligence",
        "user_id": "system",
        "name": "Due Diligence",
        "description": "Company/startup research for investors",
        "query_pattern": "Due diligence on {topic}: business model, financials, team, market position, risks",
        "depth": "deep",
        "domain": "financial",
    },
    {
        "id": "news-briefing",
        "user_id": "system",
        "name": "News Briefing",
        "description": "What happened this week in a topic",
        "query_pattern": "Latest news and developments in {topic} this week",
        "depth": "quick",
        "domain": "general",
    },
]


def seed_builtin_templates() -> None:
    """Insert built-in templates if they don't exist."""
    db = get_db()
    for t in BUILTIN_TEMPLATES:
        existing = db.execute(
            "SELECT id FROM templates WHERE id = ?", (t["id"],)
        ).fetchone()
        if not existing:
            db.execute(
                """INSERT INTO templates (id, user_id, name, description, query_pattern, depth, domain)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (t["id"], t["user_id"], t["name"], t["description"],
                 t["query_pattern"], t["depth"], t["domain"]),
            )
    db.commit()


def create_template(
    user_id: str, name: str, query_pattern: str,
    description: str = "", depth: str = "standard", domain: str = "general",
) -> str:
    """Create a user template. Returns template_id."""
    db = get_db()
    template_id = str(uuid.uuid4())
    db.execute(
        """INSERT INTO templates (id, user_id, name, description, query_pattern, depth, domain)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (template_id, user_id, name, description, query_pattern, depth, domain),
    )
    db.commit()
    return template_id


def list_templates(user_id: str | None = None) -> list[dict]:
    """List templates. If user_id is None, returns only built-in templates."""
    db = get_db()
    if user_id:
        rows = db.execute(
            """SELECT id, user_id, name, description, query_pattern, depth, domain, created_at
            FROM templates WHERE user_id = ? OR user_id = 'system'
            ORDER BY created_at DESC""",
            (user_id,),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT id, user_id, name, description, query_pattern, depth, domain, created_at
            FROM templates WHERE user_id = 'system'
            ORDER BY created_at""",
        ).fetchall()
    return [_row_to_template(r) for r in rows]


def get_template(template_id: str) -> dict | None:
    """Get a template by ID."""
    db = get_db()
    row = db.execute(
        """SELECT id, user_id, name, description, query_pattern, depth, domain, created_at
        FROM templates WHERE id = ?""",
        (template_id,),
    ).fetchone()
    if not row:
        return None
    return _row_to_template(row)


def _row_to_template(row: tuple) -> dict:
    return {
        "id": row[0],
        "user_id": row[1],
        "name": row[2],
        "description": row[3],
        "query_pattern": row[4],
        "depth": row[5],
        "domain": row[6],
        "created_at": row[7],
        "is_builtin": row[1] == "system",
    }
