"""WebAgent: Unified search + read + extract agent.

Replaces the separate Searcher and Reader agents with a single autonomous
agent that has access to ALL web tools and decides what to do based on
the query context. It can search, read pages, fetch PDFs, get YouTube
transcripts, read GitHub repos — all in one ReAct loop.
"""

from __future__ import annotations

from pathlib import Path

from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.tool import Toolkit

from ..tools.web_search import web_search
from ..tools.web_reader import fetch_url
from ..tools.academic_search import academic_search

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "web_agent.md"


def create_web_agent(
    sub_question: str,
    model: object,
    include_academic: bool = False,
    max_iters: int = 6,
) -> callable:
    """Factory returning a callable that creates a WebAgent.

    The WebAgent autonomously:
    1. Searches the web (and optionally academic papers)
    2. Picks the most relevant URLs from results
    3. Fetches and extracts content from those URLs
    4. Follows links or searches again if initial results are insufficient
    5. Returns a structured summary with sources

    Args:
        sub_question: The research sub-question to investigate.
        model: The LLM model to use.
        include_academic: Whether to include academic_search tool.
        max_iters: Maximum ReAct iterations (search + read cycles).
    """

    def factory() -> ReActAgent:
        toolkit = Toolkit()
        toolkit.register_tool_function(web_search)
        toolkit.register_tool_function(fetch_url)
        if include_academic:
            toolkit.register_tool_function(academic_search)

        sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        sys_prompt += f"\n\n## Your Assigned Sub-Question\n\n{sub_question}"

        if include_academic:
            sys_prompt += (
                "\n\n**Note:** This sub-question benefits from academic sources. "
                "Use `academic_search` to find papers, then `fetch_url` to read "
                "the most relevant ones."
            )

        agent = ReActAgent(
            name="WebAgent",
            sys_prompt=sys_prompt,
            model=model,
            formatter=OpenAIChatFormatter(),
            toolkit=toolkit,
            max_iters=max_iters,
        )
        return agent

    return factory


def create_web_agent_factory(model: object) -> callable:
    """Returns a function that creates web agent factories for the DAG builder.

    Usage:
        factory_fn = create_web_agent_factory(model)
        agent_factory = factory_fn("What is quantum computing?", needs_academic=True)
        agent = agent_factory()  # creates the actual agent
    """

    def make_factory(sub_question: str, needs_academic: bool = False) -> callable:
        return create_web_agent(sub_question, model, include_academic=needs_academic)

    return make_factory
