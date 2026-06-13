"""Tests for MapManager — loading, caching, CRUD."""

import os
import pytest
from smart_navigation.core.map_manager import MapManager


class TestMapManager:
    def test_load_demo_maps(self):
        m = MapManager()
        maps_dir = os.path.join(
            os.path.dirname(__file__), "..", "smart_navigation", "data", "maps"
        )
        scenes = m.load_all_demo_maps()
        assert len(scenes) == 4
        assert "campus_01" in scenes
        assert "mall_01" in scenes
        assert "city_01" in scenes
        assert "underground_01" in scenes

    def test_get_graph(self):
        m = MapManager()
        m.load_all_demo_maps()
        graph = m.get_graph("campus_01")
        assert graph is not None
        assert graph.total_vertices == 25
        assert graph.total_edges == 64

    def test_get_scene(self):
        m = MapManager()
        m.load_all_demo_maps()
        scene = m.get_scene("campus_01")
        assert scene is not None
        assert scene.name is not None

    def test_list_scenes(self):
        m = MapManager()
        m.load_all_demo_maps()
        scenes = m.list_scenes()
        assert len(scenes) == 4

    def test_get_all_nodes_for_scene(self):
        m = MapManager()
        m.load_all_demo_maps()
        nodes = m.get_all_nodes_for_scene("campus_01")
        assert len(nodes) == 25
        assert any(n["node_id"] == "N001" for n in nodes)

    def test_mall_vertical_connectors(self):
        """Verify that the mall map has vertical connectors between floors."""
        m = MapManager()
        m.load_all_demo_maps()
        graph = m.get_graph("mall_01")
        assert graph is not None
        # Should have edges between floors (elevator, stairs)
        assert graph.has_edge("F1-EL1", "F2-EL1") or graph.has_edge("F1-ST1", "F2-ST1")

    def test_underground_subway(self):
        """Verify that the underground map has subway edges."""
        m = MapManager()
        m.load_all_demo_maps()
        graph = m.get_graph("underground_01")
        assert graph.has_edge("U01", "U02")  # subway tunnel
