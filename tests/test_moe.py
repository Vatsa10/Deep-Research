"""Tests for the Mixture of Experts routing system."""

import os
import pytest

os.environ.setdefault("JWT_SECRET", "test-secret")


class TestRouter:
    def test_simple_route(self):
        from deep_research.moe.router import get_pipeline_config

        config = get_pipeline_config({"complexity": "simple", "domain": "general"})
        assert config.complexity == "simple"
        assert config.validator_model is None  # skipped
        assert config.distiller_model is None  # skipped
        assert config.synthesizer_model == "mini"
        assert config.critic_model == "mini"
        assert config.max_iterations == 1
        assert config.max_sub_questions == 3

    def test_moderate_route(self):
        from deep_research.moe.router import get_pipeline_config

        config = get_pipeline_config({"complexity": "moderate", "domain": "technical"})
        assert config.complexity == "moderate"
        assert config.validator_model == "mini"
        assert config.distiller_model == "mini"
        assert config.synthesizer_model == "mini"
        assert config.max_iterations == 2
        assert config.max_sub_questions == 5

    def test_complex_route(self):
        from deep_research.moe.router import get_pipeline_config

        config = get_pipeline_config({"complexity": "complex", "domain": "medical"})
        assert config.complexity == "complex"
        assert config.validator_model == "mini"
        assert config.distiller_model == "mini"
        assert config.synthesizer_model == "heavy"  # gpt-4o
        assert config.critic_model == "heavy"       # gpt-4o
        assert config.max_iterations == 3
        assert config.max_sub_questions == 7

    def test_deep_override_forces_complex(self):
        from deep_research.moe.router import get_pipeline_config

        config = get_pipeline_config(
            {"complexity": "simple", "domain": "general"},
            depth_override="deep",
        )
        assert config.complexity == "complex"
        assert config.synthesizer_model == "heavy"
        assert config.max_iterations == 3

    def test_quick_override_caps_complex(self):
        from deep_research.moe.router import get_pipeline_config

        config = get_pipeline_config(
            {"complexity": "complex", "domain": "medical"},
            depth_override="quick",
        )
        assert config.complexity == "moderate"  # capped
        assert config.max_iterations == 2

    def test_default_fallback(self):
        from deep_research.moe.router import get_pipeline_config

        config = get_pipeline_config({})  # missing fields
        assert config.complexity == "moderate"  # default

    def test_model_tiers_exist(self):
        from deep_research.moe.router import MODEL_TIERS

        assert "mini" in MODEL_TIERS
        assert "heavy" in MODEL_TIERS
        assert MODEL_TIERS["mini"]["model_name"] == "gpt-4o-mini"
        assert MODEL_TIERS["heavy"]["model_name"] == "gpt-4o"

    def test_pipeline_config_fields(self):
        from deep_research.moe.router import get_pipeline_config, PipelineConfig

        config = get_pipeline_config({"complexity": "moderate"})
        assert isinstance(config, PipelineConfig)
        assert hasattr(config, "planner_model")
        assert hasattr(config, "searcher_model")
        assert hasattr(config, "synthesizer_model")
        assert hasattr(config, "critic_model")
        assert hasattr(config, "max_iterations")
        assert hasattr(config, "max_sub_questions")


class TestDAGBuilderWebAgent:
    """Tests for the unified WebAgent-based DAG."""

    def _make_factory(self):
        def factory(*a, **kw):
            def f():
                async def agent(msg=None):
                    pass
                return agent
            return f
        return factory

    def test_dag_creates_web_agent_nodes(self):
        from deep_research.dag.builder import build_research_dag

        f = self._make_factory()
        plan = {"sub_questions": ["Q1", "Q2", "Q3"]}
        nodes = build_research_dag(plan, f, f, f, f, include_distiller=True)

        ids = {n.id for n in nodes}
        assert "web_agent_0" in ids
        assert "web_agent_1" in ids
        assert "web_agent_2" in ids
        assert "synthesizer" in ids
        assert "distiller" in ids
        assert "critic" in ids
        # No separate searcher/reader nodes
        assert not any("searcher" in nid for nid in ids)
        assert not any("reader" in nid for nid in ids)

    def test_dag_web_agents_are_parallel(self):
        from deep_research.dag.builder import build_research_dag

        f = self._make_factory()
        plan = {"sub_questions": ["Q1", "Q2"]}
        nodes = build_research_dag(plan, f, f, f, f, include_distiller=True)

        # All web agents depend on planner (parallel)
        for n in nodes:
            if n.id.startswith("web_agent"):
                assert n.depends_on == ["planner"]

    def test_dag_without_distiller(self):
        from deep_research.dag.builder import build_research_dag

        f = self._make_factory()
        plan = {"sub_questions": ["Q1"]}
        nodes = build_research_dag(plan, f, f, None, f, include_distiller=False)

        ids = {n.id for n in nodes}
        assert "distiller" not in ids
        assert "critic" in ids

        critic = next(n for n in nodes if n.id == "critic")
        assert "synthesizer" in critic.depends_on

    def test_dag_synthesizer_depends_on_all_web_agents(self):
        from deep_research.dag.builder import build_research_dag

        f = self._make_factory()
        plan = {"sub_questions": ["Q1", "Q2", "Q3"]}
        nodes = build_research_dag(plan, f, f, f, f, include_distiller=True)

        synth = next(n for n in nodes if n.id == "synthesizer")
        assert set(synth.depends_on) == {"web_agent_0", "web_agent_1", "web_agent_2"}
