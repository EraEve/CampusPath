"""A* Search Algorithm — extended with mode-aware heuristics.

Ported from CampusPath and extended with:
- Transport mode filtering
- Mode-aware heuristic selection
- Congestion and blockage awareness

Three heuristic variants:
1. euclidean — straight-line 2D distance (admissible)
2. manhattan — L1 grid distance (admissible for grid-like maps)
3. floor_aware — Euclidean + vertical floor-change penalty
"""

import math
import time
from typing import Any, Callable, Dict, List, Optional, Set

from ..core.graph import NavGraph
from ..core.min_heap import MinHeap
from ..core.queue_stack import Stack
from ..models.transport import TransportMode

INF = float("inf")
SCALE = 0.8
FLOOR_PENALTY = 20.0


# ---------------------------------------------------------------------------
# Heuristic functions
# ---------------------------------------------------------------------------

def heuristic_euclidean(graph: NavGraph, node_id: str, goal_id: str) -> float:
    """Straight-line Euclidean distance (admissible)."""
    n = graph.get_node(node_id)
    g = graph.get_node(goal_id)
    if n is None or g is None:
        return 0.0
    dx = n.x - g.x
    dy = n.y - g.y
    return math.sqrt(dx * dx + dy * dy) * SCALE


def heuristic_manhattan(graph: NavGraph, node_id: str, goal_id: str) -> float:
    """Manhattan (L1) grid distance (admissible for grid maps)."""
    n = graph.get_node(node_id)
    g = graph.get_node(goal_id)
    if n is None or g is None:
        return 0.0
    return (abs(n.x - g.x) + abs(n.y - g.y)) * SCALE


def heuristic_floor_aware(graph: NavGraph, node_id: str, goal_id: str) -> float:
    """2D Euclidean + vertical floor-change penalty.

    KEY INNOVATION: Guides search toward nearest vertical connector
    when navigating across floors.
    """
    n = graph.get_node(node_id)
    g = graph.get_node(goal_id)
    if n is None or g is None:
        return 0.0
    dx = n.x - g.x
    dy = n.y - g.y
    h_2d = math.sqrt(dx * dx + dy * dy) * SCALE
    h_floor = abs(n.floor - g.floor) * FLOOR_PENALTY
    return h_2d + h_floor


HEURISTICS: Dict[str, Callable] = {
    "euclidean": heuristic_euclidean,
    "manhattan": heuristic_manhattan,
    "floor_aware": heuristic_floor_aware,
}


# ---------------------------------------------------------------------------
# A* Algorithm
# ---------------------------------------------------------------------------

def a_star(
    graph: NavGraph,
    start_id: str,
    goal_id: str,
    heuristic: str = "euclidean",
    transport_mode: TransportMode = TransportMode.WALKING,
    record_steps: bool = False,
    highway_priority: bool = False,
    blocked_edges: Optional[Set] = None,
) -> Dict[str, Any]:
    """Run A* search with mode-aware heuristics.

    Args:
        graph: The navigation graph.
        start_id: Starting node ID.
        goal_id: Target node ID.
        heuristic: "euclidean", "manhattan", or "floor_aware".
        transport_mode: Filter edges by allowed transport mode.
        record_steps: If True, record per-step state.
        highway_priority: If True, reduce effective weight of highways.
        blocked_edges: Optional set of (from_id, to_id) to treat as blocked.

    Returns:
        Standardized result dict.
    """
    t_start = time.perf_counter()

    if not graph.has_node(start_id):
        raise KeyError(f"Start node '{start_id}' not in graph.")
    if not graph.has_node(goal_id):
        raise KeyError(f"Goal node '{goal_id}' not in graph.")
    if heuristic not in HEURISTICS:
        raise ValueError(f"Unknown heuristic '{heuristic}'. Choose: {list(HEURISTICS.keys())}")

    h_func = HEURISTICS[heuristic]
    if blocked_edges is None:
        blocked_edges = set()

    g_score: Dict[str, float] = {}
    prev: Dict[str, Optional[str]] = {}
    closed: Set[str] = set()
    heap = MinHeap()
    steps: List[dict] = []

    for node_id in graph:
        g_score[node_id] = INF
        prev[node_id] = None

    g_score[start_id] = 0.0
    h_start = h_func(graph, start_id, goal_id)
    heap.push(h_start, start_id)

    nodes_visited = 0
    reached = False

    while not heap.is_empty():
        f_current, current_id = heap.pop()
        if not current_id:
            break
        if current_id in closed:
            continue

        if current_id == goal_id:
            reached = True
            break

        closed.add(current_id)
        nodes_visited += 1
        current_g = g_score[current_id]

        if record_steps:
            frontier_ids = [heap._heap[i][1] for i in range(1, len(heap._heap))]
            steps.append({
                "current": current_id,
                "frontier": frontier_ids,
                "visited": list(closed),
                "f_current": f_current,
                "g_current": current_g,
            })

        for edge in graph.get_edges_for_mode(current_id, transport_mode, skip_blocked=True):
            neighbor_id = edge.to_id
            if neighbor_id in closed:
                continue
            if (current_id, neighbor_id) in blocked_edges:
                continue

            eff_weight = edge.effective_weight
            if highway_priority and edge.road_type.value == "highway":
                eff_weight *= 0.7

            tentative_g = current_g + eff_weight
            if tentative_g < g_score[neighbor_id]:
                g_score[neighbor_id] = tentative_g
                prev[neighbor_id] = current_id
                f_score = tentative_g + h_func(graph, neighbor_id, goal_id)
                if heap.contains(neighbor_id):
                    heap.decrease_key(neighbor_id, f_score)
                else:
                    heap.push(f_score, neighbor_id)

    path = _reconstruct_path(prev, start_id, goal_id, reached)

    t_end = time.perf_counter()

    return {
        "path": path,
        "total_distance": g_score.get(goal_id, INF),
        "nodes_visited": nodes_visited,
        "execution_time_ms": round((t_end - t_start) * 1000.0, 4),
        "steps": steps,
        "heuristic": heuristic,
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
