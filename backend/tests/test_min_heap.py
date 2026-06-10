"""Tests for MinHeap — the core priority queue used by Dijkstra.

Covers: push/pop ordering, decrease_key, edge cases, and
large-scale stress testing with 1000 random operations.
"""

import pytest
import random
from backend.algorithms.min_heap import MinHeap


class TestMinHeapBasic:
    """Basic push/pop ordering tests."""

    def test_push_pop_order(self):
        """Items should be popped in ascending priority order."""
        heap = MinHeap()
        heap.push(5.0, "E")
        heap.push(3.0, "C")
        heap.push(4.0, "D")
        heap.push(1.0, "A")
        heap.push(2.0, "B")

        results = []
        while not heap.is_empty():
            results.append(heap.pop())

        priorities = [p for p, _ in results]
        assert priorities == sorted(priorities), \
            f"Expected sorted priorities, got {priorities}"

    def test_empty_heap_pop(self):
        """Pop from empty heap returns sentinel (INF, '')."""
        heap = MinHeap()
        priority, node_id = heap.pop()
        assert priority == float("inf")
        assert node_id == ""

    def test_is_empty(self):
        """is_empty reflects heap state correctly."""
        heap = MinHeap()
        assert heap.is_empty() is True
        heap.push(1.0, "A")
        assert heap.is_empty() is False
        heap.pop()
        assert heap.is_empty() is True

    def test_size(self):
        """size() returns correct count."""
        heap = MinHeap()
        assert heap.size() == 0
        heap.push(1.0, "A")
        heap.push(2.0, "B")
        assert heap.size() == 2
        heap.pop()
        assert heap.size() == 1

    def test_contains(self):
        """contains() correctly reports membership."""
        heap = MinHeap()
        heap.push(1.0, "A")
        assert heap.contains("A") is True
        assert heap.contains("B") is False
        heap.pop()
        assert heap.contains("A") is False

    def test_duplicate_push_raises(self):
        """Pushing an existing node_id raises ValueError."""
        heap = MinHeap()
        heap.push(1.0, "A")
        with pytest.raises(ValueError, match="already in heap"):
            heap.push(2.0, "A")


class TestMinHeapDecreaseKey:
    """Tests for the decrease_key operation (the key differentiator)."""

    def test_decrease_key_updates_priority(self):
        """After decrease_key, the node should pop with new priority."""
        heap = MinHeap()
        heap.push(10.0, "A")
        heap.push(5.0, "B")
        heap.push(8.0, "C")

        heap.decrease_key("A", 3.0)  # A was 10, now 3 — new minimum

        priority, node_id = heap.pop()
        assert node_id == "A"
        assert priority == 3.0

    def test_decrease_key_maintains_heap_order(self):
        """Multiple decrease_key ops still produce sorted output."""
        heap = MinHeap()
        for i, nid in enumerate(["A", "B", "C", "D", "E"]):
            heap.push(float(i + 10), nid)

        heap.decrease_key("E", 1.0)
        heap.decrease_key("D", 2.0)
        heap.decrease_key("C", 3.0)

        priorities = []
        while not heap.is_empty():
            p, _ = heap.pop()
            priorities.append(p)

        assert priorities == sorted(priorities)

    def test_decrease_key_nonexistent_raises(self):
        """Decreasing a node not in the heap raises KeyError."""
        heap = MinHeap()
        heap.push(5.0, "A")
        with pytest.raises(KeyError, match="not in heap"):
            heap.decrease_key("B", 1.0)

    def test_decrease_key_larger_value_raises(self):
        """decrease_key with larger value raises ValueError."""
        heap = MinHeap()
        heap.push(5.0, "A")
        with pytest.raises(ValueError, match="Use decrease_key only"):
            heap.decrease_key("A", 10.0)

    def test_decrease_key_position_map_updated(self):
        """After multiple operations, position tracking remains correct."""
        heap = MinHeap()
        heap.push(10.0, "A")
        heap.push(20.0, "B")
        heap.push(30.0, "C")

        heap.decrease_key("C", 5.0)
        assert heap.contains("A") and heap.contains("B") and heap.contains("C")

        heap.pop()  # should be C at 5.0
        assert not heap.contains("C")
        assert heap.contains("A") and heap.contains("B")


class TestMinHeapLargeScale:
    """Stress test with many random operations."""

    def test_large_scale_1000_operations(self):
        """1000 random push/pop/decrease operations maintain correctness."""
        heap = MinHeap()
        random.seed(42)
        expected = {}  # node_id → current priority
        in_heap = set()

        for _ in range(1000):
            op = random.choice(["push", "push", "pop", "decrease"])
            if op == "push":
                nid = f"node-{random.randint(0, 500)}"
                if nid not in in_heap:
                    prio = random.uniform(0, 1000)
                    heap.push(prio, nid)
                    expected[nid] = prio
                    in_heap.add(nid)
            elif op == "pop" and not heap.is_empty():
                prio, nid = heap.pop()
                in_heap.discard(nid)
                if nid in expected:
                    assert abs(prio - expected[nid]) < 1e-9
            elif op == "decrease" and in_heap:
                nid = random.choice(list(in_heap))
                new_prio = expected[nid] - random.uniform(1, 50)
                heap.decrease_key(nid, new_prio)
                expected[nid] = new_prio

        # Pop remaining items and verify ascending order
        last_prio = -float("inf")
        while not heap.is_empty():
            prio, _ = heap.pop()
            assert prio >= last_prio, f"Heap order violated: {prio} < {last_prio}"
            last_prio = prio
