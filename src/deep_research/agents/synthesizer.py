"""SynthesizerAgent: Merges research findings into a coherent report."""

from __future__ import annotations

import logging
from pathlib import Path

from agentscope.agent import AgentBase
from agentscope.message import Msg

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "synthesizer.md"


class SynthesizerAgent(AgentBase):
    """Merges findings from multiple reader agents into a structured report.

    Takes a merged context message containing all reader outputs and
    produces a comprehensive markdown research report.
    """

    def __init__(self, model: object) -> None:
        super().__init__(name="Synthesizer", model=model)
        self._sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def reply(self, msg: Msg | None = None) -> Msg:
        context = msg.content if msg else "No findings provided."

        prompt = [
            Msg(name="system", content=self._sys_prompt, role="system"),
            Msg(
                name="user",
                content=(
                    "Based on the following research findings, write a "
                    "comprehensive research report:\n\n"
                    f"{context}"
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
            metadata={"report_type": "synthesis"},
        )


def create_synthesizer_factory(model: object) -> callable:
    """Returns a function that returns an agent factory for the synthesizer."""

    def make_factory() -> callable:
        def factory() -> SynthesizerAgent:
            return SynthesizerAgent(model=model)

        return factory

    return make_factory
