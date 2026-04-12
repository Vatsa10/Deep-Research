"""ReaderAgent: Fetches and extracts content from web sources."""

from __future__ import annotations

from pathlib import Path

from agentscope.agent import ReActAgent
from agentscope.tool import Toolkit

from ..tools.web_reader import fetch_url

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "reader.md"


def create_reader(model: object) -> callable:
    """Factory that returns a callable creating a ReaderAgent.

    The returned callable creates a fresh agent instance each time,
    suitable for use as a DAGNode.agent_factory.
    """

    def factory() -> ReActAgent:
        toolkit = Toolkit()
        toolkit.register_tool_function(fetch_url)

        sys_prompt = PROMPT_PATH.read_text(encoding="utf-8")

        agent = ReActAgent(
            name="Reader",
            sys_prompt=sys_prompt,
            model=model,
            toolkit=toolkit,
            max_iters=2,
        )
        return agent

    return factory


def create_reader_factory(model: object) -> callable:
    """Returns a function that returns an agent factory.

    Usage in DAG builder:
        factory_fn = create_reader_factory(model)
        agent_factory = factory_fn()
        # agent_factory() creates the actual agent
    """

    def make_factory() -> callable:
        return create_reader(model)

    return make_factory
