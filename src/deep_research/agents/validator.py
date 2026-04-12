"""PremiseValidatorAgent: Evaluates query validity before research begins."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from agentscope.agent import AgentBase
from agentscope.message import Msg

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "validator.md"


class PremiseValidatorAgent(AgentBase):
    """Evaluates a research query for validity before planning.

    Classifies queries as valid, flawed-premise, or nonsensical.
    Outputs ValidationResult in Msg.metadata["validation"].
    """

    def __init__(self, model: object) -> None:
        super().__init__(name="Validator", model=model)
        self._sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")

    async def reply(self, msg: Msg | None = None) -> Msg:
        query = msg.content if msg else ""

        prompt = [
            Msg(name="system", content=self._sys_prompt, role="system"),
            Msg(name="user", content=query, role="user"),
        ]

        response = await self.model(prompt)
        text = response.text if hasattr(response, "text") else str(response)

        try:
            if "```json" in text:
                text_json = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text_json = text.split("```")[1].split("```")[0].strip()
            else:
                text_json = text
            validation = json.loads(text_json)
        except (json.JSONDecodeError, IndexError):
            logger.warning("Failed to parse validator JSON, assuming valid")
            validation = {
                "is_valid": True,
                "query_type": "exploratory",
                "concerns": [],
                "rewritten_query": None,
                "warning": "",
            }

        return Msg(
            name=self.name,
            content=f"Validation: {'valid' if validation.get('is_valid') else 'concerns found'}",
            role="assistant",
            metadata={"validation": validation},
        )
