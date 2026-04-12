"""Builds a research DAG from a planner's output."""

from __future__ import annotations

from typing import Any

from agentscope.message import Msg

from .nodes import DAGNode


def build_research_dag(
    plan: dict[str, Any],
    web_agent_factory: Any,
    synthesizer_factory: Any,
    distiller_factory: Any | None,
    critic_factory: Any,
    include_distiller: bool = True,
) -> list[DAGNode]:
    """Construct a DAG of agent nodes from a research plan.

    DAG shape (using unified WebAgent):

        planner (seed) ─┬─→ web_agent_0 ─┐
                        ├─→ web_agent_1 ─┼─→ synthesizer → [distiller] → critic
                        └─→ web_agent_N ─┘

    Each WebAgent autonomously searches + reads + extracts for its
    sub-question. No separate searcher/reader nodes needed.

    Args:
        plan: Dict with "sub_questions" list from the PlannerAgent.
        web_agent_factory: Callable(sub_question, needs_academic) -> agent factory.
        synthesizer_factory: Callable() -> agent factory.
        distiller_factory: Callable() -> agent factory or None.
        critic_factory: Callable() -> agent factory.
        include_distiller: Whether to include the distiller node.

    Returns:
        List of DAGNode objects ready for DAGPipeline.run().
    """
    nodes: list[DAGNode] = []
    sub_questions_raw = plan.get("sub_questions", [])
    agent_ids: list[str] = []

    for i, sq in enumerate(sub_questions_raw):
        if isinstance(sq, dict):
            question = sq.get("question", str(sq))
            needs_academic = sq.get("needs_academic", False)
        else:
            question = str(sq)
            needs_academic = False

        agent_id = f"web_agent_{i}"
        agent_ids.append(agent_id)

        nodes.append(
            DAGNode(
                id=agent_id,
                agent_factory=web_agent_factory(question, needs_academic=needs_academic),
                depends_on=["planner"],
                transform=lambda upstream, q=question: Msg(
                    name="user",
                    content=(
                        f"Research this sub-question thoroughly:\n\n{q}\n\n"
                        "Search the web, read the most relevant sources, "
                        "and provide a structured summary with citations."
                    ),
                    role="user",
                ),
                label=f"Research: {question[:45]}",
                agent_type="web_agent",
            )
        )

    # Synthesizer: depends on ALL web agents
    nodes.append(
        DAGNode(
            id="synthesizer",
            agent_factory=synthesizer_factory(),
            depends_on=agent_ids,
            transform=_merge_web_agent_outputs,
            label="Synthesize findings",
            agent_type="synthesizer",
        )
    )

    # Distiller: conditional (skipped for simple queries via MoE)
    if include_distiller and distiller_factory is not None:
        nodes.append(
            DAGNode(
                id="distiller",
                agent_factory=distiller_factory(),
                depends_on=["synthesizer"],
                transform=lambda upstream: upstream["synthesizer"],
                label="Distill insights",
                agent_type="distiller",
            )
        )
        critic_depends = ["distiller", "synthesizer"]
        critic_transform = _merge_for_critic
    else:
        critic_depends = ["synthesizer"]
        critic_transform = lambda upstream: upstream["synthesizer"]

    # Critic
    nodes.append(
        DAGNode(
            id="critic",
            agent_factory=critic_factory(),
            depends_on=critic_depends,
            transform=critic_transform,
            label="Review & fact-check",
            agent_type="critic",
        )
    )

    return nodes


def _merge_web_agent_outputs(upstream: dict[str, Any]) -> Msg:
    """Merge all web agent outputs into a single context for the synthesizer."""
    sections: list[str] = []
    for node_id, msg in sorted(upstream.items()):
        content = msg.content if hasattr(msg, "content") else str(msg)
        sections.append(f"## Research from {node_id}\n\n{content}")

    merged = "\n\n---\n\n".join(sections)
    return Msg(name="web_research_aggregate", content=merged, role="assistant")


def _merge_for_critic(upstream: dict[str, Any]) -> Msg:
    """Combine distilled summary and full synthesis for the critic."""
    distilled = upstream.get("distiller")
    synthesized = upstream.get("synthesizer")

    distilled_text = distilled.content if hasattr(distilled, "content") else str(distilled)
    synth_text = synthesized.content if hasattr(synthesized, "content") else str(synthesized)

    combined = (
        f"## Executive Summary (from Distiller)\n\n{distilled_text}\n\n"
        f"---\n\n## Full Report (from Synthesizer)\n\n{synth_text}"
    )
    return Msg(name="critic_input", content=combined, role="assistant")


def get_dag_structure(nodes: list[DAGNode]) -> dict[str, Any]:
    """Export DAG structure for frontend visualization."""
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
