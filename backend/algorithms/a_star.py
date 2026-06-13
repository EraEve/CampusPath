"""A* Search Algorithm with three heuristic variants.

A* improves upon Dijkstra by using a heuristic function h(n) that estimates
the remaining distance from node n to the goal. The priority queue orders by
f(n) = g(n) + h(n), where g(n) is the known distance from start.

When h(n) is admissible (never overestimates), A* guarantees optimal paths
while exploring fewer nodes than Dijkstra on average.

Three heuristic variants are provided:
1. euclidean  — straight-line 2D distance (admissible)
2. manhattan  — grid-based distance, L1 norm (admissible for grid-like plans)
3. floor_aware — 2D Euclidean + vertical floor-change penalty (admissible)

The floor_aware heuristic is the key innovation: it guides the search
toward the correct stair/elevator when navigating across floors, by
adding abs(Δfloor) × FLOOR_PENALTY meters to the 2D estimate.

Returns the standardized result dict used across all algorithms.
"""

import math
import time
from typing import Any, Callable, Dict, List, Optional, Set

from .min_heap import MinHeap
from .queue_stack import Stack
from backend.models.graph import AdjacencyListGraph
from backend.models.node import Node

INF = float("inf")

# Heuristic scaling: normalized coordinates (0-100) represent roughly
# 80m × 50m physical space. 1 unit ≈ 0.8m.
SCALE = 0.8

# Floor penalty: each floor change adds ~20m equivalent distance
# (walking up/down stairs, waiting for elevator).
FLOOR_PENALTY = 2.0   # Must be ≤ minimum vertical transition cost (elevator=2m)


# ---------------------------------------------------------------------------
# Heuristic functions
# ---------------------------------------------------------------------------

def heuristic_euclidean(graph: AdjacencyListGraph, node_id: str,
                        goal_id: str) -> float:
    """Straight-line 2D Euclidean distance.

    Admissible because the shortest possible path between two points
    in Euclidean space is a straight line. Corridor constraints can
    only make the actual path longer, not shorter.
    """
    n = graph.get_node(node_id)
    g = graph.get_node(goal_id)
    if n is None or g is None:
        return 0.0
    dx = n.x - g.x
    dy = n.y - g.y
    return math.sqrt(dx * dx + dy * dy) * SCALE


def heuristic_manhattan(graph: AdjacencyListGraph, node_id: str,
                        goal_id: str) -> float:
    """Manhattan (L1) distance on a grid.

    Admissible for buildings where corridors form a grid (orthogonal
    hallways). Each axis movement costs at least the straight-line
    component, so L1 ≤ true distance.
    """
    n = graph.get_node(node_id)
    g = graph.get_node(goal_id)
    if n is None or g is None:
        return 0.0
    return (abs(n.x - g.x) + abs(n.y - g.y)) * SCALE


def heuristic_floor_aware(graph: AdjacencyListGraph, node_id: str,
                          goal_id: str) -> float:
    """2D Euclidean distance + vertical floor-change penalty.

    KEY INNOVATION for multi-floor navigation:
    - On the same floor: identical to euclidean.
    - Across floors: adds floor_diff × FLOOR_PENALTY to bias the
      search toward the nearest vertical connector (stair/elevator).

    This is admissible because:
    1. The 2D Euclidean component ≤ true horizontal distance.
    2. The floor penalty (20m) ≤ actual cost of climbing stairs
       (6m vertical × 3× effort multiplier ≈ 18m + horizontal
       approach distance).
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


# Registry of available heuristics (for API and frontend dropdown)
HEURISTICS: Dict[str, Callable] = {
    "euclidean": heuristic_euclidean,
    "manhattan": heuristic_manhattan,
    "floor_aware": heuristic_floor_aware,
}


# ---------------------------------------------------------------------------
# A* Algorithm
# ---------------------------------------------------------------------------

def a_star(
    graph: AdjacencyListGraph,
    start_id: str,
    goal_id: str,
    heuristic: str = "euclidean",
    record_steps: bool = False,
) -> Dict[str, Any]:
    """Run A* search with the specified heuristic.

    Args:
        graph: The building graph.
        start_id: Starting node ID.
        goal_id: Target node ID.
        heuristic: One of "euclidean", "manhattan", "floor_aware".
        record_steps: If True, record per-step state for animation.

    Returns:
        Standardized result dict with path, distance, nodes_visited, etc.
    """
    t_start = time.perf_counter()

    # Validate
    if not graph.has_node(start_id):
        raise KeyError(f"Start node '{start_id}' not in graph.")
    if not graph.has_node(goal_id):
        raise KeyError(f"Goal node '{goal_id}' not in graph.")
    if heuristic not in HEURISTICS:
        raise ValueError(
            f"Unknown heuristic '{heuristic}'. "
            f"Choose from: {list(HEURISTICS.keys())}"
        )

    h_func = HEURISTICS[heuristic]

    # ------------------------------------------------------------------
    # Data structures:
    # - g_score: HashMap<str, float>  → actual distance from start
    # - prev: HashMap<str, str|None>  → predecessor for path reconstruction
    # - closed: Set<str>              → nodes already expanded
    # - heap: MinHeap                 → frontier ordered by f(n)=g(n)+h(n)
    # ------------------------------------------------------------------
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
    heap.push(h_start, start_id)  # f(start) = 0 + h(start)

    nodes_visited = 0
    reached = False

    while not heap.is_empty():
        f_current, current_id = heap.pop()

        if not current_id:
            break

        # The heap priority is f = g + h. We need the actual g_score
        # from our HashMap — the heap priority is only for ordering.
        if current_id in closed:
            continue

        # Goal check: when we pop the goal, we've found the optimal path
        if current_id == goal_id:
            reached = True
            break

        closed.add(current_id)
        nodes_visited += 1

        current_g = g_score[current_id]

        # Record step
        if record_steps:
            frontier_ids = []
            for i in range(1, len(heap._heap)):
                frontier_ids.append(heap._heap[i][1])
            steps.append({
                "current": current_id,
                "frontier": frontier_ids,
                "visited": list(closed),
                "f_current": f_current,
                "g_current": current_g,
            })

        for neighbor_id, weight in graph.get_neighbors(current_id):
            if neighbor_id in closed:
                continue
            tentative_g = current_g + weight
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
    """Build forward path using Stack (LIFO) for reversal."""
    if not reached:
        return []

    stack = Stack()
    current = goal_id
    seen = set()  # guard against cycles (shouldn't happen, but safe)
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
