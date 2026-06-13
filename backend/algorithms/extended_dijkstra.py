"""Dijkstra's Shortest-Path Algorithm — extended with mode/congestion filtering.

Ported from CampusPath and extended with:
- Transport mode filtering via get_edges_for_mode()
- Congestion-aware effective weight
- Blocked edge skipping
- Road type awareness

Uses hand-built MinHeap with decrease_key for O((V+E) log V) performance.
"""

import time
from typing import Any, Dict, List, Optional, Set

from backend.core.nav_graph import NavGraph
from backend.core.min_heap import MinHeap
from backend.core.queue_stack import Stack
from backend.models.transport import TransportMode

INF = float("inf")


def dijkstra(
    graph: NavGraph,
    start_id: str,
    goal_id: str,
    transport_mode: TransportMode = TransportMode.WALKING,
    record_steps: bool = False,
    congestion_threshold: float = float("inf"),
    highway_priority: bool = False,
    blocked_edges: Optional[Set] = None,
) -> Dict[str, Any]:
    """Run Dijkstra's algorithm with mode and congestion awareness.

    Args:
        graph: The navigation graph.
        start_id: Starting node ID.
        goal_id: Target node ID.
        transport_mode: Filter edges by allowed transport mode.
        record_steps: If True, record per-step state for animation.
        congestion_threshold: Edges with congestion_factor > threshold get penalized.
        highway_priority: If True, reduce effective weight of highway edges.
        blocked_edges: Optional set of (from_id, to_id) tuples to treat as blocked.

    Returns:
        Standardized result dict: {path, total_distance, nodes_visited, ...}
    """
    t_start = time.perf_counter()

    if not graph.has_node(start_id):
        raise KeyError(f"Start node '{start_id}' not in graph.")
    if not graph.has_node(goal_id):
        raise KeyError(f"Goal node '{goal_id}' not in graph.")

    if blocked_edges is None:
        blocked_edges = set()

    dist: Dict[str, float] = {}
    prev: Dict[str, Optional[str]] = {}
    visited: Set[str] = set()
    heap = MinHeap()
    steps: List[dict] = []

    for node_id in graph:
        dist[node_id] = INF
        prev[node_id] = None

    dist[start_id] = 0.0
    heap.push(0.0, start_id)

    nodes_visited = 0
    reached = False

    while not heap.is_empty():
        current_dist, current_id = heap.pop()
        if not current_id:
            break
        if current_id in visited:
            continue

        visited.add(current_id)
        nodes_visited += 1

        if current_id == goal_id:
            reached = True
            break

        if record_steps:
            frontier_ids = [heap._heap[i][1] for i in range(1, len(heap._heap))]
            steps.append({
                "current": current_id,
                "frontier": frontier_ids,
                "visited": list(visited),
            })

        for edge in graph.get_edges_for_mode(current_id, transport_mode, skip_blocked=True):
            neighbor_id = edge.to_id
            if neighbor_id in visited:
                continue
            if (current_id, neighbor_id) in blocked_edges:
                continue
            if edge.is_blocked:
                continue

            eff_weight = edge.effective_weight

            # Congestion threshold: penalize edges beyond threshold
            if edge.congestion_factor > congestion_threshold:
                eff_weight *= edge.congestion_factor

            # Highway priority: reduce weight for highways
            if highway_priority and edge.road_type.value == "highway":
                eff_weight *= 0.7

            new_dist = current_dist + eff_weight
            if new_dist < dist[neighbor_id]:
                dist[neighbor_id] = new_dist
                prev[neighbor_id] = current_id
                if heap.contains(neighbor_id):
                    heap.decrease_key(neighbor_id, new_dist)
                else:
                    heap.push(new_dist, neighbor_id)

    path = _reconstruct_path(prev, start_id, goal_id, reached)

    t_end = time.perf_counter()
    execution_time_ms = (t_end - t_start) * 1000.0

    return {
        "path": path,
        "total_distance": dist.get(goal_id, INF),
        "nodes_visited": nodes_visited,
        "execution_time_ms": round(execution_time_ms, 4),
        "steps": steps,
    }


def _reconstruct_path(
    prev: Dict[str, Optional[str]],
    start_id: str,
    goal_id: str,
    reached: bool,
) -> List[str]:
    """Build forward path from start to goal using Stack (LIFO)."""
    if not reached:
        return []

    stack = Stack()
    current = goal_id
    seen = set()
    while current is not None and current not in seen:
        stack.push(current)
        if current == start_id:
            break
        seen.add(current)
        current = prev.get(current)

    path = []
    while not stack.is_empty():
        path.append(stack.pop())

    if path and path[0] == start_id:
        return path
    return []
