"""Bidirectional Search Algorithms — extended with mode filtering.

Ported from CampusPath with extensions:
- Transport mode filtering for both forward and backward search
- Congestion/blockage awareness
- Reverse adjacency built with mode-filtered edges

Two variants:
1. bidirectional_bfs — simultaneous BFS from both ends (unweighted)
2. bidirectional_dijkstra — simultaneous Dijkstra from both ends (weighted)
"""

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from ..core.graph import NavGraph
from ..core.edge import Edge
from ..core.min_heap import MinHeap
from ..core.queue_stack import Queue, Stack
from ..models.transport import TransportMode

INF = float("inf")


# ---------------------------------------------------------------------------
# Reverse adjacency (mode-filtered)
# ---------------------------------------------------------------------------

def _build_reverse_adjacency(
    graph: NavGraph,
    transport_mode: TransportMode,
) -> Dict[str, List[Edge]]:
    """Build reverse adjacency: node_id → [incoming Edge, ...] for mode.

    For each directed edge u→v usable by the mode, record v→u.
    """
    reverse: Dict[str, List[Edge]] = {nid: [] for nid in graph}
    for from_id in graph:
        for edge in graph.get_edges_for_mode(from_id, transport_mode):
            # Create reverse edge (swap from/to, keep all metadata)
            rev_edge = Edge(
                from_id=edge.to_id, to_id=edge.from_id,
                weight=edge.weight, road_type=edge.road_type,
                one_way=False, allowed_modes=edge.allowed_modes,
                speed_limit=edge.speed_limit,
                congestion_factor=edge.congestion_factor,
                is_blocked=edge.is_blocked, name=edge.name,
            )
            reverse[edge.to_id].append(rev_edge)
    return reverse


# ---------------------------------------------------------------------------
# Bidirectional BFS
# ---------------------------------------------------------------------------

def bidirectional_bfs(
    graph: NavGraph,
    start_id: str,
    goal_id: str,
    transport_mode: TransportMode = TransportMode.WALKING,
    record_steps: bool = False,
) -> Dict[str, Any]:
    """Bidirectional BFS for unweighted shortest path with mode filtering."""
    t_start = time.perf_counter()

    if not graph.has_node(start_id):
        raise KeyError(f"Start node '{start_id}' not in graph.")
    if not graph.has_node(goal_id):
        raise KeyError(f"Goal node '{goal_id}' not in graph.")

    if start_id == goal_id:
        return {"path": [start_id], "total_distance": 0.0,
                "nodes_visited": 0, "execution_time_ms": 0.0, "steps": []}

    reverse_adj = _build_reverse_adjacency(graph, transport_mode)

    fwd_parent: Dict[str, Optional[str]] = {start_id: None}
    bwd_parent: Dict[str, Optional[str]] = {goal_id: None}

    fwd_queue = Queue()
    bwd_queue = Queue()
    fwd_queue.enqueue(start_id)
    bwd_queue.enqueue(goal_id)

    meeting_node: Optional[str] = None
    nodes_discovered = 0
    steps: List[dict] = []

    while not fwd_queue.is_empty() and not bwd_queue.is_empty():
        # Expand forward by one level
        expanded_fwd = _bfs_expand_one_level(
            graph, fwd_queue, fwd_parent, bwd_parent,
            use_reverse=False, reverse_adj=reverse_adj, mode=transport_mode,
        )
        if expanded_fwd:
            meeting_node = expanded_fwd
            nodes_discovered = len(fwd_parent) + len(bwd_parent)
            break

        # Expand backward by one level
        expanded_bwd = _bfs_expand_one_level(
            graph, bwd_queue, bwd_parent, fwd_parent,
            use_reverse=True, reverse_adj=reverse_adj, mode=transport_mode,
        )
        if expanded_bwd:
            meeting_node = expanded_bwd
            nodes_discovered = len(fwd_parent) + len(bwd_parent)
            break

    path = _merge_bidirectional_path(fwd_parent, bwd_parent, meeting_node, start_id, goal_id)

    total_weight = 0.0
    for i in range(len(path) - 1):
        w = graph.get_weight(path[i], path[i + 1])
        total_weight += w if w < INF else 0.0

    t_end = time.perf_counter()

    return {
        "path": path,
        "total_distance": total_weight,
        "nodes_visited": nodes_discovered,
        "execution_time_ms": round((t_end - t_start) * 1000.0, 4),
        "steps": steps,
    }


def _bfs_expand_one_level(
    graph: NavGraph,
    queue: Queue,
    own_parent: Dict[str, Optional[str]],
    other_parent: Dict[str, Optional[str]],
    use_reverse: bool,
    reverse_adj: Dict[str, List[Edge]],
    mode: TransportMode,
) -> Optional[str]:
    """Expand one BFS level. Returns meeting node or None."""
    level_size = queue.size()
    for _ in range(level_size):
        current = queue.dequeue()
        if current is None:
            continue

        if use_reverse:
            neighbors = [(e.to_id, e.weight) for e in reverse_adj.get(current, [])]
        else:
            neighbors = [(e.to_id, e.weight) for e in graph.get_edges_for_mode(current, mode)]

        for neighbor_id, _weight in neighbors:
            if neighbor_id not in own_parent:
                own_parent[neighbor_id] = current
                queue.enqueue(neighbor_id)
                if neighbor_id in other_parent:
                    return neighbor_id
    return None


# ---------------------------------------------------------------------------
# Bidirectional Dijkstra
# ---------------------------------------------------------------------------

def bidirectional_dijkstra(
    graph: NavGraph,
    start_id: str,
    goal_id: str,
    transport_mode: TransportMode = TransportMode.WALKING,
    record_steps: bool = False,
) -> Dict[str, Any]:
    """Bidirectional Dijkstra for weighted shortest path with mode filtering."""
    t_start = time.perf_counter()

    if not graph.has_node(start_id):
        raise KeyError(f"Start node '{start_id}' not in graph.")
    if not graph.has_node(goal_id):
        raise KeyError(f"Goal node '{goal_id}' not in graph.")

    if start_id == goal_id:
        return {"path": [start_id], "total_distance": 0.0,
                "nodes_visited": 0, "execution_time_ms": 0.0, "steps": []}

    reverse_adj = _build_reverse_adjacency(graph, transport_mode)

    fwd_dist: Dict[str, float] = {}
    fwd_prev: Dict[str, Optional[str]] = {}
    fwd_heap = MinHeap()
    fwd_closed: Set[str] = set()

    bwd_dist: Dict[str, float] = {}
    bwd_prev: Dict[str, Optional[str]] = {}
    bwd_heap = MinHeap()
    bwd_closed: Set[str] = set()

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
    steps: List[dict] = []

    while not fwd_heap.is_empty() and not bwd_heap.is_empty():
        fwd_min = fwd_heap._heap[1][0] if fwd_heap.size() > 0 else INF
        bwd_min = bwd_heap._heap[1][0] if bwd_heap.size() > 0 else INF
        if fwd_min + bwd_min >= best_dist:
            break

        # Expand the side with smaller frontier
        if fwd_heap.size() <= bwd_heap.size():
            _expand_dijkstra_directed(
                graph, fwd_heap, fwd_dist, fwd_prev, fwd_closed,
                use_reverse=False, reverse_adj=reverse_adj, mode=transport_mode,
            )
        else:
            _expand_dijkstra_directed(
                graph, bwd_heap, bwd_dist, bwd_prev, bwd_closed,
                use_reverse=True, reverse_adj=reverse_adj, mode=transport_mode,
            )

        # Check for meeting point
        for nid in list(fwd_closed) + list(bwd_closed):
            if fwd_dist.get(nid, INF) < INF and bwd_dist.get(nid, INF) < INF:
                candidate = fwd_dist[nid] + bwd_dist[nid]
                if candidate < best_dist:
                    best_dist = candidate
                    meeting_node = nid

    path = _merge_weighted_path(fwd_prev, bwd_prev, meeting_node, start_id, goal_id)

    t_end = time.perf_counter()

    return {
        "path": path,
        "total_distance": best_dist if best_dist < INF else INF,
        "nodes_visited": len(fwd_closed) + len(bwd_closed),
        "execution_time_ms": round((t_end - t_start) * 1000.0, 4),
        "steps": steps,
    }


def _expand_dijkstra_directed(
    graph: NavGraph,
    heap: MinHeap,
    dist: Dict[str, float],
    prev: Dict[str, Optional[str]],
    closed: Set[str],
    use_reverse: bool,
    reverse_adj: Dict[str, List[Edge]],
    mode: TransportMode,
) -> None:
    """Expand one node from the Dijkstra frontier."""
    if heap.is_empty():
        return

    current_dist, current_id = heap.pop()
    if not current_id or current_id in closed:
        return

    closed.add(current_id)

    if use_reverse:
        neighbors = [(e.to_id, e.effective_weight) for e in reverse_adj.get(current_id, [])]
    else:
        neighbors = [(e.to_id, e.effective_weight) for e in graph.get_edges_for_mode(current_id, mode)]

    for neighbor_id, weight in neighbors:
        if neighbor_id in closed:
            continue
        new_dist = current_dist + weight
        if new_dist < dist.get(neighbor_id, INF):
            dist[neighbor_id] = new_dist
            prev[neighbor_id] = current_id
            if heap.contains(neighbor_id):
                heap.decrease_key(neighbor_id, new_dist)
            else:
                heap.push(new_dist, neighbor_id)


# ---------------------------------------------------------------------------
# Path merging
# ---------------------------------------------------------------------------

def _merge_bidirectional_path(
    fwd_parent: Dict[str, Optional[str]],
    bwd_parent: Dict[str, Optional[str]],
    meeting_node: Optional[str],
    start_id: str,
    goal_id: str,
) -> List[str]:
    """Merge forward and backward parent chains at meeting node."""
    if meeting_node is None:
        return []

    stack = Stack()
    current = meeting_node
    seen = set()
    while current is not None and current not in seen:
        stack.push(current)
        seen.add(current)
        if current == start_id:
            break
        current = fwd_parent.get(current)

    forward_path = []
    while not stack.is_empty():
        forward_path.append(stack.pop())

    if not forward_path or forward_path[0] != start_id:
        return []

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
    """Merge forward and backward predecessor chains."""
    return _merge_bidirectional_path(fwd_prev, bwd_prev, meeting_node, start_id, goal_id)
