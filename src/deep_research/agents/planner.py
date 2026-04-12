"""PlannerAgent: Deep intent analysis and query decomposition."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agentscope.agent import AgentBase
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "planner.md"


def _extract_text(content: object) -> str:
    """Extract plain text from a ChatResponse content (list of blocks) or string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and "text" in block:
                parts.append(block["text"])
            elif hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts)
    return str(content)


PLAN_DEFAULTS = {
    "query_type": "exploratory",
    "domain": "general",
    "temporal_scope": "",
    "expertise_level": "intermediate",
    "implicit_constraints": [],
    "success_criteria": "",
    "search_strategy": "",
}


class PlannerAgent(AgentBase):
    """Analyzes user intent and decomposes queries into structured sub-questions.

    Outputs a ResearchPlan with intent metadata in Msg.metadata["plan"].
    """

    def __init__(self, model: object) -> None:
        super().__init__()
        self.name = "Planner"
        self.model = model
        self._formatter = OpenAIChatFormatter()
        self._sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def reply(self, msg: Msg | None = None) -> Msg:
        query = msg.content if msg else ""

        messages = [
            Msg(name="system", content=self._sys_prompt, role="system"),
            Msg(name="user", content=query, role="user"),
        ]

        formatted = await self._formatter.format(messages)
        response = await self.model(formatted)
        text = _extract_text(response.content)

        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            plan = json.loads(text)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse planner JSON, using fallback")
            plan = {
                "main_query": query,
                "sub_questions": [
                    {
                        "question": query,
                        "keywords": query.split()[:6],
                        "priority": 1,
                        "needs_academic": False,
                    }
                ],
            }

        for key, default in PLAN_DEFAULTS.items():
            if key not in plan:
                plan[key] = default

        normalized = []
        for sq in plan.get("sub_questions", []):
            if isinstance(sq, str):
                sq = {"question": sq, "keywords": [], "priority": 1, "needs_academic": False}
            elif isinstance(sq, dict):
                sq.setdefault("needs_academic", False)
                sq.setdefault("keywords", [])
                sq.setdefault("priority", 1)
            normalized.append(sq)
        plan["sub_questions"] = normalized

        return Msg(
            name=self.name,
            content=f"Research plan with {len(normalized)} sub-questions ({plan.get('query_type', 'exploratory')} query in {plan.get('domain', 'general')} domain)",
            role="assistant",
            metadata={"plan": plan},
        )
