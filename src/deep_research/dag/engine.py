"""Async DAG pipeline executor using graphlib.TopologicalSorter."""

from __future__ import annotations

import asyncio
import logging
import time
from graphlib import TopologicalSorter
from typing import Any, Callable

from .nodes import DAGNode, DAGResult, NodeStatus

logger = logging.getLogger(__name__)


class DAGPipeline:
    """Executes a DAG of agent nodes with automatic parallelism.

    Independent nodes run concurrently via asyncio. Dependencies are
    respected using graphlib.TopologicalSorter — a node only starts
    once all its dependencies have completed.

    Args:
        on_progress: Optional async callback fired on node state changes.
            Signature: (node_id, status, data) -> None
        max_concurrency: Maximum number of nodes running in parallel.
        node_timeout: Timeout in seconds for each individual node.
    """

    def __init__(
        self,
        on_progress: Callable[..., Any] | None = None,
        max_concurrency: int = 10,
        node_timeout: float = 120.0,
    ) -> None:
        self._on_progress = on_progress
        self._max_concurrency = max_concurrency
        self._node_timeout = node_timeout

    async def _notify(
        self, node_id: str, status: NodeStatus, data: Any = None
    ) -> None:
        if self._on_progress:
            try:
                await self._on_progress(node_id, status, data)
            except Exception:
                logger.warning("Progress callback failed for %s", node_id, exc_info=True)

    async def _execute_node(
        self,
        node: DAGNode,
        results: dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> Any:
        """Execute a single DAG node."""
        async with semaphore:
            await self._notify(node.id, NodeStatus.RUNNING)

            # Build input from upstream results
            if node.transform:
                upstream = {dep: results[dep] for dep in node.depends_on}
                input_msg = node.transform(upstream)
            elif node.depends_on:
                input_msg = results[node.depends_on[0]]
            else:
                input_msg = None

            # Create and call the agent
            agent = node.agent_factory()
            result = await asyncio.wait_for(
                agent(input_msg),
                timeout=self._node_timeout,
            )
            return result

    async def run(
        self,
        nodes: list[DAGNode],
        seed_results: dict[str, Any] | None = None,
    ) -> DAGResult:
        """Execute the DAG, returning results from all nodes.

        Args:
            nodes: List of DAGNode objects defining the graph.
            seed_results: Pre-populated results (e.g., planner output)
                that nodes can depend on without a corresponding DAGNode.

        Returns:
            DAGResult with outputs, execution order, durations, and failures.
        """
        node_map: dict[str, DAGNode] = {n.id: n for n in nodes}
        results: dict[str, Any] = dict(seed_results or {})
        dag_result = DAGResult()
        semaphore = asyncio.Semaphore(self._max_concurrency)

        # Build dependency graph — only include nodes we need to execute
        graph: dict[str, set[str]] = {}
        for n in nodes:
            # Filter deps to only those that are actual nodes (not seeds)
            graph[n.id] = {d for d in n.depends_on if d in node_map}

        sorter = TopologicalSorter(graph)
        sorter.prepare()

        pending_tasks: dict[str, asyncio.Task] = {}

        while sorter.is_active():
            # Launch all ready nodes
            for node_id in sorter.get_ready():
                # Check that all dependencies (including seeds) have results
                node = node_map[node_id]
                missing = [d for d in node.depends_on if d not in results]
                if missing:
                    logger.error(
                        "Node %s missing dependencies: %s", node_id, missing
                    )
                    dag_result.failed_nodes[node_id] = (
                        f"Missing dependencies: {missing}"
                    )
                    sorter.done(node_id)
                    continue

                task = asyncio.create_task(
                    self._execute_node(node, results, semaphore),
                    name=f"dag-{node_id}",
                )
                pending_tasks[node_id] = task

            if not pending_tasks:
                break

            # Wait for at least one task to complete
            done, _ = await asyncio.wait(
                pending_tasks.values(),
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in done:
                # Find which node this task belongs to
                node_id = next(
                    nid for nid, t in pending_tasks.items() if t is task
                )
                start_time = time.monotonic()
                del pending_tasks[node_id]

                try:
                    result = task.result()
                    results[node_id] = result
                    dag_result.outputs[node_id] = result
                    dag_result.execution_order.append(node_id)
                    dag_result.node_durations[node_id] = (
                        time.monotonic() - start_time
                    )
                    await self._notify(node_id, NodeStatus.COMPLETED, result)
                except asyncio.TimeoutError:
                    error_msg = f"Node {node_id} timed out after {self._node_timeout}s"
                    logger.error(error_msg)
                    dag_result.failed_nodes[node_id] = error_msg
                    await self._notify(node_id, NodeStatus.FAILED, error_msg)
                except Exception as exc:
                    error_msg = f"Node {node_id} failed: {exc}"
                    logger.error(error_msg, exc_info=True)
                    dag_result.failed_nodes[node_id] = str(exc)
                    await self._notify(node_id, NodeStatus.FAILED, str(exc))

                sorter.done(node_id)

        return dag_result
