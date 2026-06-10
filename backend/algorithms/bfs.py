"""Breadth-First Search for unweighted shortest paths.

BFS finds the path with the fewest edges between start and goal.
It ignores edge weights, treating every edge as cost 1.

This serves as the BASELINE for algorithm comparison:
- On unweighted graphs, BFS is optimal (minimum edges).
- On weighted graphs, BFS may find a suboptimal path (more edges
  but shorter total distance). This contrast demonstrates WHY
  weighted algorithms (Dijkstra, A*) are necessary for realistic
  building navigation where corridors have different lengths.

Uses the hand-built Queue ADT (FIFO) and Stack (LIFO) for path
reconstruction — all core data structures are custom.
"""

import time
from typing import Any, Dict, List, Optional, Set

from .queue_stack import Queue, Stack
from ..models.graph import AdjacencyListGraph


INF = float("inf")


def bfs_shortest_path(
    graph: AdjacencyListGraph,
    start_id: str,
    goal_id: str,
    record_steps: bool = False,
) -> Dict[str, Any]:
    """Find the path with the fewest edges using BFS.

    Note: This is an UNWEIGHTED search. Edge weights are ignored.
    Use Dijkstra or A* for weighted shortest paths.

    Args:
        graph: The building graph.
        start_id: Starting node ID.
        goal_id: Target node ID.
        record_steps: If True, record per-step state for animation.

    Returns:
        Standardized result dict.
        total_distance here is the SUM OF ACTUAL EDGE WEIGHTS along
        the BFS path (for fair comparison), NOT the number of edges.
    """
    t_start = time.perf_counter()

    if not graph.has_node(start_id):
        raise KeyError(f"Start node '{start_id}' not in graph.")
    if not graph.has_node(goal_id):
        raise KeyError(f"Goal node '{goal_id}' not in graph.")

    # ------------------------------------------------------------------
    # Data structures:
    # - queue: Queue (FIFO)       → frontier, ordered by discovery time
    # - prev: HashMap<str, str>   → predecessor for path reconstruction
    # - visited: Set<str>         → nodes already discovered/expanded
    # ------------------------------------------------------------------
    queue = Queue()
    prev: Dict[str, Optional[str]] = {}
    visited: Set[str] = set()
    steps: List[dict] = []

    for node_id in graph:
        prev[node_id] = None

    queue.enqueue(start_id)
    visited.add(start_id)

    nodes_visited = 0
    reached = False

    while not queue.is_empty():
        current_id = queue.dequeue()
        if current_id is None:
            break

        nodes_visited += 1

        # Goal check at expansion time
        if current_id == goal_id:
            reached = True
            break

        # Record step
        if record_steps:
            frontier = []
            # Build frontier snapshot (approximate from queue internals)
            for i in range(queue._head, len(queue._items)):
                frontier.append(queue._items[i])
            steps.append({
                "current": current_id,
                "frontier": frontier,
                "visited": list(visited),
            })

        for neighbor_id, _weight in graph.get_neighbors(current_id):
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                prev[neighbor_id] = current_id
                queue.enqueue(neighbor_id)

    # Reconstruct path
    path = _reconstruct_path(prev, start_id, goal_id, reached)

    # Compute actual weighted distance along the BFS path
    total_weight = 0.0
    for i in range(len(path) - 1):
        w = graph.get_weight(path[i], path[i + 1])
        total_weight += w if w >= 0 else 0.0

    t_end = time.perf_counter()

    return {
        "path": path,
        "total_distance": total_weight,
        "nodes_visited": nodes_visited,
        "execution_time_ms": round((t_end - t_start) * 1000.0, 4),
        "steps": steps,
    }


def _reconstruct_path(
    prev: Dict[str, Optional[str]],
    start_id: str,
    goal_id: str,
    reached: bool,
) -> List[str]:
    """Build forward path using Stack (LIFO)."""
    if not reached:
        return []

    stack = Stack()
    current = goal_id
    while current is not None:
        stack.push(current)
        if current == start_id:
            break
        current = prev.get(current)

    path = []
    while not stack.is_empty():
        path.append(stack.pop())

    if path and path[0] == start_id:
        return path
    return []
