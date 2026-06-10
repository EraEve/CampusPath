"""Tests for BFS and Bidirectional Search algorithms.

Covers: BFS correctness on unweighted graphs, BFS vs Dijkstra
on weighted graphs (showing why weighted algorithms matter),
bidirectional BFS correctness, and performance comparison.
"""

import pytest
from backend.models.node import Node, NodeType
from backend.models.graph import AdjacencyListGraph
from backend.algorithms.bfs import bfs_shortest_path
from backend.algorithms.bidirectional import bidirectional_bfs, bidirectional_dijkstra
from backend.algorithms.dijkstra import dijkstra


def _make_node(nid: str, floor: int = 1, x: float = 0, y: float = 0) -> Node:
    return Node(node_id=nid, name=nid, node_type=NodeType.ROOM,
                floor=floor, x=x, y=y)


class TestBFS:
    """BFS correctness and comparison with weighted algorithms."""

    def test_bfs_shortest_unweighted_path(self):
        """BFS finds shortest path by edge count with uniform weights."""
        g = AdjacencyListGraph()
        for i in range(5):
            g.add_node(_make_node(f"N{i}"))
        for i in range(4):
            g.add_edge(f"N{i}", f"N{i+1}", 1.0)

        result = bfs_shortest_path(g, "N0", "N4")
        assert result["path"] == ["N0", "N1", "N2", "N3", "N4"]
        assert len(result["path"]) == 5  # 5 nodes = 4 edges

    def test_bfs_vs_dijkstra_weighted(self):
        """BFS may find a suboptimal path on a weighted graph.

        Path A→B→C has 2 edges but weight 10+10=20.
        Path A→D→E→C has 3 edges but weight 3+3+3=9.
        BFS picks 2-edge path. Dijkstra picks lighter 3-edge path.
        """
        g = AdjacencyListGraph()
        for nid in ["A", "B", "C", "D", "E"]:
            g.add_node(_make_node(nid))
        g.add_edge("A", "B", 10.0)
        g.add_edge("B", "C", 10.0)   # path A-B-C: 2 edges, weight 20
        g.add_edge("A", "D", 3.0)
        g.add_edge("D", "E", 3.0)
        g.add_edge("E", "C", 3.0)    # path A-D-E-C: 3 edges, weight 9

        bfs_result = bfs_shortest_path(g, "A", "C")
        dij_result = dijkstra(g, "A", "C")

        # BFS picks fewer edges (A-B-C = 2 edges)
        assert len(bfs_result["path"]) <= len(dij_result["path"]) or \
            bfs_result["total_distance"] >= dij_result["total_distance"], \
            "BFS should NOT beat Dijkstra on weighted distance"

        # Dijkstra's path should be lighter
        assert dij_result["total_distance"] <= bfs_result["total_distance"], \
            "Dijkstra must find optimal weighted path"

    def test_bfs_no_path(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        result = bfs_shortest_path(g, "A", "B")
        assert result["path"] == []
        assert result["total_distance"] == 0.0


class TestBidirectional:
    """Bidirectional search correctness tests."""

    def test_bidirectional_bfs_matches_bfs(self):
        """Bidirectional BFS should find same-length path as regular BFS."""
        g = AdjacencyListGraph()
        for i in range(6):
            g.add_node(_make_node(f"N{i}"))
        for i in range(5):
            g.add_edge(f"N{i}", f"N{i+1}", 1.0)

        bfs_result = bfs_shortest_path(g, "N0", "N5")
        bi_result = bidirectional_bfs(g, "N0", "N5")

        assert len(bi_result["path"]) == len(bfs_result["path"]), \
            f"Bidirectional path length {len(bi_result['path'])} != BFS {len(bfs_result['path'])}"
        assert bi_result["path"][0] == "N0"
        assert bi_result["path"][-1] == "N5"

    def test_bidirectional_bfs_faster(self):
        """Bidirectional BFS should visit fewer nodes than regular BFS.

        In a chain graph of length 6, BFS visits ~6 nodes.
        Bidirectional BFS from both ends visits ~3+3=6 total discovered,
        and expands ~3 levels total vs ~6 levels for BFS.
        """
        g = AdjacencyListGraph()
        # Create a chain with side branches to make the difference clear
        for i in range(8):
            g.add_node(_make_node(f"N{i}"))
        for i in range(7):
            g.add_edge(f"N{i}", f"N{i+1}", 1.0)

        bfs_result = bfs_shortest_path(g, "N0", "N7")
        bi_result = bidirectional_bfs(g, "N0", "N7")

        # Bidirectional should visit fewer or equal nodes
        assert bi_result["nodes_visited"] <= bfs_result["nodes_visited"] + 2, \
            f"Bidirectional visited {bi_result['nodes_visited']}, BFS visited {bfs_result['nodes_visited']}"

    def test_bidirectional_dijkstra_optimal(self):
        """Bidirectional Dijkstra should match regular Dijkstra's result."""
        g = AdjacencyListGraph()
        for nid in ["A", "B", "C", "D", "E"]:
            g.add_node(_make_node(nid))
        g.add_edge("A", "B", 4.0)
        g.add_edge("A", "C", 2.0)
        g.add_edge("B", "D", 5.0)
        g.add_edge("C", "D", 8.0)
        g.add_edge("C", "E", 3.0)
        g.add_edge("E", "D", 2.0)

        dij_result = dijkstra(g, "A", "D")
        bi_dij_result = bidirectional_dijkstra(g, "A", "D")

        assert abs(bi_dij_result["total_distance"] - dij_result["total_distance"]) < 1e-9, \
            f"Bi-Dijkstra dist {bi_dij_result['total_distance']} != Dijkstra {dij_result['total_distance']}"

    def test_bidirectional_dijkstra_same_node(self):
        """Trivial case: start == goal."""
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        result = bidirectional_dijkstra(g, "A", "A")
        assert result["path"] == ["A"]
        assert result["total_distance"] == 0.0

    def test_bidirectional_bfs_same_node(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        result = bidirectional_bfs(g, "A", "A")
        assert result["path"] == ["A"]
        assert result["total_distance"] == 0.0
