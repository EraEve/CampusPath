"""Tests for pathfinding algorithms with mode/congestion filtering."""

import pytest
from smart_navigation.core.graph import NavGraph
from smart_navigation.core.node import NavNode, NavNodeType
from smart_navigation.core.edge import Edge
from smart_navigation.models.transport import TransportMode, RoadType
from smart_navigation.algorithms.dijkstra import dijkstra
from smart_navigation.algorithms.a_star import a_star
from smart_navigation.algorithms.bfs import bfs_shortest_path
from smart_navigation.algorithms.bidirectional import bidirectional_dijkstra, bidirectional_bfs
from smart_navigation.algorithms.congestion_avoidance import congestion_avoidance_dijkstra
from smart_navigation.algorithms.multi_criteria import multi_criteria_dijkstra
from smart_navigation.algorithms.reroute import reroute_from_position


def _make_simple_graph():
    """Create a simple 4-node graph for testing.

    N1 --100-- N2 --100-- N3
     |                       |
     +-------300------- N4 -+
    """
    g = NavGraph()
    g.add_node(NavNode("N1", "Start", NavNodeType.INTERSECTION, 0, 0, 0))
    g.add_node(NavNode("N2", "Mid", NavNodeType.INTERSECTION, 0, 100, 0))
    g.add_node(NavNode("N3", "Goal", NavNodeType.INTERSECTION, 0, 200, 0))
    g.add_node(NavNode("N4", "Alt", NavNodeType.INTERSECTION, 0, 50, 100))

    g.add_undirected_edge("N1", "N2", 100, RoadType.MAIN_ROAD,
                          allowed_modes={TransportMode.DRIVING, TransportMode.WALKING})
    g.add_undirected_edge("N2", "N3", 100, RoadType.MAIN_ROAD,
                          allowed_modes={TransportMode.DRIVING, TransportMode.WALKING})
    g.add_undirected_edge("N1", "N4", 150, RoadType.PATH,
                          allowed_modes={TransportMode.WALKING})
    g.add_undirected_edge("N4", "N3", 150, RoadType.PATH,
                          allowed_modes={TransportMode.WALKING})
    return g


class TestDijkstra:
    def test_simple_path(self):
        g = _make_simple_graph()
        result = dijkstra(g, "N1", "N3", TransportMode.DRIVING)
        assert result["path"] == ["N1", "N2", "N3"]
        assert result["total_distance"] == 200.0

    def test_mode_filtering_walking_only(self):
        """Walking should find a path but may take different routes."""
        g = _make_simple_graph()
        result = dijkstra(g, "N1", "N3", TransportMode.WALKING)
        assert len(result["path"]) > 0
        assert result["total_distance"] < float("inf")

    def test_unreachable_due_to_mode(self):
        """Create a graph where driving cannot reach the goal (walking-only path)."""
        g = NavGraph()
        g.add_node(NavNode("S", "S", NavNodeType.INTERSECTION, 0, 0, 0))
        g.add_node(NavNode("G", "G", NavNodeType.INTERSECTION, 0, 100, 0))
        g.add_edge(Edge(from_id="S", to_id="G", weight=100, road_type=RoadType.WALKING_PATH,
                        allowed_modes={TransportMode.WALKING}))
        result = dijkstra(g, "S", "G", TransportMode.DRIVING)
        assert result["total_distance"] == float("inf")
        assert result["path"] == []

    def test_blocked_edge(self):
        g = _make_simple_graph()
        g.block_edge("N1", "N2")
        g.block_edge("N2", "N1")
        result = dijkstra(g, "N1", "N3", TransportMode.DRIVING)
        # With N1-N2 blocked, driving has no route (walking path not available for driving)
        assert result["total_distance"] == float("inf")

    def test_blocked_edges_set(self):
        g = _make_simple_graph()
        result = dijkstra(g, "N1", "N3", TransportMode.DRIVING,
                         blocked_edges={("N1", "N2")})
        assert result["total_distance"] == float("inf")


class TestAStar:
    def test_simple_path(self):
        g = _make_simple_graph()
        result = a_star(g, "N1", "N3", "euclidean", TransportMode.DRIVING)
        assert result["path"] == ["N1", "N2", "N3"]
        assert result["total_distance"] == 200.0

    def test_with_mode_filtering(self):
        g = _make_simple_graph()
        result = a_star(g, "N1", "N3", "euclidean", TransportMode.WALKING)
        assert len(result["path"]) > 0


class TestBFS:
    def test_simple_path(self):
        g = _make_simple_graph()
        result = bfs_shortest_path(g, "N1", "N3", TransportMode.DRIVING)
        assert result["path"] == ["N1", "N2", "N3"]

    def test_mode_filtering(self):
        g = NavGraph()
        g.add_node(NavNode("S", "S", NavNodeType.INTERSECTION, 0, 0, 0))
        g.add_node(NavNode("G", "G", NavNodeType.INTERSECTION, 0, 100, 0))
        g.add_edge(Edge(from_id="S", to_id="G", weight=100, road_type=RoadType.WALKING_PATH,
                        allowed_modes={TransportMode.WALKING}))
        result = bfs_shortest_path(g, "S", "G", TransportMode.DRIVING)
        assert result["path"] == []


class TestBidirectional:
    def test_bidi_dijkstra(self):
        g = _make_simple_graph()
        result = bidirectional_dijkstra(g, "N1", "N3", TransportMode.DRIVING)
        assert result["total_distance"] == 200.0

    def test_bidi_bfs(self):
        g = _make_simple_graph()
        result = bidirectional_bfs(g, "N1", "N3", TransportMode.DRIVING)
        assert len(result["path"]) > 0


class TestCongestionAvoidance:
    def test_avoid_congested(self):
        g = _make_simple_graph()
        # Congest N1-N2
        g.apply_congestion("N1", "N2", 3.0)
        g.apply_congestion("N2", "N1", 3.0)
        result = congestion_avoidance_dijkstra(
            g, "N1", "N3", TransportMode.WALKING, congestion_threshold=1.5,
        )
        # Walking should take the uncongested path through N4
        # But N4 path is 300 total vs N1-N2-N3 is 200 * 3 = 600 effective
        assert len(result["path"]) > 0


class TestMultiCriteria:
    def test_multi_criteria(self):
        g = _make_simple_graph()
        result = multi_criteria_dijkstra(
            g, "N1", "N3", TransportMode.DRIVING,
            w_distance=0.5, w_time=0.5, w_cost=0.0,
        )
        assert result["total_distance"] > 0


class TestReroute:
    def test_reroute_from_blockage(self):
        g = _make_simple_graph()
        result = reroute_from_position(
            g, ["N1", "N2", "N3"], "N1", "N3",
            TransportMode.DRIVING,
            blocked_edges={("N1", "N2")},
        )
        # With N1→N2 blocked and driving mode, path should be empty (unreachable)
        assert len(result["path"]) == 0

    def test_reroute_success(self):
        g = _make_simple_graph()
        result = reroute_from_position(
            g, ["N1", "N2", "N3"], "N1", "N3",
            TransportMode.DRIVING,
            blocked_edges=set(),
        )
        # Should find the direct path
        assert len(result["path"]) == 3
        assert result["total_distance"] == 200.0
