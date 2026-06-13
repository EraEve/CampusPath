"""Breadth-First Search — extended with mode filtering.

Finds the path with the fewest edges. Now supports transport mode filtering
so BFS respects road-type restrictions.

Ported from CampusPath and extended with mode/congestion awareness.
"""

import time
from typing import Any, Dict, List, Optional, Set

from ..core.graph import NavGraph
from ..core.queue_stack import Queue, Stack
from ..models.transport import TransportMode

INF = float("inf")


def bfs_shortest_path(
    graph: NavGraph,
    start_id: str,
    goal_id: str,
    transport_mode: TransportMode = TransportMode.WALKING,
    record_steps: bool = False,
    blocked_edges: Optional[Set] = None,
) -> Dict[str, Any]:
    """Find the path with the fewest edges using BFS.

    This is an UNWEIGHTED search. Edge weights are ignored for the search
    but summed for the reported total_distance (for fair comparison).

    Args:
        graph: The navigation graph.
        start_id: Starting node ID.
        goal_id: Target node ID.
        transport_mode: Filter edges by allowed transport mode.
        record_steps: If True, record per-step state.
        blocked_edges: Optional set of (from_id, to_id) to treat as blocked.

    Returns:
        Standardized result dict.
    """
    t_start = time.perf_counter()

    if not graph.has_node(start_id):
        raise KeyError(f"Start node '{start_id}' not in graph.")
    if not graph.has_node(goal_id):
        raise KeyError(f"Goal node '{goal_id}' not in graph.")

    if blocked_edges is None:
        blocked_edges = set()

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

        if current_id == goal_id:
            reached = True
            break

        if record_steps:
            frontier = [queue._items[i] for i in range(queue._head, len(queue._items))]
            steps.append({
                "current": current_id,
                "frontier": frontier,
                "visited": list(visited),
            })

        for edge in graph.get_edges_for_mode(current_id, transport_mode, skip_blocked=True):
            neighbor_id = edge.to_id
            if neighbor_id not in visited:
                if (current_id, neighbor_id) in blocked_edges:
                    continue
                visited.add(neighbor_id)
                prev[neighbor_id] = current_id
                queue.enqueue(neighbor_id)

    path = _reconstruct_path(prev, start_id, goal_id, reached)

    # Compute actual weighted distance along the BFS path
    total_weight = 0.0
    for i in range(len(path) - 1):
        w = graph.get_weight(path[i], path[i + 1])
        total_weight += w if w < INF else 0.0

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
