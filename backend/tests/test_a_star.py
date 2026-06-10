"""Tests for A* search algorithm with 3 heuristic variants.

Covers: all heuristics produce valid paths, admissibility verification,
A* vs Dijkstra consistency, node visit efficiency, and floor-aware behavior.
"""

import math
import pytest
from backend.models.node import Node, NodeType
from backend.models.graph import AdjacencyListGraph
from backend.algorithms.a_star import (
    a_star, HEURISTICS,
    heuristic_euclidean, heuristic_manhattan, heuristic_floor_aware,
    SCALE, FLOOR_PENALTY,
)
from backend.algorithms.dijkstra import dijkstra


def _make_node(nid: str, floor: int = 1, x: float = 0, y: float = 0) -> Node:
    return Node(node_id=nid, name=nid, node_type=NodeType.ROOM,
                floor=floor, x=x, y=y)


class TestAStarHeuristics:
    """Heuristic function correctness and admissibility."""

    def test_all_heuristics_return_path(self):
        """All three heuristics should find a valid path."""
        g = AdjacencyListGraph()
        for i in range(5):
            g.add_node(_make_node(f"N{i}", x=i * 10, y=0))
        for i in range(4):
            g.add_edge(f"N{i}", f"N{i+1}", 10.0)

        for h in ["euclidean", "manhattan", "floor_aware"]:
            result = a_star(g, "N0", "N4", heuristic=h)
            assert result["path"] == ["N0", "N1", "N2", "N3", "N4"], \
                f"Heuristic '{h}' failed to find correct path"
            assert result["total_distance"] == 40.0

    def test_euclidean_admissible(self):
        """Euclidean heuristic must never overestimate for any node pair."""
        g = AdjacencyListGraph()
        g.add_node(_make_node("A", x=0, y=0))
        g.add_node(_make_node("B", x=30, y=40))
        g.add_node(_make_node("C", x=50, y=50))
        g.add_edge("A", "B", 60.0)  # long edge
        g.add_edge("B", "C", 30.0)

        # h("A", "C") = sqrt(50²+50²)*0.8 = sqrt(5000)*0.8 ≈ 56.6
        # True shortest A→C = 90.0, so h <= true ✓
        h_val = heuristic_euclidean(g, "A", "C")
        assert h_val <= 90.0, f"h={h_val} > true=90.0 — heuristic NOT admissible"

    def test_manhattan_admissible(self):
        """Manhattan heuristic must be admissible on orthogonal layouts."""
        g = AdjacencyListGraph()
        g.add_node(_make_node("A", x=0, y=0))
        g.add_node(_make_node("B", x=30, y=0))
        g.add_node(_make_node("C", x=30, y=40))
        g.add_edge("A", "B", 30.0)
        g.add_edge("B", "C", 40.0)  # orthogonal path = 70

        h_val = heuristic_manhattan(g, "A", "C")
        # Manhattan = (30+40)*0.8 = 56. True = 70. 56 ≤ 70 ✓
        assert h_val <= 70.0, f"h={h_val} > true=70.0"

    def test_floor_aware_penalizes_vertical(self):
        """Floor-aware heuristic should add significant cost for floor change."""
        g = AdjacencyListGraph()
        g.add_node(_make_node("F1-R", floor=1, x=10, y=10))
        g.add_node(_make_node("F4-R", floor=4, x=10, y=10))

        h_euc = heuristic_euclidean(g, "F1-R", "F4-R")
        h_floor = heuristic_floor_aware(g, "F1-R", "F4-R")
        # Floor penalty = 3 floors × 20m = 60m added
        expected_extra = 3 * FLOOR_PENALTY
        assert abs(h_floor - h_euc - expected_extra) < 1e-9, \
            f"Floor-aware should add ~{expected_extra}, got {h_floor - h_euc}"


class TestAStarCorrectness:
    """A* vs Dijkstra consistency tests."""

    def test_a_star_matches_dijkstra(self):
        """On a simple graph, A* (all heuristics) should match Dijkstra's optimal path."""
        g = AdjacencyListGraph()
        # Build a small grid-like graph
        nodes = []
        for i in range(3):
            for j in range(3):
                nid = f"N{i}{j}"
                g.add_node(_make_node(nid, x=i * 20, y=j * 20))
                nodes.append(nid)

        # Connect grid
        for i in range(3):
            for j in range(3):
                nid = f"N{i}{j}"
                if i < 2:
                    g.add_edge(nid, f"N{i+1}{j}", 20.0)
                if j < 2:
                    g.add_edge(nid, f"N{i}{j+1}", 20.0)
                # Add diagonals with weighted edges
                if i < 2 and j < 2:
                    g.add_edge(nid, f"N{i+1}{j+1}", 28.0)

        d_result = dijkstra(g, "N00", "N22")
        d_dist = d_result["total_distance"]

        for h in ["euclidean", "manhattan", "floor_aware"]:
            a_result = a_star(g, "N00", "N22", heuristic=h)
            assert a_result["total_distance"] == d_dist, \
                f"A*({h}) distance {a_result['total_distance']} != Dijkstra {d_dist}"

    def test_a_star_visits_fewer_nodes(self):
        """A* with good heuristic should expand fewer nodes than Dijkstra."""
        g = AdjacencyListGraph()
        # Create a graph where A* can focus toward the goal
        for i in range(10):
            g.add_node(_make_node(f"N{i}", x=i * 10, y=0))
        for i in range(9):
            g.add_edge(f"N{i}", f"N{i+1}", 10.0)
        # Add side branches (distractors for Dijkstra)
        for i in range(8):
            side = _make_node(f"S{i}", x=i * 10, y=10)
            g.add_node(side)
            g.add_edge(f"N{i}", f"S{i}", 5.0)
            g.add_edge(f"S{i}", f"N{i+1}", 6.0)  # shortcut back

        d_result = dijkstra(g, "N0", "N9")
        a_result = a_star(g, "N0", "N9", heuristic="euclidean")

        # A* should visit fewer or equal nodes than Dijkstra
        assert a_result["nodes_visited"] <= d_result["nodes_visited"], \
            f"A* visited {a_result['nodes_visited']} > Dijkstra {d_result['nodes_visited']}"

    def test_nonexistent_heuristic_raises(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_edge("A", "B", 5.0)
        with pytest.raises(ValueError, match="Unknown heuristic"):
            a_star(g, "A", "B", heuristic="invalid_h")
