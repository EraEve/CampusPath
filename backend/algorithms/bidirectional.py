"""Bidirectional Search Algorithms.

Two variants are implemented:

1. bidirectional_bfs — Two simultaneous BFS searches (forward from start,
   backward from goal). When the frontiers meet, the path is merged.
   Guarantees shortest path in number of edges (unweighted).

2. bidirectional_dijkstra — Two simultaneous Dijkstra searches using two
   MinHeaps. When a node is expanded by both sides, we have the shortest
   weighted path. This is a significant optimization for large graphs.

Bidirectional search reduces the explored space from O(b^d) to O(b^(d/2)),
where b is the branching factor and d is the path depth. For a building
graph with b≈3, this is a ~10× reduction in visited nodes for d=5-6.

IMPORTANT: Both algorithms build a reverse adjacency index at startup
to efficiently traverse edges in the backward direction. This is O(|E|)
preprocessing — negligible compared to the search itself.

Both variants use the hand-built Queue, MinHeap, and Stack ADTs.
"""

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from .min_heap import MinHeap
from .queue_stack import Queue, Stack
from ..models.graph import AdjacencyListGraph


INF = float("inf")


# ---------------------------------------------------------------------------
# Reverse adjacency helper
# ---------------------------------------------------------------------------

def _build_reverse_adjacency(
    graph: AdjacencyListGraph,
) -> Dict[str, List[Tuple[str, float]]]:
    """Build a reverse adjacency index: node_id → [(predecessor_id, weight)].

    For each directed edge u→v with weight w, we record v→u with weight w.
    This enables efficient backward search in bidirectional algorithms
    without modifying the original graph.

    Time: O(|E|), Space: O(|E|).
    """
    reverse: Dict[str, List[Tuple[str, float]]] = {nid: [] for nid in graph}
    for from_id, neighbors in graph.adjacency.items():
        for to_id, weight in neighbors:
            reverse[to_id].append((from_id, weight))
    return reverse


# ---------------------------------------------------------------------------
# Bidirectional BFS (unweighted)
# ---------------------------------------------------------------------------

def bidirectional_bfs(
    graph: AdjacencyListGraph,
    start_id: str,
    goal_id: str,
    record_steps: bool = False,
) -> Dict[str, Any]:
    """Bidirectional BFS for unweighted shortest path.

    Runs BFS simultaneously from start (forward, following outgoing edges)
    and goal (backward, following incoming edges via reverse adjacency).
    When a node is discovered by both frontiers, the path is complete.

    Returns the standardized result dict.
    """
    t_start = time.perf_counter()

    if not graph.has_node(start_id):
        raise KeyError(f"Start node '{start_id}' not in graph.")
    if not graph.has_node(goal_id):
        raise KeyError(f"Goal node '{goal_id}' not in graph.")

    if start_id == goal_id:
        return {
            "path": [start_id],
            "total_distance": 0.0,
            "nodes_visited": 0,
            "execution_time_ms": 0.0,
            "steps": [],
        }

    # Build reverse adjacency for backward traversal
    reverse_adj = _build_reverse_adjacency(graph)

    # Forward: uses graph.get_neighbors (outgoing edges)
    # Backward: uses reverse_adj (incoming edges = outgoing in reverse graph)
    fwd_parent: Dict[str, Optional[str]] = {start_id: None}
    bwd_parent: Dict[str, Optional[str]] = {goal_id: None}

    fwd_queue = Queue()
    bwd_queue = Queue()
    fwd_queue.enqueue(start_id)
    bwd_queue.enqueue(goal_id)

    meeting_node: Optional[str] = None
    nodes_discovered = 0

    while not fwd_queue.is_empty() and not bwd_queue.is_empty():
        # Expand forward frontier by one level
        meeting_node = _bfs_expand_one_level(
            graph, fwd_queue, fwd_parent, bwd_parent,
            use_reverse=False, reverse_adj=reverse_adj,
        )
        if meeting_node:
            nodes_discovered = len(fwd_parent) + len(bwd_parent)
            break

        # Expand backward frontier by one level
        meeting_node = _bfs_expand_one_level(
            graph, bwd_queue, bwd_parent, fwd_parent,
            use_reverse=True, reverse_adj=reverse_adj,
        )
        if meeting_node:
            nodes_discovered = len(fwd_parent) + len(bwd_parent)
            break

    # Merge paths
    path = _merge_bidirectional_path(
        fwd_parent, bwd_parent, meeting_node, start_id, goal_id
    )

    # Compute actual weighted distance
    total_weight = 0.0
    for i in range(len(path) - 1):
        w = graph.get_weight(path[i], path[i + 1])
        total_weight += w if w >= 0 else 0.0

    t_end = time.perf_counter()

    return {
        "path": path,
        "total_distance": total_weight,
        "nodes_visited": nodes_discovered,
        "execution_time_ms": round((t_end - t_start) * 1000.0, 4),
        "steps": [],
    }


def _bfs_expand_one_level(
    graph: AdjacencyListGraph,
    queue: Queue,
    own_parent: Dict[str, Optional[str]],
    other_parent: Dict[str, Optional[str]],
    use_reverse: bool,
    reverse_adj: Dict[str, List[Tuple[str, float]]],
) -> Optional[str]:
    """Expand one BFS level from the given queue.

    Args:
        graph: The building graph.
        queue: The BFS frontier queue for this direction.
        own_parent: Parent dict for this direction (node_id → parent).
        other_parent: Parent dict for the opposite direction.
        use_reverse: If True, traverse incoming edges (backward search).
        reverse_adj: Precomputed reverse adjacency index.

    Returns:
        meeting_node_id if the frontiers intersect, else None.
    """
    level_size = queue.size()
    for _ in range(level_size):
        current = queue.dequeue()
        if current is None:
            continue

        # Get neighbors depending on direction
        if use_reverse:
            neighbors = reverse_adj.get(current, [])
        else:
            neighbors = graph.get_neighbors(current)

        for neighbor_id, _weight in neighbors:
            if neighbor_id not in own_parent:
                own_parent[neighbor_id] = current
                queue.enqueue(neighbor_id)
                # Check intersection with the OTHER search
                if neighbor_id in other_parent:
                    return neighbor_id
    return None


# ---------------------------------------------------------------------------
# Bidirectional Dijkstra (weighted)
# ---------------------------------------------------------------------------

def bidirectional_dijkstra(
    graph: AdjacencyListGraph,
    start_id: str,
    goal_id: str,
    record_steps: bool = False,
) -> Dict[str, Any]:
    """Bidirectional Dijkstra for weighted shortest path.

    Runs two Dijkstra instances simultaneously:
    - Forward: outgoing edges, MinHeap ordered by dist from start.
    - Backward: incoming edges (via reverse adjacency), MinHeap ordered
      by dist from goal.

    Terminates when the sum of minimum frontier keys from both sides
    ≥ best candidate found (the classic stopping condition for
    bidirectional Dijkstra).

    Args:
        graph: The building graph.
        start_id: Starting node ID.
        goal_id: Target node ID.
        record_steps: If True, record step data (ignored for brevity).

    Returns:
        Standardized result dict.
    """
    t_start = time.perf_counter()

    if not graph.has_node(start_id):
        raise KeyError(f"Start node '{start_id}' not in graph.")
    if not graph.has_node(goal_id):
        raise KeyError(f"Goal node '{goal_id}' not in graph.")

    if start_id == goal_id:
        return {
            "path": [start_id],
            "total_distance": 0.0,
            "nodes_visited": 0,
            "execution_time_ms": 0.0,
            "steps": [],
        }

    reverse_adj = _build_reverse_adjacency(graph)

    # Forward: dist from start along outgoing edges
    fwd_dist: Dict[str, float] = {}
    fwd_prev: Dict[str, Optional[str]] = {}
    fwd_heap = MinHeap()
    fwd_closed: Set[str] = set()

    # Backward: dist from goal along incoming edges (reverse direction)
    bwd_dist: Dict[str, float] = {}
    bwd_prev: Dict[str, Optional[str]] = {}
    bwd_heap = MinHeap()
    bwd_closed: Set[str] = set()

    # Initialize all nodes
    for nid in graph:
        fwd_dist[nid] = INF
        fwd_prev[nid] = None
        bwd_dist[nid] = INF
        bwd_prev[nid] = None

    fwd_dist[start_id] = 0.0
    fwd_heap.push(0.0, start_id)
    bwd_dist[goal_id] = 0.0
    bwd_heap.push(0.0, goal_id)

    best_dist = INF
    meeting_node: Optional[str] = None

    while not fwd_heap.is_empty() and not bwd_heap.is_empty():
        # Termination check: if min frontier priority sum >= best_dist
        fwd_min = fwd_heap._heap[1][0] if fwd_heap.size() > 0 else INF
        bwd_min = bwd_heap._heap[1][0] if bwd_heap.size() > 0 else INF
        if fwd_min + bwd_min >= best_dist:
            break

        # Expand the side with smaller frontier
        if fwd_heap.size() <= bwd_heap.size():
            _dijkstra_expand_directed(
                graph, fwd_heap, fwd_dist, fwd_prev, fwd_closed,
                use_reverse=False, reverse_adj=reverse_adj,
            )
        else:
            _dijkstra_expand_directed(
                graph, bwd_heap, bwd_dist, bwd_prev, bwd_closed,
                use_reverse=True, reverse_adj=reverse_adj,
            )

        # Check for better meeting point after each expansion
        for nid in fwd_closed:
            if nid in bwd_dist and bwd_dist[nid] < INF:
                candidate = fwd_dist[nid] + bwd_dist[nid]
                if candidate < best_dist:
                    best_dist = candidate
                    meeting_node = nid

    # Also check nodes closed in backward with forward distances
    for nid in bwd_closed:
        if nid in fwd_dist and fwd_dist[nid] < INF:
            candidate = fwd_dist[nid] + bwd_dist[nid]
            if candidate < best_dist:
                best_dist = candidate
                meeting_node = nid

    # Reconstruct path
    path = _merge_weighted_path(
        fwd_prev, bwd_prev, meeting_node, start_id, goal_id
    )

    t_end = time.perf_counter()

    return {
        "path": path,
        "total_distance": best_dist if best_dist < INF else INF,
        "nodes_visited": len(fwd_closed) + len(bwd_closed),
        "execution_time_ms": round((t_end - t_start) * 1000.0, 4),
        "steps": [],
    }


def _dijkstra_expand_directed(
    graph: AdjacencyListGraph,
    heap: MinHeap,
    dist: Dict[str, float],
    prev: Dict[str, Optional[str]],
    closed: Set[str],
    use_reverse: bool,
    reverse_adj: Dict[str, List[Tuple[str, float]]],
) -> None:
    """Expand one node from the Dijkstra frontier.

    Args:
        use_reverse: If True, traverse incoming edges (backward search).
        reverse_adj: Precomputed reverse adjacency index.
    """
    if heap.is_empty():
        return

    current_dist, current_id = heap.pop()
    if not current_id:
        return
    if current_id in closed:
        return

    closed.add(current_id)

    # Get neighbors based on direction
    if use_reverse:
        neighbors = reverse_adj.get(current_id, [])
    else:
        neighbors = graph.get_neighbors(current_id)

    for neighbor_id, weight in neighbors:
        if neighbor_id in closed:
            continue
        new_dist = current_dist + weight
        if neighbor_id not in dist or new_dist < dist[neighbor_id]:
            dist[neighbor_id] = new_dist
            prev[neighbor_id] = current_id
            if heap.contains(neighbor_id):
                heap.decrease_key(neighbor_id, new_dist)
            else:
                heap.push(new_dist, neighbor_id)


# ---------------------------------------------------------------------------
# Path merging utilities (shared by both bidirectional algorithms)
# ---------------------------------------------------------------------------

def _merge_bidirectional_path(
    fwd_parent: Dict[str, Optional[str]],
    bwd_parent: Dict[str, Optional[str]],
    meeting_node: Optional[str],
    start_id: str,
    goal_id: str,
) -> List[str]:
    """Merge forward and backward parent chains at meeting node.

    Forward chain: start → ... → meeting_node
    Backward chain: meeting_node ← ... ← goal

    Uses Stack ADT for reversal.
    """
    if meeting_node is None:
        return []

    # Build forward path: start → ... → meeting_node
    stack = Stack()
    current = meeting_node
    seen = set()
    while current is not None and current not in seen:
        stack.push(current)
        seen.add(current)
        if current == start_id:
            break
        current = fwd_parent.get(current)

    if stack.is_empty():
        return []

    forward_path = []
    while not stack.is_empty():
        forward_path.append(stack.pop())

    if forward_path[0] != start_id:
        return []

    # Build backward path: meeting_node → ... → goal
    # Note: the backward search explored from goal outward.
    # bwd_parent[meeting_node] is the node one step CLOSER to goal.
    # So from meeting_node, we follow bwd_parent toward goal.
    backward_path = []
    current = bwd_parent.get(meeting_node)
    seen = set()
    while current is not None and current not in seen:
        backward_path.append(current)
        seen.add(current)
        if current == goal_id:
            break
        current = bwd_parent.get(current)

    return forward_path + backward_path


def _merge_weighted_path(
    fwd_prev: Dict[str, Optional[str]],
    bwd_prev: Dict[str, Optional[str]],
    meeting_node: Optional[str],
    start_id: str,
    goal_id: str,
) -> List[str]:
    """Merge forward and backward predecessor chains at meeting node.

    Same logic as _merge_bidirectional_path but uses the predecessor
    naming convention (prev instead of parent).
    """
    if meeting_node is None:
        return []

    # Forward: start → ... → meeting_node
    stack = Stack()
    current = meeting_node
    seen = set()
    while current is not None and current not in seen:
        stack.push(current)
        seen.add(current)
        if current == start_id:
            break
        current = fwd_prev.get(current)

    if stack.is_empty():
        return []

    forward_path = []
    while not stack.is_empty():
        forward_path.append(stack.pop())

    if forward_path[0] != start_id:
        return []

    # Backward: meeting_node → ... → goal
    backward_path = []
    current = bwd_prev.get(meeting_node)
    seen = set()
    while current is not None and current not in seen:
        backward_path.append(current)
        seen.add(current)
        if current == goal_id:
            break
        current = bwd_prev.get(current)

    return forward_path + backward_path
