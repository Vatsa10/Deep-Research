"""Pydantic models for structured data exchange between agents."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SubQuestion(BaseModel):
    """A single research sub-question decomposed from the main query."""

    question: str = Field(description="The sub-question to investigate")
    keywords: list[str] = Field(
        default_factory=list,
        description="2-6 search keywords for this sub-question",
    )
    priority: int = Field(
        default=1, description="Priority 1 (highest) to 5 (lowest)"
    )


class ResearchPlan(BaseModel):
    """Output of the PlannerAgent: a structured research plan."""

    main_query: str = Field(description="The original user query")
    sub_questions: list[SubQuestion] = Field(
        description="Decomposed sub-questions to investigate"
    )
    search_strategy: str = Field(
        default="",
        description="High-level strategy for the research",
    )


class SourceInfo(BaseModel):
    """A single source found during research."""

    url: str
    title: str = ""
    relevance_score: float = 0.0
    snippet: str = ""


class SearchResult(BaseModel):
    """Output of a SearcherAgent."""

    sub_question: str
    sources: list[SourceInfo] = Field(default_factory=list)
    summary: str = ""


class ReportSection(BaseModel):
    """A section of the final research report."""

    title: str
    content: str
    sources: list[str] = Field(
        default_factory=list, description="URLs cited in this section"
    )


class CritiqueResult(BaseModel):
    """Output of the CriticAgent."""

    is_complete: bool = Field(
        description="Whether the research is comprehensive enough"
    )
    completeness_score: int = Field(
        description="Score from 1-10 on research completeness"
    )
    gaps: list[str] = Field(
        default_factory=list,
        description="Identified knowledge gaps requiring further research",
    )
    factual_issues: list[str] = Field(
        default_factory=list,
        description="Claims that need verification or correction",
    )
    feedback: str = Field(
        default="",
        description="Overall feedback on the report quality",
    )


class DAGNodeStatus(BaseModel):
    """Status of a single DAG node for frontend visualization."""

    id: str
    label: str
    agent_type: str
    status: str = "pending"
    summary: str = ""
    duration_s: float | None = None


class DAGStatus(BaseModel):
    """Full DAG status for frontend rendering."""

    nodes: list[DAGNodeStatus] = Field(default_factory=list)
    edges: list[dict] = Field(default_factory=list)
    iteration: int = 1
    max_iterations: int = 3
