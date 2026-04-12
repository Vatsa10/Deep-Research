"""Integration tests for the research pipeline."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from deep_research.dag.builder import build_research_dag, get_dag_structure
from deep_research.dag.nodes import DAGNode


class FakeMsg:
    def __init__(self, content="", metadata=None):
        self.content = content
        self.name = "test"
        self.role = "assistant"
        self.metadata = metadata or {}


def test_build_research_dag_structure():
    """build_research_dag should create correct node topology."""
    plan = {
        "sub_questions": ["Question 1", "Question 2", "Question 3"],
    }

    def searcher_factory(q):
        def factory():
            async def agent(msg=None):
                return FakeMsg(f"search results for {q}")

            return agent

        return factory

    def reader_factory():
        def factory():
            async def agent(msg=None):
                return FakeMsg("extracted content")

            return agent

        return factory

    def synth_factory():
        def factory():
            async def agent(msg=None):
                return FakeMsg("# Report\n\nSynthesized content")

            return agent

        return factory

    def critic_factory():
        def factory():
            async def agent(msg=None):
                return FakeMsg(
                    "critique",
                    metadata={
                        "critique": {
                            "is_complete": True,
                            "completeness_score": 9,
                            "gaps": [],
                            "factual_issues": [],
                            "feedback": "Great report.",
                        }
                    },
                )

            return agent

        return factory

    nodes = build_research_dag(
        plan=plan,
        searcher_factory=searcher_factory,
        reader_factory=reader_factory,
        synthesizer_factory=synth_factory,
        critic_factory=critic_factory,
    )

    # Should have: 3 searchers + 3 readers + 1 synthesizer + 1 critic = 8 nodes
    assert len(nodes) == 8

    node_ids = {n.id for n in nodes}
    assert "searcher_0" in node_ids
    assert "searcher_1" in node_ids
    assert "searcher_2" in node_ids
    assert "reader_0" in node_ids
    assert "reader_1" in node_ids
    assert "reader_2" in node_ids
    assert "synthesizer" in node_ids
    assert "critic" in node_ids

    # Check dependencies
    node_map = {n.id: n for n in nodes}
    assert node_map["reader_0"].depends_on == ["searcher_0"]
    assert node_map["reader_1"].depends_on == ["searcher_1"]
    assert set(node_map["synthesizer"].depends_on) == {
        "reader_0",
        "reader_1",
        "reader_2",
    }
    assert node_map["critic"].depends_on == ["synthesizer"]

    # All searchers depend on planner (seed)
    for i in range(3):
        assert node_map[f"searcher_{i}"].depends_on == ["planner"]


def test_get_dag_structure_for_frontend():
    """get_dag_structure should return serializable node/edge data."""
    nodes = [
        DAGNode(id="a", agent_factory=lambda: None, label="Node A", agent_type="searcher"),
        DAGNode(
            id="b",
            agent_factory=lambda: None,
            depends_on=["a"],
            label="Node B",
            agent_type="reader",
        ),
    ]

    structure = get_dag_structure(nodes)

    assert len(structure["nodes"]) == 2
    assert len(structure["edges"]) == 1
    assert structure["edges"][0] == {"from": "a", "to": "b"}
    assert structure["nodes"][0]["label"] == "Node A"
