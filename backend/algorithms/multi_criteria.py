"""Multi-Criteria Pathfinding.

Finds optimal paths based on weighted combination of distance, time, and cost.

The composite edge cost is:
  f(edge) = w_distance * distance
          + w_time * (distance / speed_limit)    [if speed_limit > 0]
          + w_cost * toll_factor

Users can adjust weights via sliders to emphasize different criteria:
- Distance-first: w_distance=1.0, w_time=0.0, w_cost=0.0
- Time-first: w_distance=0.0, w_time=1.0, w_cost=0.0
- Cost-first: w_distance=0.0, w_time=0.0, w_cost=1.0
- Balanced: w_distance=0.4, w_time=0.4, w_cost=0.2

Uses weighted-sum approach (simpler than true Pareto optimization)
which is sufficient for demonstrating the concept and fast enough
for interactive use.
"""

import time
from typing import Any, Dict, List, Optional, Set

from backend.core.nav_graph import NavGraph
from backend.core.min_heap import MinHeap
from backend.core.queue_stack import Stack
from backend.models.transport import TransportMode

INF = float("inf")

# Default walking speed in km/h when no speed limit is specified
DEFAULT_WALK_SPEED = 5.0       # 5 km/h walking pace
DEFAULT_DRIVING_SPEED = 40.0   # 40 km/h default driving speed
DEFAULT_TOLL_COST_PER_KM = 1.0  # 1 cost unit per km on highways


def multi_criteria_dijkstra(
    graph: NavGraph,
    start_id: str,
    goal_id: str,
    transport_mode: TransportMode = TransportMode.DRIVING,
    w_distance: float = 0.4,
    w_time: float = 0.4,
    w_cost: float = 0.2,
    blocked_edges: Optional[Set] = None,
) -> Dict[str, Any]:
    """Find the optimal path using weighted multi-criteria objective.

    Args:
        graph: The navigation graph.
        start_id: Starting node ID.
        goal_id: Target node ID.
        transport_mode: Filter edges by allowed transport mode.
        w_distance: Weight for distance criterion (0.0 - 1.0).
        w_time: Weight for time criterion (0.0 - 1.0).
        w_cost: Weight for cost criterion (0.0 - 1.0).
        blocked_edges: Optional set of (from_id, to_id) to treat as blocked.

    Returns:
        Dict with path, total_distance, total_time, total_cost, etc.
    """
    t_start = time.perf_counter()

    if not graph.has_node(start_id):
        raise KeyError(f"Start node '{start_id}' not in graph.")
    if not graph.has_node(goal_id):
        raise KeyError(f"Goal node '{goal_id}' not in graph.")

    if blocked_edges is None:
        blocked_edges = set()

    # Normalize weights
    total_w = w_distance + w_time + w_cost
    if total_w == 0:
        w_distance = 1.0
        total_w = 1.0
    w_distance /= total_w
    w_time /= total_w
    w_cost /= total_w

    # Composite score: Dict[str, (composite, distance, time, cost)]
    comp: Dict[str, float] = {}
    prev: Dict[str, Optional[str]] = {}
    visited: Set[str] = set()
    heap = MinHeap()

    # Track per-criterion accumulators for path reporting
    acc_dist: Dict[str, float] = {}
    acc_time: Dict[str, float] = {}
    acc_cost: Dict[str, float] = {}

    for node_id in graph:
        comp[node_id] = INF
        prev[node_id] = None
        acc_dist[node_id] = 0.0
        acc_time[node_id] = 0.0
        acc_cost[node_id] = 0.0

    comp[start_id] = 0.0
    heap.push(0.0, start_id)

    nodes_visited = 0
    reached = False

    while not heap.is_empty():
        current_comp, current_id = heap.pop()
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

            # Distance component
            dist_val = edge.effective_weight  # meters

            # Time component: distance / speed → seconds
            speed = edge.speed_limit if edge.speed_limit > 0 else _default_speed(transport_mode)
            speed_ms = speed / 3.6  # km/h → m/s
            time_val = dist_val / speed_ms if speed_ms > 0 else dist_val / 1.4  # ~5 km/h

            # Cost component: toll on highways
            cost_val = 0.0
            if edge.road_type.value == "highway":
                cost_val = (dist_val / 1000.0) * DEFAULT_TOLL_COST_PER_KM
            elif edge.road_type.value in ("main_road",):
                cost_val = (dist_val / 1000.0) * 0.2  # small cost on main roads

            # Weighted composite
            composite = (
                w_distance * (dist_val / 100.0) +   # normalize to ~0-10 range
                w_time * (time_val / 60.0) +         # normalize to minutes
                w_cost * cost_val
            )

            new_comp = current_comp + composite
            if new_comp < comp[neighbor_id]:
                comp[neighbor_id] = new_comp
                prev[neighbor_id] = current_id
                acc_dist[neighbor_id] = acc_dist[current_id] + dist_val
                acc_time[neighbor_id] = acc_time[current_id] + time_val
                acc_cost[neighbor_id] = acc_cost[current_id] + cost_val
                if heap.contains(neighbor_id):
                    heap.decrease_key(neighbor_id, new_comp)
                else:
                    heap.push(new_comp, neighbor_id)

    path = _reconstruct_path(prev, start_id, goal_id, reached)

    t_end = time.perf_counter()

    return {
        "path": path,
        "total_distance": acc_dist.get(goal_id, 0.0),
        "total_time": acc_time.get(goal_id, 0.0),
        "total_cost": acc_cost.get(goal_id, 0.0),
        "nodes_visited": nodes_visited,
        "execution_time_ms": round((t_end - t_start) * 1000.0, 4),
        "weights": {"distance": w_distance, "time": w_time, "cost": w_cost},
        "steps": [],
    }


def _default_speed(mode: TransportMode) -> float:
    """Return default speed in km/h for a transport mode."""
    speeds = {
        TransportMode.WALKING: DEFAULT_WALK_SPEED,
        TransportMode.DRIVING: DEFAULT_DRIVING_SPEED,
        TransportMode.BUS: 30.0,
        TransportMode.SUBWAY: 55.0,
        TransportMode.TRAIN: 80.0,
    }
    return speeds.get(mode, DEFAULT_WALK_SPEED)


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
