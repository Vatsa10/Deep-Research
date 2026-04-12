"""Core research pipeline: connects planner → DAG builder → DAG executor → iteration loop."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

from agentscope.message import Msg
from agentscope.model import OpenAIChatModel

from ..agents.planner import PlannerAgent
from ..agents.searcher import create_searcher_factory
from ..agents.reader import create_reader_factory
from ..agents.synthesizer import create_synthesizer_factory
from ..agents.critic import create_critic_factory
from ..dag.engine import DAGPipeline
from ..dag.builder import build_research_dag, get_dag_structure
from ..dag.nodes import NodeStatus

logger = logging.getLogger(__name__)

# Depth presets: (max_iterations, max_sub_questions, max_urls_per_question)
DEPTH_PRESETS = {
    "quick": (1, 3, 3),
    "standard": (2, 5, 5),
    "deep": (3, 7, 8),
}


def load_model_config() -> dict:
    """Load model configuration from config file."""
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "model_config.json"
    with open(config_path, encoding="utf-8") as f:
        return json.load(f)


def create_model(config: dict) -> OpenAIChatModel:
    """Create an OpenAI chat model from config."""
    return OpenAIChatModel(
        model_name=config["model_name"],
        temperature=config.get("temperature", 0.3),
    )


async def run_research(
    query: str,
    depth: str = "standard",
    on_progress: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Execute the full research pipeline.

    Args:
        query: The user's research query.
        depth: Research depth — "quick", "standard", or "deep".
        on_progress: Optional async callback for SSE progress events.
            Signature: (event_type: str, data: dict) -> None

    Returns:
        Dict with keys: report, sources, iterations, dag_trace.
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

    # Agent factories for the DAG builder
    searcher_factory = create_searcher_factory(searcher_model)
    reader_factory = create_reader_factory(reader_model)
    synthesizer_factory = create_synthesizer_factory(synthesizer_model)
    critic_factory = create_critic_factory(critic_model)

    async def emit(event_type: str, data: dict) -> None:
        if on_progress:
            await on_progress(event_type, data)

    # Initialize planner
    planner = PlannerAgent(model=planner_model)
    final_report = ""
    all_sources: list[dict] = []
    iteration = 0

    for iteration in range(1, max_iterations + 1):
        await emit("iteration_start", {"iteration": iteration, "max": max_iterations})

        # Stage 1: Plan
        await emit("status", {"agent": "Planner", "message": "Decomposing query..."})

        if iteration == 1:
            plan_msg = await planner(Msg(name="user", content=query, role="user"))
        else:
            # Re-plan with gaps from the critic
            gap_context = (
                f"Original query: {query}\n\n"
                f"Previous research gaps to address:\n"
                + "\n".join(f"- {g}" for g in gaps)
            )
            plan_msg = await planner(
                Msg(name="user", content=gap_context, role="user")
            )

        plan = plan_msg.metadata.get("plan", {})
        sub_questions_raw = plan.get("sub_questions", [])

        # Normalize sub_questions
        sub_questions: list[str] = []
        for sq in sub_questions_raw[:max_sub_questions]:
            if isinstance(sq, dict):
                sub_questions.append(sq.get("question", str(sq)))
            else:
                sub_questions.append(str(sq))

        # Inject sub_questions as strings into the plan for the DAG builder
        plan["sub_questions"] = sub_questions

        await emit(
            "status",
            {
                "agent": "Planner",
                "message": f"Created plan with {len(sub_questions)} sub-questions",
            },
        )

        # Stage 2: Build and execute the DAG
        dag_nodes = build_research_dag(
            plan=plan,
            searcher_factory=searcher_factory,
            reader_factory=reader_factory,
            synthesizer_factory=synthesizer_factory,
            critic_factory=critic_factory,
        )

        # Send DAG structure to frontend
        dag_structure = get_dag_structure(dag_nodes)
        await emit("dag_init", {
            "structure": dag_structure,
            "iteration": iteration,
        })

        # DAG progress callback
        async def dag_progress(
            node_id: str, status: NodeStatus, data: Any = None
        ) -> None:
            summary = ""
            if data and hasattr(data, "content"):
                summary = str(data.content)[:200]
            await emit(
                f"node_{status.value}",
                {"node_id": node_id, "summary": summary},
            )

        # Execute the DAG
        pipeline = DAGPipeline(
            on_progress=dag_progress,
            max_concurrency=max_urls,
            node_timeout=120.0,
        )

        seed_results = {"planner": plan_msg}
        dag_result = await pipeline.run(dag_nodes, seed_results)

        # Extract results
        synthesizer_output = dag_result.outputs.get("synthesizer")
        critic_output = dag_result.outputs.get("critic")

        if synthesizer_output:
            final_report = (
                synthesizer_output.content
                if hasattr(synthesizer_output, "content")
                else str(synthesizer_output)
            )

        # Check critic's verdict
        if critic_output and hasattr(critic_output, "metadata"):
            critique = critic_output.metadata.get("critique", {})
            is_complete = critique.get("is_complete", True)
            score = critique.get("completeness_score", 10)
            gaps = critique.get("gaps", [])

            await emit("critique", {
                "score": score,
                "is_complete": is_complete,
                "gaps": gaps,
                "iteration": iteration,
            })

            if is_complete or iteration >= max_iterations:
                break
        else:
            break

    await emit("done", {
        "report": final_report,
        "iterations": iteration,
    })

    return {
        "report": final_report,
        "sources": all_sources,
        "iterations": iteration,
        "dag_trace": {
            "execution_order": dag_result.execution_order,
            "durations": dag_result.node_durations,
            "failures": dag_result.failed_nodes,
        },
    }
