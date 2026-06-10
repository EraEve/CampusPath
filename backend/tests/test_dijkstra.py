"""Tests for Dijkstra's algorithm with hand-built MinHeap.

Covers: trivial paths, triangle topology, disconnected graphs,
early termination, multi-floor paths, and optimality verification.
"""

import pytest
from backend.models.node import Node, NodeType
from backend.models.graph import AdjacencyListGraph
from backend.algorithms.dijkstra import dijkstra


def _make_node(nid: str, floor: int = 1, x: float = 0, y: float = 0) -> Node:
    return Node(node_id=nid, name=nid, node_type=NodeType.ROOM,
                floor=floor, x=x, y=y)


class TestDijkstraBasic:
    """Fundamental correctness tests."""

    def test_simple_path_two_nodes(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A", x=0, y=0))
        g.add_node(_make_node("B", x=10, y=0))
        g.add_edge("A", "B", 5.0)

        result = dijkstra(g, "A", "B")
        assert result["path"] == ["A", "B"]
        assert result["total_distance"] == 5.0
        assert result["nodes_visited"] <= 2

    def test_shortest_path_triangle(self):
        """A→B direct (10), A→C→B (3+3=6). Dijkstra must pick the latter."""
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_node(_make_node("C"))
        g.add_edge("A", "B", 10.0)
        g.add_edge("A", "C", 3.0)
        g.add_edge("C", "B", 3.0)

        result = dijkstra(g, "A", "B")
        assert result["path"] == ["A", "C", "B"]
        assert result["total_distance"] == 6.0

    def test_no_path_disconnected(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        # No edge between A and B

        result = dijkstra(g, "A", "B")
        assert result["path"] == []
        assert result["total_distance"] == float("inf")

    def test_start_equals_goal(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_edge("A", "B", 5.0)

        result = dijkstra(g, "A", "A")
        assert result["path"] == ["A"]
        assert result["total_distance"] == 0.0

    def test_early_exit_at_goal(self):
        """Dijkstra should stop as soon as goal is popped."""
        g = AdjacencyListGraph()
        nodes = [_make_node(f"N{i}", x=i * 10, y=0) for i in range(10)]
        for n in nodes:
            g.add_node(n)
        for i in range(9):
            g.add_edge(f"N{i}", f"N{i+1}", 1.0)
        # Add side branches so total nodes > path length
        for i in range(5):
            side = _make_node(f"S{i}", x=i * 10, y=10)
            g.add_node(side)
            g.add_edge(f"N{i}", f"S{i}", 0.5)

        result = dijkstra(g, "N0", "N5")
        assert result["path"] is not None
        # Should have visited ≤ 7 nodes (path N0→...→N5 = 6 edges + start)
        # Not all 15 nodes
        assert result["nodes_visited"] < g.total_vertices

    def test_nonexistent_node_raises(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        with pytest.raises(KeyError):
            dijkstra(g, "A", "NONEXISTENT")
        with pytest.raises(KeyError):
            dijkstra(g, "NONEXISTENT", "A")


class TestDijkstraMultiFloor:
    """Multi-floor specific tests."""

    def test_multi_floor_path(self):
        """Path from Floor 1 to Floor 2 via stair."""
        g = AdjacencyListGraph()
        g.add_node(_make_node("F1-R101", floor=1, x=10, y=10))
        g.add_node(_make_node("F1-STAIR", floor=1, x=30, y=20))
        g.add_node(_make_node("F2-STAIR", floor=2, x=30, y=20))
        g.add_node(_make_node("F2-R201", floor=2, x=50, y=10))

        g.add_edge("F1-R101", "F1-STAIR", 10.0)
        g.add_edge("F1-STAIR", "F2-STAIR", 6.0)  # stair transition
        g.add_edge("F2-STAIR", "F2-R201", 8.0)

        result = dijkstra(g, "F1-R101", "F2-R201")
        assert result["path"] == ["F1-R101", "F1-STAIR", "F2-STAIR", "F2-R201"]
        assert result["total_distance"] == 24.0

    def test_vertical_connector_weight_respected(self):
        """Elevator should be shorter than stairs."""
        g = AdjacencyListGraph()
        g.add_node(_make_node("F1-R", floor=1, x=10, y=10))
        g.add_node(_make_node("F1-STAIR", floor=1, x=20, y=10))
        g.add_node(_make_node("F1-ELEV", floor=1, x=30, y=10))
        g.add_node(_make_node("F2-STAIR", floor=2, x=20, y=10))
        g.add_node(_make_node("F2-ELEV", floor=2, x=30, y=10))
        g.add_node(_make_node("F2-R", floor=2, x=40, y=10))

        g.add_edge("F1-R", "F1-STAIR", 5.0)
        g.add_edge("F1-R", "F1-ELEV", 8.0)
        g.add_edge("F1-STAIR", "F2-STAIR", 6.0)   # stairs cost
        g.add_edge("F1-ELEV", "F2-ELEV", 2.0)      # elevator cost (faster)
        g.add_edge("F2-STAIR", "F2-R", 5.0)
        g.add_edge("F2-ELEV", "F2-R", 3.0)

        result = dijkstra(g, "F1-R", "F2-R")
        # Elevator path: 8+2+3=13 vs Stairs: 5+6+5=16
        # Dijkstra should pick elevator
        assert result["total_distance"] == 13.0
        assert "ELEV" in result["path"][2] or "ELEV" in result["path"][1]
