"""Min-Heap Priority Queue with O(log n) decrease_key.

This is the core data structure enabling Dijkstra's O((V+E) log V)
performance. A standard library heapq would only give O(log n) push/pop,
not decrease_key, forcing re-insertion which degrades to O(E log E).

Implementation: Binary heap with a position map (HashMap) tracking each
node_id's array index. Sift-up/sift-down maintain the heap invariant
after any mutation.

All operations are O(log n) except is_empty/contains/size which are O(1).

NOTE: This is NOT a generic heap — it is purpose-built for pathfinding
where priorities are floats and items are string node IDs. This keeps
the code focused for the course report.
"""

from typing import Dict, List, Tuple


INF = float("inf")


class MinHeap:
    """Binary min-heap with decrease_key support via position map.

    Each entry is (priority: float, node_id: str). The smallest priority
    is always at index 1 (index 0 is a dummy sentinel for simpler math).

    The position dict maps node_id → current heap index, enabling O(1)
    lookup for decrease_key (then O(log n) sift-up to restore invariant).

    Usage:
        heap = MinHeap()
        heap.push(5.0, "room-101")
        heap.push(3.0, "room-202")
        heap.decrease_key("room-101", 1.0)   # update priority
        priority, node = heap.pop()           # (1.0, "room-101")
    """

    def __init__(self) -> None:
        # heap[0] is a sentinel; real data starts at index 1
        self._heap: List[Tuple[float, str]] = [( -INF, "__SENTINEL__")]
        self._position: Dict[str, int] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def push(self, priority: float, node_id: str) -> None:
        """Insert a new node with the given priority.

        Raises ValueError if node_id is already in the heap. Use
        decrease_key to update an existing entry instead.
        """
        if node_id in self._position:
            raise ValueError(
                f"Node '{node_id}' already in heap. "
                f"Use decrease_key() to update priority."
            )
        self._heap.append((priority, node_id))
        idx = len(self._heap) - 1
        self._position[node_id] = idx
        self._sift_up(idx)

    def pop(self) -> Tuple[float, str]:
        """Remove and return the (priority, node_id) with smallest priority.

        Returns (INF, "") if the heap is empty (caller should check
        is_empty() first in performance-critical code).
        """
        if self.is_empty():
            return (INF, "")

        min_entry = self._heap[1]
        node_id = min_entry[1]
        del self._position[node_id]

        last = self._heap.pop()
        if len(self._heap) > 1:
            self._heap[1] = last
            self._position[last[1]] = 1
            self._sift_down(1)

        return min_entry

    def decrease_key(self, node_id: str, new_priority: float) -> None:
        """Reduce the priority of an existing node.

        Raises KeyError if node_id is not in the heap.
        Raises ValueError if new_priority > current priority.
        """
        if node_id not in self._position:
            raise KeyError(f"Node '{node_id}' not in heap.")
        idx = self._position[node_id]
        old_priority = self._heap[idx][0]
        if new_priority > old_priority:
            raise ValueError(
                f"new_priority ({new_priority}) > "
                f"current ({old_priority}). Use decrease_key only."
            )
        self._heap[idx] = (new_priority, node_id)
        self._sift_up(idx)

    def is_empty(self) -> bool:
        """Return True if the heap contains no entries."""
        return len(self._heap) <= 1

    def contains(self, node_id: str) -> bool:
        """Return True if node_id is currently in the heap."""
        return node_id in self._position

    def size(self) -> int:
        """Return the number of entries in the heap."""
        return len(self._heap) - 1

    # ------------------------------------------------------------------
    # Internal: heap invariant maintenance
    # ------------------------------------------------------------------

    def _sift_up(self, idx: int) -> None:
        """Move the element at idx upward to restore heap order."""
        while idx > 1:
            parent = idx // 2
            if self._heap[idx][0] < self._heap[parent][0]:
                self._swap(idx, parent)
                idx = parent
            else:
                break

    def _sift_down(self, idx: int) -> None:
        """Move the element at idx downward to restore heap order."""
        n = len(self._heap)
        while 2 * idx < n:
            child = 2 * idx
            # Pick the smaller of the two children
            if child + 1 < n and self._heap[child + 1][0] < self._heap[child][0]:
                child += 1
            if self._heap[child][0] < self._heap[idx][0]:
                self._swap(idx, child)
                idx = child
            else:
                break

    def _swap(self, i: int, j: int) -> None:
        """Swap heap entries at indices i and j, updating positions."""
        self._heap[i], self._heap[j] = self._heap[j], self._heap[i]
        self._position[self._heap[i][1]] = i
        self._position[self._heap[j][1]] = j
