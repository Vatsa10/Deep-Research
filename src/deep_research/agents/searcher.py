"""SearcherAgent: Executes web searches for research sub-questions."""

from __future__ import annotations

import json
from pathlib import Path

from agentscope.agent import ReActAgent
from agentscope.message import Msg
from agentscope.tool import Toolkit

from ..tools.web_search import web_search

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "searcher.md"


def create_searcher(sub_question: str, model: object) -> callable:
    """Factory that returns a callable creating a SearcherAgent.

    The returned callable creates a fresh agent instance each time,
    suitable for use as a DAGNode.agent_factory.
    """

    def factory() -> ReActAgent:
        toolkit = Toolkit()
        toolkit.register_tool_function(web_search)

        sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        sys_prompt += f"\n\n## Your Assigned Sub-Question\n\n{sub_question}"

        agent = ReActAgent(
            name="Searcher",
            sys_prompt=sys_prompt,
            model=model,
            toolkit=toolkit,
            max_iters=3,
        )
        return agent

    return factory


def create_searcher_factory(model: object) -> callable:
    """Returns a function that, given a sub-question, returns an agent factory.

    Usage in DAG builder:
        factory_fn = create_searcher_factory(model)
        agent_factory = factory_fn("What is quantum computing?")
        # agent_factory() creates the actual agent
    """

    def make_factory(sub_question: str) -> callable:
        return create_searcher(sub_question, model)

    return make_factory


def parse_search_results(msg: Msg) -> list[dict]:
    """Extract search results from a searcher's output message."""
    content = msg.content if hasattr(msg, "content") else str(msg)

    # Try to extract structured results from metadata
    if hasattr(msg, "metadata") and msg.metadata:
        results = msg.metadata.get("search_results", [])
        if results:
            return results

    # Fallback: parse URLs from content
    urls = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("http://") or line.startswith("https://"):
            urls.append({"url": line, "title": "", "content": ""})
        elif "](http" in line:
            # Markdown link
            try:
                title = line.split("[")[1].split("]")[0]
                url = line.split("(")[1].split(")")[0]
                urls.append({"url": url, "title": title, "content": ""})
            except (IndexError, ValueError):
                continue
    return urls
