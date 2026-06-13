"""Tests for NavGraph with road-type-aware edges."""

import pytest
from smart_navigation.core.graph import NavGraph
from smart_navigation.core.node import NavNode, NavNodeType
from smart_navigation.core.edge import Edge
from smart_navigation.models.transport import TransportMode, RoadType


class TestNavGraphBasic:
    """Basic vertex and edge operations."""

    def test_add_node(self):
        g = NavGraph()
        n = NavNode(node_id="N1", name="Test", node_type=NavNodeType.INTERSECTION)
        g.add_node(n)
        assert g.has_node("N1")
        assert g.total_vertices == 1

    def test_add_duplicate_node_raises(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "Test"))
        with pytest.raises(ValueError):
            g.add_node(NavNode("N1", "Test2"))

    def test_remove_node(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "A"))
        g.add_node(NavNode("N2", "B"))
        g.remove_node("N1")
        assert not g.has_node("N1")
        assert g.has_node("N2")

    def test_add_edge(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "A", x=0, y=0))
        g.add_node(NavNode("N2", "B", x=100, y=0))
        e = Edge(from_id="N1", to_id="N2", weight=100, road_type=RoadType.MAIN_ROAD)
        g.add_edge(e)
        assert g.has_edge("N1", "N2")
        assert g.total_edges == 1

    def test_add_undirected_edge(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "A", x=0, y=0))
        g.add_node(NavNode("N2", "B", x=100, y=0))
        fwd, rev = g.add_undirected_edge("N1", "N2", 100, RoadType.MAIN_ROAD)
        assert g.has_edge("N1", "N2")
        assert g.has_edge("N2", "N1")
        assert g.total_edges == 2

    def test_negative_weight_raises(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "A"))
        g.add_node(NavNode("N2", "B"))
        with pytest.raises(ValueError):
            g.add_edge(Edge(from_id="N1", to_id="N2", weight=-5))

    def test_get_node(self):
        g = NavGraph()
        n = NavNode("N1", "Test", x=10, y=20)
        g.add_node(n)
        found = g.get_node("N1")
        assert found is not None
        assert found.x == 10
        assert found.y == 20


class TestModeFiltering:
    """Transport mode filtering on edges."""

    def test_get_edges_for_mode_filters_correctly(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "A", x=0, y=0))
        g.add_node(NavNode("N2", "B", x=100, y=0))
        g.add_node(NavNode("N3", "C", x=0, y=100))

        # Add a driving edge and a walking edge
        e1 = Edge(from_id="N1", to_id="N2", weight=100, road_type=RoadType.MAIN_ROAD,
                  allowed_modes={TransportMode.DRIVING, TransportMode.WALKING})
        e2 = Edge(from_id="N1", to_id="N3", weight=50, road_type=RoadType.WALKING_PATH,
                  allowed_modes={TransportMode.WALKING})
        g.add_edge(e1)
        g.add_edge(e2)

        driving_edges = g.get_edges_for_mode("N1", TransportMode.DRIVING)
        walking_edges = g.get_edges_for_mode("N1", TransportMode.WALKING)

        assert len(driving_edges) == 1
        assert driving_edges[0].to_id == "N2"
        assert len(walking_edges) == 2

    def test_highway_excludes_walking(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "A", x=0, y=0))
        g.add_node(NavNode("N2", "B", x=100, y=0))

        e = Edge(from_id="N1", to_id="N2", weight=100, road_type=RoadType.HIGHWAY)
        g.add_edge(e)

        driving = g.get_edges_for_mode("N1", TransportMode.DRIVING)
        walking = g.get_edges_for_mode("N1", TransportMode.WALKING)

        assert len(driving) == 1
        assert len(walking) == 0  # highways exclude walkers


class TestCongestionBlockage:
    """Congestion and blockage edge operations."""

    def test_block_edge(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "A", x=0, y=0))
        g.add_node(NavNode("N2", "B", x=100, y=0))
        g.add_edge(Edge(from_id="N1", to_id="N2", weight=100))

        g.block_edge("N1", "N2")
        edge = g.get_edge("N1", "N2")
        assert edge.is_blocked
        assert edge.effective_weight == float("inf")

    def test_unblock_edge(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "A", x=0, y=0))
        g.add_node(NavNode("N2", "B", x=100, y=0))
        g.add_edge(Edge(from_id="N1", to_id="N2", weight=100))

        g.block_edge("N1", "N2")
        g.unblock_edge("N1", "N2")
        edge = g.get_edge("N1", "N2")
        assert not edge.is_blocked
        assert edge.effective_weight == 100.0

    def test_congestion_factor(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "A", x=0, y=0))
        g.add_node(NavNode("N2", "B", x=100, y=0))
        g.add_edge(Edge(from_id="N1", to_id="N2", weight=100))

        g.apply_congestion("N1", "N2", 2.0)
        edge = g.get_edge("N1", "N2")
        assert edge.congestion_factor == 2.0
        assert edge.effective_weight == 200.0

    def test_reset_traffic(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "A", x=0, y=0))
        g.add_node(NavNode("N2", "B", x=100, y=0))
        g.add_edge(Edge(from_id="N1", to_id="N2", weight=100))

        g.block_edge("N1", "N2")
        g.apply_congestion("N1", "N2", 2.0)
        g.reset_traffic()

        edge = g.get_edge("N1", "N2")
        assert not edge.is_blocked
        assert edge.congestion_factor == 1.0


class TestSerialization:
    """Graph serialization round-trip."""

    def test_to_dict_and_from_dict(self):
        g = NavGraph()
        g.add_node(NavNode("N1", "A", NavNodeType.INTERSECTION, 0, 10, 20, "test_scene"))
        g.add_node(NavNode("N2", "B", NavNodeType.POI, 0, 30, 40, "test_scene"))
        g.add_edge(Edge(from_id="N1", to_id="N2", weight=100, road_type=RoadType.MAIN_ROAD,
                        allowed_modes={TransportMode.DRIVING, TransportMode.WALKING}))

        data = g.to_dict()
        g2 = NavGraph.from_dict(data, scene_id="test_scene")

        assert g2.total_vertices == 2
        assert g2.total_edges == 1
        assert g2.has_edge("N1", "N2")
        edge = g2.get_edge("N1", "N2")
        assert edge.road_type == RoadType.MAIN_ROAD
        assert edge.weight == 100
