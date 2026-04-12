"""SearcherAgent: Executes web and academic searches for research sub-questions."""

from __future__ import annotations

from pathlib import Path

from agentscope.agent import ReActAgent
from agentscope.formatter import OpenAIChatFormatter
from agentscope.message import Msg
from agentscope.tool import Toolkit

from ..tools.web_search import web_search
from ..tools.academic_search import academic_search

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "searcher.md"


def create_searcher(
    sub_question: str,
    model: object,
    include_academic: bool = False,
) -> callable:
    """Factory that returns a callable creating a SearcherAgent.

    Args:
        sub_question: The sub-question this searcher is responsible for.
        model: The LLM model to use.
        include_academic: Whether to register academic_search tool.
    """

    def factory() -> ReActAgent:
        toolkit = Toolkit()
        toolkit.register_tool_function(web_search)
        if include_academic:
            toolkit.register_tool_function(academic_search)

        sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")
        sys_prompt += f"\n\n## Your Assigned Sub-Question\n\n{sub_question}"
        if include_academic:
            sys_prompt += "\n\n**Note:** This sub-question benefits from academic sources. Use `academic_search` first, then supplement with `web_search`."

        agent = ReActAgent(
            name="Searcher",
            sys_prompt=sys_prompt,
            model=model,
            formatter=OpenAIChatFormatter(),
            toolkit=toolkit,
            max_iters=3,
        )
        return agent

    return factory


def create_searcher_factory(model: object) -> callable:
    """Returns a function that, given a sub-question, returns an agent factory.

    Usage in DAG builder:
        factory_fn = create_searcher_factory(model)
        agent_factory = factory_fn("What is quantum computing?", needs_academic=True)
    """

    def make_factory(sub_question: str, needs_academic: bool = False) -> callable:
        return create_searcher(sub_question, model, include_academic=needs_academic)

    return make_factory


def parse_search_results(msg: Msg) -> list[dict]:
    """Extract search results from a searcher's output message."""
    content = msg.content if hasattr(msg, "content") else str(msg)

    if hasattr(msg, "metadata") and msg.metadata:
        results = msg.metadata.get("search_results", [])
        if results:
            return results

    urls = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("http://") or line.startswith("https://"):
            urls.append({"url": line, "title": "", "content": ""})
        elif "](http" in line:
            try:
                title = line.split("[")[1].split("]")[0]
                url = line.split("(")[1].split(")")[0]
                urls.append({"url": url, "title": title, "content": ""})
            except (IndexError, ValueError):
                continue
    return urls
