"""Tests for the async DAG pipeline engine."""

import asyncio
import pytest
from unittest.mock import AsyncMock

from deep_research.dag.engine import DAGPipeline
from deep_research.dag.nodes import DAGNode, DAGResult


class FakeMsg:
    """Minimal message stub for testing."""

    def __init__(self, content: str):
        self.content = content

    def __repr__(self):
        return f"FakeMsg({self.content!r})"


def make_agent(result_content: str, delay: float = 0.0):
    """Create a fake agent factory that returns a callable async agent."""

    def factory():
        async def agent(msg=None):
            if delay:
                await asyncio.sleep(delay)
            return FakeMsg(result_content)

        return agent

    return factory


@pytest.mark.asyncio
async def test_single_node():
    """A single node with no dependencies should execute."""
    nodes = [
        DAGNode(
            id="a",
            agent_factory=make_agent("result_a"),
        ),
    ]
    pipeline = DAGPipeline()
    result = await pipeline.run(nodes)

    assert "a" in result.outputs
    assert result.outputs["a"].content == "result_a"
    assert result.execution_order == ["a"]
    assert not result.failed_nodes


@pytest.mark.asyncio
async def test_sequential_dependency():
    """B depends on A — A must run first."""
    nodes = [
        DAGNode(id="a", agent_factory=make_agent("result_a")),
        DAGNode(
            id="b",
            agent_factory=make_agent("result_b"),
            depends_on=["a"],
        ),
    ]
    pipeline = DAGPipeline()
    result = await pipeline.run(nodes)

    assert result.execution_order.index("a") < result.execution_order.index("b")
    assert len(result.outputs) == 2


@pytest.mark.asyncio
async def test_parallel_execution():
    """Three independent nodes should all execute."""
    nodes = [
        DAGNode(id="a", agent_factory=make_agent("a", delay=0.05)),
        DAGNode(id="b", agent_factory=make_agent("b", delay=0.05)),
        DAGNode(id="c", agent_factory=make_agent("c", delay=0.05)),
    ]
    pipeline = DAGPipeline()
    result = await pipeline.run(nodes)

    assert len(result.outputs) == 3
    assert set(result.outputs.keys()) == {"a", "b", "c"}


@pytest.mark.asyncio
async def test_diamond_pattern():
    """A -> B,C -> D (B and C parallel, D waits for both)."""
    nodes = [
        DAGNode(id="a", agent_factory=make_agent("a")),
        DAGNode(id="b", agent_factory=make_agent("b"), depends_on=["a"]),
        DAGNode(id="c", agent_factory=make_agent("c"), depends_on=["a"]),
        DAGNode(id="d", agent_factory=make_agent("d"), depends_on=["b", "c"]),
    ]
    pipeline = DAGPipeline()
    result = await pipeline.run(nodes)

    order = result.execution_order
    assert order.index("a") < order.index("b")
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("d")
    assert order.index("c") < order.index("d")


@pytest.mark.asyncio
async def test_seed_results():
    """Nodes can depend on pre-populated seed results."""
    nodes = [
        DAGNode(
            id="b",
            agent_factory=make_agent("result_b"),
            depends_on=["seed"],
        ),
    ]
    pipeline = DAGPipeline()
    result = await pipeline.run(nodes, seed_results={"seed": FakeMsg("seed_data")})

    assert "b" in result.outputs


@pytest.mark.asyncio
async def test_timeout_handling():
    """A slow node should be marked as failed after timeout."""

    def slow_factory():
        async def agent(msg=None):
            await asyncio.sleep(10)
            return FakeMsg("never")

        return agent

    nodes = [
        DAGNode(id="slow", agent_factory=slow_factory),
    ]
    pipeline = DAGPipeline(node_timeout=0.1)
    result = await pipeline.run(nodes)

    assert "slow" in result.failed_nodes
    assert "slow" not in result.outputs


@pytest.mark.asyncio
async def test_max_concurrency():
    """Only max_concurrency nodes should run at once."""
    running = {"count": 0, "max_seen": 0}

    def counting_factory(name: str):
        def factory():
            async def agent(msg=None):
                running["count"] += 1
                running["max_seen"] = max(running["max_seen"], running["count"])
                await asyncio.sleep(0.05)
                running["count"] -= 1
                return FakeMsg(name)

            return agent

        return factory

    nodes = [
        DAGNode(id=f"n{i}", agent_factory=counting_factory(f"n{i}"))
        for i in range(6)
    ]
    pipeline = DAGPipeline(max_concurrency=2)
    result = await pipeline.run(nodes)

    assert len(result.outputs) == 6
    assert running["max_seen"] <= 2


@pytest.mark.asyncio
async def test_progress_callback():
    """Progress callback should be called for each node."""
    events: list[tuple] = []

    async def on_progress(node_id, status, data=None):
        events.append((node_id, status.value))

    nodes = [
        DAGNode(id="a", agent_factory=make_agent("a")),
        DAGNode(id="b", agent_factory=make_agent("b"), depends_on=["a"]),
    ]
    pipeline = DAGPipeline(on_progress=on_progress)
    await pipeline.run(nodes)

    node_ids = [e[0] for e in events]
    assert "a" in node_ids
    assert "b" in node_ids
