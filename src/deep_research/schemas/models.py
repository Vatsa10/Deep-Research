"""Pydantic models for structured data exchange between agents."""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────


class QueryType(str, Enum):
    FACTUAL = "factual"
    COMPARATIVE = "comparative"
    CAUSAL = "causal"
    PREDICTIVE = "predictive"
    OPINION = "opinion"
    EXPLORATORY = "exploratory"


class SourceType(str, Enum):
    ACADEMIC = "academic"
    GOVERNMENT = "government"
    NEWS_MAJOR = "news_major"
    NEWS_OTHER = "news_other"
    DOCUMENTATION = "documentation"
    BLOG = "blog"
    FORUM = "forum"
    UNKNOWN = "unknown"


class CredibilityTier(str, Enum):
    TIER1 = "tier1"  # .edu, .gov, Nature, Science, arXiv, PubMed
    TIER2 = "tier2"  # .org, Reuters, BBC, IEEE, major outlets
    TIER3 = "tier3"  # general .com
    LOW = "low"      # Medium, Reddit, Quora, blogspot


class CitationStatus(str, Enum):
    VERIFIED = "verified"
    DEAD = "dead"
    UNRESOLVABLE = "unresolvable"
    UNCHECKED = "unchecked"


# ── Query Planning ─────────────────────────────────────────────────────


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
    needs_academic: bool = Field(
        default=False,
        description="Whether this sub-question benefits from academic sources",
    )


class ResearchPlan(BaseModel):
    """Output of the PlannerAgent: a structured research plan."""

    main_query: str = Field(description="The original user query")
    query_type: str = Field(
        default="exploratory",
        description="Type: factual, comparative, causal, predictive, opinion, exploratory",
    )
    domain: str = Field(
        default="general",
        description="Domain: general, technical, medical, legal, financial, scientific",
    )
    temporal_scope: str = Field(
        default="",
        description="Time range relevant to this query, e.g. '2024-2026'",
    )
    expertise_level: str = Field(
        default="intermediate",
        description="Target audience: beginner, intermediate, expert",
    )
    implicit_constraints: list[str] = Field(
        default_factory=list,
        description="Unstated user needs inferred from the query",
    )
    success_criteria: str = Field(
        default="",
        description="What would make this research genuinely useful",
    )
    sub_questions: list[SubQuestion] = Field(
        description="Decomposed sub-questions to investigate"
    )
    search_strategy: str = Field(
        default="",
        description="High-level strategy for the research",
    )


class ValidationResult(BaseModel):
    """Output of the PremiseValidatorAgent."""

    is_valid: bool = Field(description="Whether the premise is reasonable")
    query_type: str = Field(
        default="factual",
        description="Classification of the query type",
    )
    concerns: list[str] = Field(
        default_factory=list,
        description="Issues with the premise or query",
    )
    rewritten_query: str | None = Field(
        default=None,
        description="Suggested rewrite if the original is problematic",
    )
    warning: str = Field(
        default="",
        description="Warning to include in the report if premise is flawed",
    )


# ── Source & Credibility ───────────────────────────────────────────────


class SourceInfo(BaseModel):
    """A single source found during research, with credibility metadata."""

    url: str
    title: str = ""
    relevance_score: float = 0.0
    snippet: str = ""
    # Credibility fields
    credibility_score: float = Field(
        default=0.5,
        description="Overall credibility 0.0-1.0",
    )
    source_type: str = Field(
        default="unknown",
        description="academic, government, news_major, blog, forum, etc.",
    )
    credibility_tier: str = Field(
        default="tier3",
        description="tier1 (highest), tier2, tier3, low",
    )
    domain_authority: str = Field(
        default="",
        description="Domain of the source for authority assessment",
    )
    is_peer_reviewed: bool = False
    publication_date: str = Field(
        default="",
        description="When the source was published, if detectable",
    )
    citation_status: str = Field(
        default="unchecked",
        description="verified, dead, unresolvable, unchecked",
    )


class SearchResult(BaseModel):
    """Output of a SearcherAgent."""

    sub_question: str
    sources: list[SourceInfo] = Field(default_factory=list)
    summary: str = ""


# ── Reasoning & Evidence ──────────────────────────────────────────────


class ClaimWithEvidence(BaseModel):
    """A single factual claim linked to its supporting evidence."""

    claim: str = Field(description="The factual assertion")
    supporting_sources: list[str] = Field(
        default_factory=list,
        description="URLs that support this claim",
    )
    confidence: str = Field(
        default="medium",
        description="high, medium, low — based on source count and credibility",
    )
    is_verified: bool = Field(
        default=False,
        description="Whether fact-checker confirmed this claim",
    )
    issues: list[str] = Field(
        default_factory=list,
        description="Problems found: unsupported, single-source, low-credibility, etc.",
    )


class ReasoningStep(BaseModel):
    """A single step in the reasoning chain — what was done and why."""

    agent: str = Field(description="Which agent performed this step")
    action: str = Field(description="What was done: searched, read, scored, etc.")
    input_summary: str = Field(default="", description="What the agent received")
    output_summary: str = Field(default="", description="What the agent produced")
    decisions: list[str] = Field(
        default_factory=list,
        description="Key decisions made: sources kept/discarded, conflicts found, etc.",
    )


class Contradiction(BaseModel):
    """A conflict between two sources on the same topic."""

    topic: str = Field(description="What the disagreement is about")
    claim_a: str = Field(description="First claim")
    source_a: str = Field(description="URL supporting claim A")
    source_a_credibility: float = 0.5
    claim_b: str = Field(description="Opposing claim")
    source_b: str = Field(description="URL supporting claim B")
    source_b_credibility: float = 0.5
    resolution: str = Field(
        default="",
        description="Assessment of which is more likely correct and why",
    )
    confidence: str = Field(
        default="low",
        description="Confidence in the resolution",
    )


# ── Report ────────────────────────────────────────────────────────────


class ReportSection(BaseModel):
    """A section of the final research report."""

    title: str
    content: str
    sources: list[str] = Field(
        default_factory=list, description="URLs cited in this section"
    )
    confidence: str = Field(
        default="medium",
        description="Confidence level for this section",
    )


class FactCheckResult(BaseModel):
    """Output of the fact-checking pass."""

    total_claims: int = 0
    verified_claims: int = 0
    unsupported_claims: list[str] = Field(default_factory=list)
    unverified_statistics: list[str] = Field(default_factory=list)
    dead_links: list[str] = Field(default_factory=list)
    verified_links: list[str] = Field(default_factory=list)


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
    hallucination_concerns: list[str] = Field(
        default_factory=list,
        description="Claims that appear fabricated or unsupported",
    )
    recency_issues: list[str] = Field(
        default_factory=list,
        description="Areas where sources are outdated",
    )
    contradiction_gaps: list[str] = Field(
        default_factory=list,
        description="Contradictions not adequately addressed",
    )
    feedback: str = Field(
        default="",
        description="Overall feedback on the report quality",
    )


# ── DAG Status ────────────────────────────────────────────────────────


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
