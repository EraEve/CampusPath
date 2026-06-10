"""CampusPath Pathfinding Algorithms.

All algorithms are implemented from scratch with zero external dependencies
(no networkx, no scipy, no heapq). Every data structure (min-heap, queue,
stack, adjacency-list graph) is hand-built for the DS&A course.

Algorithm modules:
- dijkstra: Weighted shortest path with MinHeap + decrease_key
- a_star: Heuristic search with 3 variants
- bfs: Unweighted BFS shortest path (baseline)
- bidirectional: Bidirectional BFS + Bidirectional Dijkstra

Supporting data structures:
- min_heap: Binary min-heap with O(log n) decrease_key
- queue_stack: Queue (FIFO) and Stack (LIFO) ADTs
"""

# Lazy imports — modules are imported only when accessed.

__all__ = [
    "MinHeap", "Queue", "Stack",
    "dijkstra", "a_star", "HEURISTICS",
    "bfs_shortest_path",
    "bidirectional_bfs", "bidirectional_dijkstra",
]
