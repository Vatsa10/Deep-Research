"""DAG node definitions for the research pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class DAGNode:
    """A node in the research DAG that wraps an agent call.

    Attributes:
        id: Unique identifier for this node (e.g., "searcher_0", "reader_1").
        agent_factory: Callable that creates and returns an agent. Called lazily
            when the node is ready to execute.
        depends_on: List of node IDs that must complete before this node runs.
        transform: Optional callable that takes a dict of upstream node results
            (keyed by node ID) and returns the input message for this node's agent.
            If None, the first dependency's result is passed directly.
        label: Human-readable label for display (e.g., "Search: quantum computing").
        agent_type: Type name for frontend display (e.g., "searcher", "reader").
    """

    id: str
    agent_factory: Callable[[], Any]
    depends_on: list[str] = field(default_factory=list)
    transform: Callable[[dict[str, Any]], Any] | None = None
    label: str = ""
    agent_type: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            self.label = self.id


@dataclass
class DAGResult:
    """Result of a complete DAG execution.

    Attributes:
        outputs: Dict mapping node IDs to their output messages.
        execution_order: List of node IDs in the order they completed.
        node_durations: Dict mapping node IDs to execution duration in seconds.
        failed_nodes: Dict mapping failed node IDs to their error messages.
    """

    outputs: dict[str, Any] = field(default_factory=dict)
    execution_order: list[str] = field(default_factory=list)
    node_durations: dict[str, float] = field(default_factory=dict)
    failed_nodes: dict[str, str] = field(default_factory=dict)
