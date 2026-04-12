"""CriticAgent: Reviews research reports for completeness and accuracy."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agentscope.agent import AgentBase
from agentscope.message import Msg

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "critic.md"


class CriticAgent(AgentBase):
    """Reviews a synthesized report and outputs a structured critique.

    Evaluates completeness, accuracy, and identifies knowledge gaps.
    The critique drives the iteration loop — if is_complete is False,
    the pipeline re-plans and searches for the identified gaps.
    """

    def __init__(self, model: object) -> None:
        super().__init__(name="Critic", model=model)
        self._sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def reply(self, msg: Msg | None = None) -> Msg:
        report = msg.content if msg else "No report provided."

        prompt = [
            Msg(name="system", content=self._sys_prompt, role="system"),
            Msg(
                name="user",
                content=(
                    "Review the following research report and provide "
                    "your critique:\n\n"
                    f"{report}"
                ),
                role="user",
            ),
        ]

        response = await self.model(prompt)
        text = response.text if hasattr(response, "text") else str(response)

        # Parse JSON critique
        try:
            if "```json" in text:
                text_json = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text_json = text.split("```")[1].split("```")[0].strip()
            else:
                text_json = text
            critique = json.loads(text_json)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse critic JSON, marking as complete")
            critique = {
                "is_complete": True,
                "completeness_score": 7,
                "gaps": [],
                "factual_issues": [],
                "feedback": "Unable to parse structured critique.",
            }

        return Msg(
            name=self.name,
            content=text,
            role="assistant",
            metadata={"critique": critique},
        )


def create_critic_factory(model: object) -> callable:
    """Returns a function that returns an agent factory for the critic."""

    def make_factory() -> callable:
        def factory() -> CriticAgent:
            return CriticAgent(model=model)

        return factory

    return make_factory
