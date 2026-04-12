"""PlannerAgent: Decomposes research queries into sub-questions."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agentscope.agent import AgentBase
from agentscope.message import Msg

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "planner.md"


class PlannerAgent(AgentBase):
    """Decomposes a user's research query into structured sub-questions.

    Outputs a ResearchPlan as JSON in Msg.metadata["plan"].
    """

    def __init__(self, model: object) -> None:
        super().__init__(name="Planner", model=model)
        self._sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def reply(self, msg: Msg | None = None) -> Msg:
        query = msg.content if msg else ""

        prompt = [
            Msg(name="system", content=self._sys_prompt, role="system"),
            Msg(name="user", content=query, role="user"),
        ]

        response = await self.model(prompt)
        text = response.text if hasattr(response, "text") else str(response)

        # Parse JSON from the response
        try:
            # Handle markdown code blocks
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
                    }
                ],
                "search_strategy": "Direct search for the main query",
            }

        # Ensure sub_questions is a list of dicts with required fields
        for sq in plan.get("sub_questions", []):
            if isinstance(sq, str):
                sq = {"question": sq, "keywords": [], "priority": 1}

        return Msg(
            name=self.name,
            content=f"Research plan with {len(plan.get('sub_questions', []))} sub-questions",
            role="assistant",
            metadata={"plan": plan},
        )
