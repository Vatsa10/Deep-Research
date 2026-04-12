"""WebAgent: Autonomous web research agent with full tool access.

A single agent that searches, reads, follows links, and extracts
content from any source the query demands. Replaces the old
separate Searcher + Reader architecture.
"""

from __future__ import annotations

from pathlib import Path

from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.tool import Toolkit

from ..tools.web_search import web_search, search_news, quick_answer
from ..tools.web_reader import fetch_url, crawl_links
from ..tools.academic_search import academic_search

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "web_agent.md"


def create_web_agent(
    sub_question: str,
    model: object,
    include_academic: bool = False,
    max_iters: int = 6,
) -> callable:
    """Factory returning a callable that creates a WebAgent.

    The agent autonomously decides which tools to use based on the
    sub-question. It has access to:
    - web_search: general web search
    - search_news: recent news articles
    - quick_answer: instant factual lookups
    - fetch_url: read any URL (web, PDF, YouTube, GitHub, etc.)
    - crawl_links: discover related pages within a site
    - academic_search: 200M+ academic papers (when enabled)
    """

    def factory() -> ReActAgent:
        toolkit = Toolkit()

        # Core tools — always available
        toolkit.register_tool_function(web_search)
        toolkit.register_tool_function(fetch_url)
        toolkit.register_tool_function(search_news)
        toolkit.register_tool_function(quick_answer)
        toolkit.register_tool_function(crawl_links)

        # Academic search — only when the sub-question needs it
        if include_academic:
            toolkit.register_tool_function(academic_search)

        sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        sys_prompt += f"\n\n## Your Assigned Sub-Question\n\n{sub_question}"

        if include_academic:
            sys_prompt += (
                "\n\n**Note:** This sub-question benefits from academic sources. "
                "Consider using `academic_search` alongside `web_search`."
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
    """Returns a function that creates web agent factories for the DAG builder."""

    def make_factory(sub_question: str, needs_academic: bool = False) -> callable:
        return create_web_agent(sub_question, model, include_academic=needs_academic)

    return make_factory
