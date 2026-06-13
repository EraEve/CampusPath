"""Incremental Rerouting on Blockage.

When a vehicle encounters a blockage or deviation from the planned path,
this module finds a new route from the current position to the original
goal, excluding blocked edges.

Key function: reroute_from_position()
1. Find the node on the original path closest to current position
2. Run Dijkstra from that node to goal with blocked edges excluded
3. Return the merged path: [already_traversed_prefix] + [new_reroute]
"""

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from ..core.graph import NavGraph
from ..core.min_heap import MinHeap
from ..core.queue_stack import Stack
from ..models.transport import TransportMode

INF = float("inf")


def reroute_from_position(
    graph: NavGraph,
    original_path: List[str],
    current_node_id: str,
    goal_id: str,
    transport_mode: TransportMode = TransportMode.DRIVING,
    blocked_edges: Optional[Set[Tuple[str, str]]] = None,
) -> Dict[str, Any]:
    """Reroute from current position to goal, avoiding blocked edges.

    Args:
        graph: The navigation graph.
        original_path: The originally planned path (node IDs).
        current_node_id: The node where the vehicle currently is.
        goal_id: The ultimate destination.
        transport_mode: Transport mode for rerouting.
        blocked_edges: Set of (from_id, to_id) tuples that are blocked.

    Returns:
        Dict with:
        - path: merged path (traversed + rerouted)
        - original_path: the original path (for comparison)
        - deviation_node: where the reroute diverges
        - total_distance: distance of the new merged path
        - reroute_distance: distance of just the rerouted segment
        - blocked_edges_avoided: list of blocked edges that were avoided
    """
    t_start = time.perf_counter()

    if blocked_edges is None:
        blocked_edges = set()

    if not original_path:
        return {"path": [], "error": "No original path provided"}

    # Find where we are in the original path
    traversed = []
    try:
        idx = original_path.index(current_node_id)
        traversed = original_path[:idx + 1]
    except ValueError:
        # Current node not on path — find nearest
        traversed = [original_path[0]]
        current_node_id = original_path[0]

    # Run Dijkstra from current to goal, excluding blocked edges
    dist, prev, reached = _dijkstra_with_blocked(
        graph, current_node_id, goal_id, transport_mode, blocked_edges
    )

    # Reconstruct reroute segment
    reroute_segment = _reconstruct_path(prev, current_node_id, goal_id, reached)

    # Merge: traversed (minus last to avoid duplicate) + reroute
    if len(traversed) > 1:
        merged = traversed[:-1] + reroute_segment
    else:
        merged = reroute_segment

    # Compute distances
    reroute_dist = sum(
        graph.get_weight(reroute_segment[i], reroute_segment[i + 1])
        for i in range(len(reroute_segment) - 1)
        if graph.get_weight(reroute_segment[i], reroute_segment[i + 1]) < INF
    )

    total_dist = sum(
        graph.get_weight(merged[i], merged[i + 1])
        for i in range(len(merged) - 1)
        if graph.get_weight(merged[i], merged[i + 1]) < INF
    )

    blocked_list = [f"{f}→{t}" for f, t in blocked_edges]

    t_end = time.perf_counter()

    return {
        "path": merged,
        "original_path": original_path,
        "deviation_node": current_node_id,
        "total_distance": total_dist,
        "reroute_distance": reroute_dist,
        "reroute_segment": reroute_segment,
        "traversed": traversed,
        "blocked_edges_avoided": blocked_list,
        "nodes_visited": len(dist),
        "execution_time_ms": round((t_end - t_start) * 1000.0, 4),
    }


def _dijkstra_with_blocked(
    graph: NavGraph,
    start_id: str,
    goal_id: str,
    transport_mode: TransportMode,
    blocked_edges: Set[Tuple[str, str]],
) -> Tuple[Dict[str, float], Dict[str, Optional[str]], bool]:
    """Standard Dijkstra with blocked edges excluded. Returns (dist, prev, reached)."""
    dist: Dict[str, float] = {}
    prev: Dict[str, Optional[str]] = {}
    visited: Set[str] = set()
    heap = MinHeap()

    for node_id in graph:
        dist[node_id] = INF
        prev[node_id] = None

    dist[start_id] = 0.0
    heap.push(0.0, start_id)
    reached = False

    while not heap.is_empty():
        current_dist, current_id = heap.pop()
        if not current_id or current_id in visited:
            continue

        visited.add(current_id)

        if current_id == goal_id:
            reached = True
            break

        for edge in graph.get_edges_for_mode(current_id, transport_mode, skip_blocked=True):
            neighbor_id = edge.to_id
            if neighbor_id in visited:
                continue
            if (current_id, neighbor_id) in blocked_edges:
                continue

            new_dist = current_dist + edge.effective_weight
            if new_dist < dist[neighbor_id]:
                dist[neighbor_id] = new_dist
                prev[neighbor_id] = current_id
                if heap.contains(neighbor_id):
                    heap.decrease_key(neighbor_id, new_dist)
                else:
                    heap.push(new_dist, neighbor_id)

    return dist, prev, reached


def find_nearest_path_node(
    graph: NavGraph,
    path: List[str],
    x: float,
    y: float,
) -> Optional[str]:
    """Find the node on the path closest to the given (x, y) position.

    Used for deviation detection: when the vehicle is off-path,
    find the nearest path node to restart routing from.

    Args:
        graph: The navigation graph.
        path: The planned path of node IDs.
        x, y: Current position coordinates.

    Returns:
        The node ID on the path closest to (x, y), or None.
    """
    if not path:
        return None

    best_node = None
    best_dist = float("inf")

    for node_id in path:
        node = graph.get_node(node_id)
        if node is None:
            continue
        dx = node.x - x
        dy = node.y - y
        d = dx * dx + dy * dy
        if d < best_dist:
            best_dist = d
            best_node = node_id

    return best_node


def _reconstruct_path(prev, start_id, goal_id, reached) -> List[str]:
    """Build forward path using Stack."""
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
