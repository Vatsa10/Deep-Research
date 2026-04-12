"""Mixture of Experts: query classification + adaptive model routing."""

from .classifier import classify_query
from .router import get_pipeline_config, PipelineConfig

__all__ = ["classify_query", "get_pipeline_config", "PipelineConfig"]
