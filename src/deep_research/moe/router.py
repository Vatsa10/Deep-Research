"""MoE Router: maps query classification → model assignments + skip flags."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MODEL_TIERS: dict[str, dict[str, Any]] = {
    "mini": {"model_name": "gpt-4o-mini", "temperature": 0.2},
    "heavy": {"model_name": "gpt-4o", "temperature": 0.3},
}


@dataclass
class PipelineConfig:
    """Configuration for a single pipeline run, determined by the MoE router."""

    complexity: str
    domain: str

    # Model tier names (keys into MODEL_TIERS) — None means skip agent
    validator_model: str | None
    planner_model: str
    searcher_model: str       # used by WebAgent (search + read unified)
    synthesizer_model: str
    distiller_model: str | None
    critic_model: str

    max_iterations: int
    max_sub_questions: int


# Pre-defined routes for each complexity level
_ROUTES: dict[str, dict] = {
    "simple": {
        "validator_model": None,
        "planner_model": "mini",
        "searcher_model": "mini",
        "synthesizer_model": "mini",
        "distiller_model": None,
        "critic_model": "mini",
        "max_iterations": 1,
        "max_sub_questions": 3,
    },
    "moderate": {
        "validator_model": "mini",
        "planner_model": "mini",
        "searcher_model": "mini",
        "synthesizer_model": "mini",
        "distiller_model": "mini",
        "critic_model": "mini",
        "max_iterations": 2,
        "max_sub_questions": 5,
    },
    "complex": {
        "validator_model": "mini",
        "planner_model": "mini",
        "searcher_model": "mini",
        "synthesizer_model": "heavy",
        "distiller_model": "mini",
        "critic_model": "heavy",
        "max_iterations": 3,
        "max_sub_questions": 7,
    },
}


def get_pipeline_config(
    classification: dict,
    depth_override: str | None = None,
) -> PipelineConfig:
    """Map a classifier result to a PipelineConfig.

    Args:
        classification: Output from classify_query().
        depth_override: If user explicitly selects "deep", force complex route.

    Returns:
        PipelineConfig with model assignments and limits.
    """
    complexity = classification.get("complexity", "moderate")

    if depth_override == "deep":
        complexity = "complex"
    elif depth_override == "quick" and complexity == "complex":
        complexity = "moderate"

    route = _ROUTES.get(complexity, _ROUTES["moderate"])

    return PipelineConfig(
        complexity=complexity,
        domain=classification.get("domain", "general"),
        **route,
    )
