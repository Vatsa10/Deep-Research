"""SynthesizerAgent: Merges research findings into a coherent report."""

from __future__ import annotations

import logging
from pathlib import Path

from agentscope.agent import AgentBase
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "synthesizer.md"


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


class SynthesizerAgent(AgentBase):
    """Merges findings from multiple reader agents into a structured report."""

    def __init__(self, model: object) -> None:
        super().__init__()
        self.name = "Synthesizer"
        self.model = model
        self._formatter = OpenAIChatFormatter()
        self._sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def reply(self, msg: Msg | None = None) -> Msg:
        context = msg.content if msg else "No findings provided."

        messages = [
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

        formatted = await self._formatter.format(messages)
        response = await self.model(formatted)
        text = _extract_text(response.content)

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
