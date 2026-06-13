"""Queue and Stack ADTs for graph search algorithms.

Ported from CampusPath (queue_stack.py).

- Queue (FIFO): Used by BFS and Bidirectional BFS
- Stack (LIFO): Used for path reconstruction in all algorithms

All operations are O(1) amortized.
"""

from typing import Any, List, Optional


class Queue:
    """First-In-First-Out (FIFO) queue.

    Used by BFS to explore nodes in order of discovery distance.
    Python list with index pointer for efficient dequeuing without
    the O(n) cost of list.pop(0).

    Usage:
        q = Queue()
        q.enqueue("start")
        item = q.dequeue()   # "start"
    """

    def __init__(self) -> None:
        self._items: List[Any] = []
        self._head: int = 0

    def enqueue(self, item: Any) -> None:
        """Add an item to the back of the queue. O(1)."""
        self._items.append(item)

    def dequeue(self) -> Optional[Any]:
        """Remove and return the front item. O(1) amortized.

        Returns None if the queue is empty.
        """
        if self.is_empty():
            return None
        item = self._items[self._head]
        self._head += 1
        if self._head > len(self._items) // 2:
            self._items = self._items[self._head:]
            self._head = 0
        return item

    def is_empty(self) -> bool:
        """Return True if the queue contains no items."""
        return self._head >= len(self._items)

    def size(self) -> int:
        """Return the current number of items in the queue."""
        return len(self._items) - self._head

    def __len__(self) -> int:
        return self.size()

    def __repr__(self) -> str:
        return f"Queue({self._items[self._head:]})"


class Stack:
    """Last-In-First-Out (LIFO) stack.

    Used for path reconstruction: after a search finds the goal,
    we follow predecessor pointers backward (goal → ... → start),
    push each onto a stack, then pop to get the forward order.

    Usage:
        s = Stack()
        s.push("a")
        s.push("b")
        item = s.pop()   # "b"
    """

    def __init__(self) -> None:
        self._items: List[Any] = []

    def push(self, item: Any) -> None:
        """Push an item onto the top of the stack. O(1)."""
        self._items.append(item)

    def pop(self) -> Optional[Any]:
        """Remove and return the top item. O(1).

        Returns None if the stack is empty.
        """
        if self.is_empty():
            return None
        return self._items.pop()

    def peek(self) -> Optional[Any]:
        """Return the top item without removing it. O(1)."""
        if self.is_empty():
            return None
        return self._items[-1]

    def is_empty(self) -> bool:
        """Return True if the stack contains no items."""
        return len(self._items) == 0

    def size(self) -> int:
        """Return the current number of items in the stack."""
        return len(self._items)

    def __len__(self) -> int:
        return self.size()

    def __repr__(self) -> str:
        return f"Stack({self._items})"
