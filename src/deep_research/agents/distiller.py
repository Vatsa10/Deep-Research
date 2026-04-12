"""DistillerAgent: Compresses synthesis into actionable executive summary."""

from __future__ import annotations

import logging
from pathlib import Path

from agentscope.agent import AgentBase
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "distiller.md"


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


class DistillerAgent(AgentBase):
    """Takes a full synthesized report and produces a concise executive summary."""

    def __init__(self, model: object) -> None:
        super().__init__()
        self.name = "Distiller"
        self.model = model
        self._formatter = OpenAIChatFormatter()
        self._sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def reply(self, msg: Msg | None = None) -> Msg:
        report = msg.content if msg else "No report provided."

        messages = [
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

        formatted = await self._formatter.format(messages)
        response = await self.model(formatted)
        text = _extract_text(response.content)

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
