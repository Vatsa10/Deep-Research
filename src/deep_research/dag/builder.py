"""Builds a research DAG from a planner's output."""

from __future__ import annotations

from typing import Any

from agentscope.message import Msg

from .nodes import DAGNode


def build_research_dag(
    plan: dict[str, Any],
    searcher_factory: Any,
    reader_factory: Any,
    synthesizer_factory: Any,
    critic_factory: Any,
) -> list[DAGNode]:
    """Construct a DAG of agent nodes from a research plan.

    The resulting DAG has this shape (for N sub-questions):

        planner (seed) ─┬─→ searcher_0 → reader_0 ─┐
                        ├─→ searcher_1 → reader_1 ─┼─→ synthesizer → critic
                        └─→ searcher_N → reader_N ─┘

    Args:
        plan: Dict with "sub_questions" list from the PlannerAgent.
        searcher_factory: Callable(sub_question: str) -> agent factory.
        reader_factory: Callable() -> agent factory.
        synthesizer_factory: Callable() -> agent factory.
        critic_factory: Callable() -> agent factory.

    Returns:
        List of DAGNode objects ready for DAGPipeline.run().
    """
    nodes: list[DAGNode] = []
    sub_questions: list[str] = plan.get("sub_questions", [])
    reader_ids: list[str] = []

    for i, question in enumerate(sub_questions):
        searcher_id = f"searcher_{i}"
        reader_id = f"reader_{i}"
        reader_ids.append(reader_id)

        # Searcher node: depends on planner (seed result)
        nodes.append(
            DAGNode(
                id=searcher_id,
                agent_factory=searcher_factory(question),
                depends_on=["planner"],
                transform=lambda upstream, q=question: Msg(
                    name="user",
                    content=f"Search for: {q}",
                    role="user",
                ),
                label=f"Search: {question[:50]}",
                agent_type="searcher",
            )
        )

        # Reader node: depends on its searcher
        nodes.append(
            DAGNode(
                id=reader_id,
                agent_factory=reader_factory(),
                depends_on=[searcher_id],
                transform=lambda upstream, sid=searcher_id: upstream[sid],
                label=f"Read sources for Q{i + 1}",
                agent_type="reader",
            )
        )

    # Synthesizer node: depends on ALL readers
    nodes.append(
        DAGNode(
            id="synthesizer",
            agent_factory=synthesizer_factory(),
            depends_on=reader_ids,
            transform=_merge_reader_outputs,
            label="Synthesize findings",
            agent_type="synthesizer",
        )
    )

    # Critic node: depends on synthesizer
    nodes.append(
        DAGNode(
            id="critic",
            agent_factory=critic_factory(),
            depends_on=["synthesizer"],
            transform=lambda upstream: upstream["synthesizer"],
            label="Review & fact-check",
            agent_type="critic",
        )
    )

    return nodes


def _merge_reader_outputs(upstream: dict[str, Any]) -> Msg:
    """Merge all reader outputs into a single context message for the synthesizer."""
    sections: list[str] = []
    for node_id, msg in sorted(upstream.items()):
        content = msg.content if hasattr(msg, "content") else str(msg)
        sections.append(f"## Findings from {node_id}\n\n{content}")

    merged = "\n\n---\n\n".join(sections)
    return Msg(
        name="reader_aggregate",
        content=merged,
        role="assistant",
    )


def get_dag_structure(nodes: list[DAGNode]) -> dict[str, Any]:
    """Export DAG structure for frontend visualization.

    Returns a dict with "nodes" and "edges" suitable for rendering.
    """
    dag_nodes = [
        {
            "id": n.id,
            "label": n.label,
            "type": n.agent_type,
            "depends_on": n.depends_on,
        }
        for n in nodes
    ]
    edges = []
    for n in nodes:
        for dep in n.depends_on:
            edges.append({"from": dep, "to": n.id})

    return {"nodes": dag_nodes, "edges": edges}
