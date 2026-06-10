"""Dijkstra's Shortest-Path Algorithm with hand-built MinHeap.

Finds the minimum-weight path from start_id to goal_id in a weighted,
directed graph with non-negative edge weights.

Implementation highlights for the Data Structures course:
1. Uses MinHeap (not heapq) with O(log n) decrease_key for O((V+E) log V).
2. HashMap 'dist' for O(1) distance lookup.
3. HashMap 'prev' for O(1) predecessor lookup during path reconstruction.
4. Stack (LIFO) used in reconstruct_path to reverse the predecessor chain.
5. Early exit when the goal node is popped from the heap.
6. Optional step recording for frontend animation.

Returns a standardized result dict consumed by all algorithms for
fair comparison in the experiment framework.
"""

import time
from typing import Any, Dict, List, Optional, Set

from .min_heap import MinHeap
from .queue_stack import Stack
from ..models.graph import AdjacencyListGraph

INF = float("inf")


def dijkstra(
    graph: AdjacencyListGraph,
    start_id: str,
    goal_id: str,
    record_steps: bool = False,
) -> Dict[str, Any]:
    """Run Dijkstra's algorithm on a weighted graph.

    Args:
        graph: The building graph (adjacency list).
        start_id: ID of the starting node.
        goal_id: ID of the target node.
        record_steps: If True, record per-step state for animation.

    Returns:
        {
            "path": List[str],           # ordered node_ids from start to goal
            "total_distance": float,     # sum of edge weights (INF if unreachable)
            "nodes_visited": int,        # nodes popped from the frontier
            "execution_time_ms": float,  # wall-clock time in milliseconds
            "steps": List[dict],         # per-step state (empty if not recorded)
        }
    """
    t_start = time.perf_counter()

    # Validate inputs
    if not graph.has_node(start_id):
        raise KeyError(f"Start node '{start_id}' not in graph.")
    if not graph.has_node(goal_id):
        raise KeyError(f"Goal node '{goal_id}' not in graph.")

    # ------------------------------------------------------------------
    # Data structures used (documented for course report):
    # - dist: HashMap<str, float>  → shortest known distance to each node
    # - prev: HashMap<str, str|None> → predecessor in optimal path
    # - visited: Set<str>          → nodes whose optimal distance is known
    # - heap: MinHeap              → frontier ordered by dist
    # - steps: List<dict>          → animation trace
    # ------------------------------------------------------------------
    dist: Dict[str, float] = {}
    prev: Dict[str, Optional[str]] = {}
    visited: Set[str] = set()
    heap = MinHeap()
    steps: List[dict] = []

    # Initialize distances
    for node_id in graph:
        dist[node_id] = INF
        prev[node_id] = None

    dist[start_id] = 0.0
    heap.push(0.0, start_id)

    nodes_visited = 0
    early_exit = False

    while not heap.is_empty():
        current_dist, current_id = heap.pop()

        # Sentinel check (shouldn't happen with valid graph)
        if not current_id:
            break

        # Skip stale entries (node was already finalized via decrease_key)
        if current_id in visited:
            continue

        visited.add(current_id)
        nodes_visited += 1

        # Early exit: goal found with optimal distance
        if current_id == goal_id:
            early_exit = True
            break

        # Record step for animation (before expanding neighbors)
        if record_steps:
            frontier_ids = []
            for i in range(1, len(heap._heap)):
                frontier_ids.append(heap._heap[i][1])
            steps.append({
                "current": current_id,
                "frontier": frontier_ids,
                "visited": list(visited),
                "dist_snapshot": {
                    nid: d for nid, d in dist.items()
                    if d < INF and nid not in visited
                },
            })

        # Relax edges: for each neighbor, try to improve distance
        for neighbor_id, weight in graph.get_neighbors(current_id):
            if neighbor_id in visited:
                continue
            new_dist = current_dist + weight
            if new_dist < dist[neighbor_id]:
                dist[neighbor_id] = new_dist
                prev[neighbor_id] = current_id
                if heap.contains(neighbor_id):
                    heap.decrease_key(neighbor_id, new_dist)
                else:
                    heap.push(new_dist, neighbor_id)

    # Reconstruct path using Stack (LIFO) for correct order
    path = _reconstruct_path(prev, start_id, goal_id, early_exit or goal_id in visited)

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
    """Build the forward path from start to goal using a Stack.

    Traces predecessor pointers backward (goal → ... → start),
    pushes each onto a Stack, then pops to get forward order.

    The Stack is a hand-built ADT — this is NOT using a Python list
    directly for reversal, to demonstrate Stack usage in the report.

    Returns empty list if goal is unreachable.
    """
    if not reached:
        return []

    stack = Stack()
    current = goal_id
    while current is not None:
        stack.push(current)
        if current == start_id:
            break
        current = prev.get(current)

    # Build forward path by popping from Stack (LIFO → correct order)
    path = []
    while not stack.is_empty():
        path.append(stack.pop())

    # Verify the path starts with start_id (safety check)
    if path and path[0] == start_id:
        return path
    return []
