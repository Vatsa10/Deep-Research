"""Query complexity classifier — single cheap LLM call (~150 tokens)."""

from __future__ import annotations

import json
import logging

from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg

logger = logging.getLogger(__name__)

CLASSIFIER_PROMPT = """Classify this research query. Respond with JSON only, no markdown.

{
  "complexity": "simple|moderate|complex",
  "domain": "general|technical|medical|legal|financial|scientific",
  "needs_validation": true/false,
  "needs_distiller": true/false,
  "recommended_iterations": 1
}

Rules:
- simple: factual lookups, definitions, single-topic ("What is X?", "Who invented Y?", "Define Z")
- moderate: comparisons, multi-angle analysis, trends ("Compare X vs Y", "What are the trends in X?")
- complex: multi-domain, causal analysis, academic sources needed ("Impact of X on Y with evidence", anything medical/legal)
- needs_validation: false for obvious factual queries, true if premise could be flawed or topic is controversial
- needs_distiller: false for simple (report will be short), true for moderate and complex
- recommended_iterations: 1 for simple, 2 for moderate, 3 for complex"""


def _extract_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b["text"] if isinstance(b, dict) and "text" in b else str(b)
            for b in content
        )
    return str(content)


async def classify_query(query: str, model: object) -> dict:
    """Classify a query's complexity with a single cheap LLM call.

    Returns dict with: complexity, domain, needs_validation, needs_distiller,
    recommended_iterations.

    Cost: ~150 tokens. Latency: ~200ms.
    """
    formatter = OpenAIChatFormatter()
    messages = [
        Msg(name="system", content=CLASSIFIER_PROMPT, role="system"),
        Msg(name="user", content=query, role="user"),
    ]

    formatted = await formatter.format(messages)
    response = await model(formatted)
    text = _extract_text(response.content)

    try:
        # Strip markdown fences if present
        if "```" in text:
            text = text.split("```")[1] if "```json" not in text else text.split("```json")[1]
            text = text.split("```")[0]
        result = json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        logger.warning("Classifier failed to parse, defaulting to moderate")
        result = {
            "complexity": "moderate",
            "domain": "general",
            "needs_validation": True,
            "needs_distiller": True,
            "recommended_iterations": 2,
        }

    # Ensure all fields exist
    result.setdefault("complexity", "moderate")
    result.setdefault("domain", "general")
    result.setdefault("needs_validation", True)
    result.setdefault("needs_distiller", True)
    result.setdefault("recommended_iterations", 2)

    return result
