"""Core research pipeline: validator → planner → DAG → fact-check → iteration loop."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from agentscope.message import Msg
from agentscope.model import OpenAIChatModel

from ..agents.validator import PremiseValidatorAgent
from ..agents.planner import PlannerAgent
from ..agents.searcher import create_searcher_factory
from ..agents.reader import create_reader_factory
from ..agents.synthesizer import create_synthesizer_factory
from ..agents.distiller import create_distiller_factory
from ..agents.critic import create_critic_factory
from ..dag.engine import DAGPipeline
from ..dag.builder import build_research_dag, get_dag_structure
from ..dag.nodes import NodeStatus
from ..tools.fact_checker import verify_all_citations

logger = logging.getLogger(__name__)

DEPTH_PRESETS = {
    "quick": (1, 3, 3),
    "standard": (2, 5, 5),
    "deep": (3, 7, 8),
}


def load_model_config() -> dict:
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "model_config.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def create_model(config: dict) -> OpenAIChatModel:
    return OpenAIChatModel(
        model_name=config["model_name"],
        stream=False,
        generate_kwargs={"temperature": config.get("temperature", 0.3)},
    )


async def run_research(
    query: str,
    depth: str = "standard",
    on_progress: Callable[..., Any] | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Execute the full research pipeline with all deficiency fixes.

    Pipeline stages:
    0. Retrieve memory context (Qdrant + Turso buffer)
    1. Premise validation (reject nonsense, classify query)
    2. Intent-aware planning (deep decomposition)
    3. DAG execution (parallel search → read → synthesize → distill → critique)
    4. Fact-checking (citation verification, unsupported claim detection)
    5. Iteration loop (critic-driven refinement)
    6. Store results in memory (Qdrant + Turso buffer)
    """
    max_iterations, max_sub_questions, max_urls = DEPTH_PRESETS.get(
        depth, DEPTH_PRESETS["standard"]
    )

    model_config = load_model_config()
    planner_model = create_model(model_config["planner"])
    searcher_model = create_model(model_config["searcher"])
    reader_model = create_model(model_config["reader"])
    synthesizer_model = create_model(model_config["synthesizer"])
    critic_model = create_model(model_config["critic"])

    searcher_factory = create_searcher_factory(searcher_model)
    reader_factory = create_reader_factory(reader_model)
    synthesizer_factory = create_synthesizer_factory(synthesizer_model)
    distiller_factory = create_distiller_factory(synthesizer_model)
    critic_factory = create_critic_factory(critic_model)

    async def emit(event_type: str, data: dict) -> None:
        if on_progress:
            await on_progress(event_type, data)

    # ── Stage -1: Retrieve Memory Context ─────────────────────────────

    memory_context = ""
    if user_id:
        try:
            from ..db.memory import build_context_from_memory
            from ..vector.memory import search_similar_research

            # Turso buffer: recent research summaries
            memory_context = build_context_from_memory(user_id, limit=5)

            # Qdrant: semantically similar past research
            similar = await search_similar_research(query, user_id=user_id, top_k=3)
            if similar:
                memory_context += "\n\n## Similar Past Research\n"
                for s in similar:
                    memory_context += f"- {s['query']}: {s['distilled_summary'][:150]}\n"
        except Exception:
            logger.debug("Memory retrieval skipped", exc_info=True)

    # ── Stage 0: Premise Validation ──────────────────────────────────

    await emit("status", {"agent": "Validator", "message": "Checking query premise..."})

    validator = PremiseValidatorAgent(model=planner_model)
    validation_msg = await validator(Msg(name="user", content=query, role="user"))
    validation = validation_msg.metadata.get("validation", {})

    premise_warning = ""
    effective_query = query

    if not validation.get("is_valid", True):
        await emit("validation", {
            "is_valid": False,
            "concerns": validation.get("concerns", []),
        })
        # Still proceed but with warning
        premise_warning = validation.get("warning", "The premise of this query may be flawed.")

    if validation.get("rewritten_query"):
        effective_query = validation["rewritten_query"]
        await emit("status", {
            "agent": "Validator",
            "message": f"Query rewritten: {effective_query[:100]}",
        })

    # ── Stage 1+: Planning and DAG Execution Loop ────────────────────

    planner = PlannerAgent(model=planner_model)
    final_report = ""
    distilled_summary = ""
    all_sources: list[dict] = []
    reasoning_trace: list[dict] = []
    fact_check_result: dict = {}
    iteration = 0
    gaps: list[str] = []

    for iteration in range(1, max_iterations + 1):
        await emit("iteration_start", {"iteration": iteration, "max": max_iterations})

        # ── Planning ──
        await emit("status", {"agent": "Planner", "message": "Analyzing intent and decomposing query..."})

        if iteration == 1:
            plan_input = effective_query
            if premise_warning:
                plan_input = f"{effective_query}\n\n[VALIDATOR WARNING: {premise_warning}]"
            if memory_context:
                plan_input = f"{plan_input}\n\n{memory_context}"
            plan_msg = await planner(Msg(name="user", content=plan_input, role="user"))
        else:
            gap_context = (
                f"Original query: {effective_query}\n\n"
                f"Previous research gaps to address:\n"
                + "\n".join(f"- {g}" for g in gaps)
            )
            plan_msg = await planner(Msg(name="user", content=gap_context, role="user"))

        plan = plan_msg.metadata.get("plan", {})

        # Trim sub-questions to depth limit
        plan["sub_questions"] = plan.get("sub_questions", [])[:max_sub_questions]

        reasoning_trace.append({
            "agent": "Planner",
            "action": "decomposed query",
            "output_summary": f"{len(plan['sub_questions'])} sub-questions, type={plan.get('query_type')}, domain={plan.get('domain')}",
            "decisions": [f"Query type: {plan.get('query_type')}", f"Domain: {plan.get('domain')}"],
        })

        await emit("status", {
            "agent": "Planner",
            "message": f"Plan: {len(plan['sub_questions'])} sub-questions ({plan.get('query_type', '?')} / {plan.get('domain', '?')})",
        })

        # ── Build and Execute DAG ──
        dag_nodes = build_research_dag(
            plan=plan,
            searcher_factory=searcher_factory,
            reader_factory=reader_factory,
            synthesizer_factory=synthesizer_factory,
            distiller_factory=distiller_factory,
            critic_factory=critic_factory,
        )

        dag_structure = get_dag_structure(dag_nodes)
        await emit("dag_init", {"structure": dag_structure, "iteration": iteration})

        async def dag_progress(node_id: str, status: NodeStatus, data: Any = None) -> None:
            summary = ""
            if data and hasattr(data, "content"):
                summary = str(data.content)[:200]
            await emit(f"node_{status.value}", {"node_id": node_id, "summary": summary})

        pipeline = DAGPipeline(
            on_progress=dag_progress,
            max_concurrency=max_urls,
            node_timeout=120.0,
        )

        seed_results = {"planner": plan_msg}
        dag_result = await pipeline.run(dag_nodes, seed_results)

        # ── Extract Results ──
        synthesizer_output = dag_result.outputs.get("synthesizer")
        distiller_output = dag_result.outputs.get("distiller")
        critic_output = dag_result.outputs.get("critic")

        if synthesizer_output:
            report_text = synthesizer_output.content if hasattr(synthesizer_output, "content") else str(synthesizer_output)
            # Prepend premise warning if present
            if premise_warning and iteration == 1:
                final_report = f"> **Warning:** {premise_warning}\n\n{report_text}"
            else:
                final_report = report_text

        if distiller_output:
            distilled_summary = distiller_output.content if hasattr(distiller_output, "content") else str(distiller_output)

        # ── Fact-Checking (citation verification) ──
        await emit("status", {"agent": "FactChecker", "message": "Verifying citations..."})
        try:
            fact_check_result = await verify_all_citations(final_report)
            await emit("fact_check", {
                "total": fact_check_result.get("total", 0),
                "verified": fact_check_result.get("verified", 0),
                "dead": fact_check_result.get("dead", 0),
            })
        except Exception as exc:
            logger.warning("Fact-check failed: %s", exc)
            fact_check_result = {"total": 0, "verified": 0, "dead": 0, "details": []}

        # ── Critic Verdict ──
        if critic_output and hasattr(critic_output, "metadata"):
            critique = critic_output.metadata.get("critique", {})
            is_complete = critique.get("is_complete", True)
            score = critique.get("completeness_score", 10)
            gaps = critique.get("gaps", [])

            reasoning_trace.append({
                "agent": "Critic",
                "action": "reviewed report",
                "output_summary": f"Score: {score}/10, complete: {is_complete}",
                "decisions": [
                    f"Gaps: {gaps}" if gaps else "No gaps",
                    f"Hallucination concerns: {critique.get('hallucination_concerns', [])}",
                ],
            })

            await emit("critique", {
                "score": score,
                "is_complete": is_complete,
                "gaps": gaps,
                "hallucination_concerns": critique.get("hallucination_concerns", []),
                "iteration": iteration,
            })

            if is_complete or iteration >= max_iterations:
                break
        else:
            break

    # ── Store in Memory ──
    if user_id and distilled_summary:
        try:
            from ..db.memory import store_memory, prune_old_memories

            plan_data = plan_msg.metadata.get("plan", {}) if plan_msg else {}
            store_memory(
                user_id=user_id,
                session_id=state_session_id if 'state_session_id' in dir() else "",
                summary=distilled_summary[:500],
                domain=plan_data.get("domain", "general"),
                query_type=plan_data.get("query_type", "exploratory"),
            )
            prune_old_memories(user_id, keep=50)
        except Exception:
            logger.debug("Memory storage skipped", exc_info=True)

    # ── Final Output ──
    await emit("done", {
        "report": final_report,
        "distilled": distilled_summary,
        "iterations": iteration,
    })

    return {
        "report": final_report,
        "distilled_summary": distilled_summary,
        "sources": all_sources,
        "iterations": iteration,
        "validation": validation,
        "fact_check": fact_check_result,
        "reasoning_trace": reasoning_trace,
        "dag_trace": {
            "execution_order": dag_result.execution_order,
            "durations": dag_result.node_durations,
            "failures": dag_result.failed_nodes,
        },
    }
