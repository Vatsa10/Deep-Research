"""Tests for agent implementations."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agentscope.message import Msg


@pytest.mark.asyncio
async def test_planner_produces_valid_plan():
    """PlannerAgent should output a structured research plan."""
    mock_response = MagicMock()
    mock_response.text = json.dumps(
        {
            "main_query": "quantum computing advances",
            "sub_questions": [
                {
                    "question": "What are the latest quantum computing breakthroughs?",
                    "keywords": ["quantum", "computing", "breakthroughs", "2026"],
                    "priority": 1,
                },
                {
                    "question": "Which companies lead quantum computing?",
                    "keywords": ["quantum", "computing", "companies", "leaders"],
                    "priority": 2,
                },
            ],
            "search_strategy": "Start with recent breakthroughs, then explore key players.",
        }
    )

    mock_model = AsyncMock(return_value=mock_response)

    from deep_research.agents.planner import PlannerAgent

    planner = PlannerAgent(model=mock_model)
    result = await planner.reply(
        Msg(name="user", content="quantum computing advances", role="user")
    )

    assert result.metadata is not None
    plan = result.metadata["plan"]
    assert "sub_questions" in plan
    assert len(plan["sub_questions"]) == 2
    assert plan["main_query"] == "quantum computing advances"


@pytest.mark.asyncio
async def test_planner_handles_malformed_json():
    """PlannerAgent should fallback gracefully on bad JSON."""
    mock_response = MagicMock()
    mock_response.text = "This is not valid JSON at all"

    mock_model = AsyncMock(return_value=mock_response)

    from deep_research.agents.planner import PlannerAgent

    planner = PlannerAgent(model=mock_model)
    result = await planner.reply(
        Msg(name="user", content="test query", role="user")
    )

    plan = result.metadata["plan"]
    assert "sub_questions" in plan
    assert len(plan["sub_questions"]) >= 1


@pytest.mark.asyncio
async def test_critic_parses_critique():
    """CriticAgent should parse structured critique from LLM output."""
    critique_json = json.dumps(
        {
            "is_complete": False,
            "completeness_score": 6,
            "gaps": ["Missing information about quantum error correction"],
            "factual_issues": [],
            "feedback": "Good coverage but needs more depth on error correction.",
        }
    )

    mock_response = MagicMock()
    mock_response.text = f"```json\n{critique_json}\n```"

    mock_model = AsyncMock(return_value=mock_response)

    from deep_research.agents.critic import CriticAgent

    critic = CriticAgent(model=mock_model)
    result = await critic.reply(
        Msg(name="synthesizer", content="Some research report...", role="assistant")
    )

    critique = result.metadata["critique"]
    assert critique["is_complete"] is False
    assert critique["completeness_score"] == 6
    assert len(critique["gaps"]) == 1


@pytest.mark.asyncio
async def test_synthesizer_produces_report():
    """SynthesizerAgent should produce a markdown report."""
    mock_response = MagicMock()
    mock_response.text = "# Research Report\n\n## Summary\n\nKey findings here."

    mock_model = AsyncMock(return_value=mock_response)

    from deep_research.agents.synthesizer import SynthesizerAgent

    synth = SynthesizerAgent(model=mock_model)
    result = await synth.reply(
        Msg(name="reader_aggregate", content="Findings...", role="assistant")
    )

    assert "Research Report" in result.content
    assert result.metadata["report_type"] == "synthesis"
