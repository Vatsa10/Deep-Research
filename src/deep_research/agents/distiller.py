"""DistillerAgent: Compresses synthesis into actionable executive summary."""

from __future__ import annotations

import logging
from pathlib import Path

from agentscope.agent import AgentBase
from agentscope.message import Msg

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "distiller.md"


class DistillerAgent(AgentBase):
    """Takes a full synthesized report and produces a concise executive summary.

    Extracts key findings with confidence levels, actionable recommendations,
    and open questions.
    """

    def __init__(self, model: object) -> None:
        super().__init__(name="Distiller", model=model)
        self._sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def reply(self, msg: Msg | None = None) -> Msg:
        report = msg.content if msg else "No report provided."

        prompt = [
            Msg(name="system", content=self._sys_prompt, role="system"),
            Msg(
                name="user",
                content=(
                    "Distill the following research report into a concise "
                    "executive summary with key findings, recommendations, "
                    "and open questions:\n\n"
                    f"{report}"
                ),
                role="user",
            ),
        ]

        response = await self.model(prompt)
        text = response.text if hasattr(response, "text") else str(response)

        return Msg(
            name=self.name,
            content=text,
            role="assistant",
            metadata={"report_type": "distilled"},
        )


def create_distiller_factory(model: object) -> callable:
    """Returns a function that returns an agent factory for the distiller."""

    def make_factory() -> callable:
        def factory() -> DistillerAgent:
            return DistillerAgent(model=model)

        return factory

    return make_factory
