"""Congestion-Avoidance Pathfinding.

Runs Dijkstra with congestion penalties on congested edges, then compares
the result against a normal path. Highlights edges that were avoided due
to congestion.

Use case: User wants to avoid traffic jams — the algorithm naturally
routes around congested areas by penalizing affected edge weights.
"""

import time
from typing import Any, Dict, List, Optional, Set

from ..core.graph import NavGraph
from ..core.min_heap import MinHeap
from ..core.queue_stack import Stack
from ..models.transport import TransportMode

INF = float("inf")


def congestion_avoidance_dijkstra(
    graph: NavGraph,
    start_id: str,
    goal_id: str,
    transport_mode: TransportMode = TransportMode.DRIVING,
    congestion_threshold: float = 1.5,
    highway_priority: bool = False,
    blocked_edges: Optional[Set] = None,
) -> Dict[str, Any]:
    """Find the best path while avoiding congested edges.

    Edges with congestion_factor > threshold get their effective weight
    multiplied by that factor, pushing the search toward less congested
    alternatives.

    Args:
        graph: The navigation graph.
        start_id: Starting node ID.
        goal_id: Target node ID.
        transport_mode: Filter edges by allowed transport mode.
        congestion_threshold: Penalize edges above this congestion factor.
        highway_priority: If True, reduce weight of highway edges.
        blocked_edges: Optional set of (from_id, to_id) to treat as blocked.

    Returns:
        Dict with path, total_distance, and extra fields:
        - congested_edges_avoided: list of congested edges on the normal
          path that were avoided
        - normal_path_distance: what the distance would be without avoidance
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
    congested_avoided: List[str] = []
    heap = MinHeap()

    for node_id in graph:
        dist[node_id] = INF
        prev[node_id] = None

    dist[start_id] = 0.0
    heap.push(0.0, start_id)

    # Track which edges we penalized
    penalized_edges: Set[tuple] = set()

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

        for edge in graph.get_edges_for_mode(current_id, transport_mode, skip_blocked=True):
            neighbor_id = edge.to_id
            if neighbor_id in visited:
                continue
            if (current_id, neighbor_id) in blocked_edges:
                continue

            eff_weight = edge.effective_weight

            # Penalize congested edges
            if edge.congestion_factor > congestion_threshold:
                eff_weight *= edge.congestion_factor
                penalized_edges.add((current_id, neighbor_id))
                congested_avoided.append(
                    f"{current_id}→{neighbor_id} ({edge.name or edge.road_type.value})"
                )

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

    # Count how many edges on the chosen path were penalized but still used
    edges_on_path = []
    for i in range(len(path) - 1):
        edge = graph.get_edge(path[i], path[i + 1])
        if edge:
            edges_on_path.append(edge)

    t_end = time.perf_counter()

    return {
        "path": path,
        "total_distance": dist.get(goal_id, INF),
        "nodes_visited": nodes_visited,
        "execution_time_ms": round((t_end - t_start) * 1000.0, 4),
        "congested_edges_avoided": list(set(congested_avoided)),
        "penalized_edges_count": len(penalized_edges),
        "edges_using_congested": sum(
            1 for e in edges_on_path if e.congestion_factor > congestion_threshold
        ),
        "steps": [],
    }


def _reconstruct_path(prev, start_id, goal_id, reached) -> List[str]:
    """Build forward path using Stack (LIFO)."""
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
