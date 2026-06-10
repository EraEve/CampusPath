"""Tests for the Building model — map loading, pathfinding,
algorithm comparison, and validation.
"""

import os
import json
import pytest
from backend.models.building import Building
from backend.models.graph import AdjacencyListGraph
from backend.models.node import Node, NodeType


# Path to the campus building JSON
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
BUILDING_JSON = os.path.join(DATA_DIR, "campus_building.json")


@pytest.fixture
def building() -> Building:
    """Load the real campus building map."""
    b = Building(BUILDING_JSON)
    return b


class TestBuildingLoad:
    """Map loading and graph construction."""

    def test_load_from_json_succeeds(self, building):
        assert building.name == "计算机学院教学楼 A"
        assert building.floors == [1, 2, 3, 4]
        assert building.graph.total_vertices > 50
        assert building.graph.total_edges > 100

    def test_all_floors_have_nodes(self, building):
        for floor in [1, 2, 3, 4]:
            nodes = building.graph.get_nodes_by_floor(floor)
            assert len(nodes) >= 10, \
                f"Floor {floor} has only {len(nodes)} nodes"

    def test_vertical_connectors_exist(self, building):
        """Stairs and elevators must have nodes on every floor."""
        for floor in [1, 2, 3, 4]:
            assert building.graph.has_node(f"F{floor}-STAIR-A"), \
                f"Missing STAIR-A on floor {floor}"
            assert building.graph.has_node(f"F{floor}-STAIR-B"), \
                f"Missing STAIR-B on floor {floor}"
            assert building.graph.has_node(f"F{floor}-ELEV-1"), \
                f"Missing ELEV-1 on floor {floor}"

    def test_validation_passes(self, building):
        issues = building.validate()
        assert issues == [], f"Validation found issues: {issues}"

    def test_graph_connected(self, building):
        """A* should find a path between any two rooms."""
        path = building.find_path("F1-ENTRANCE", "F4-ROOFTOP", algorithm="dijkstra")
        assert len(path["path"]) > 0, "No path from entrance to rooftop"
        assert path["total_distance"] < float("inf")


class TestBuildingPathfinding:
    """Pathfinding through the Building interface."""

    def test_find_path_dijkstra(self, building):
        result = building.find_path("F1-R101", "F1-R103", algorithm="dijkstra")
        assert len(result["path"]) >= 2
        assert result["path"][0] == "F1-R101"
        assert result["path"][-1] == "F1-R103"
        assert result["total_distance"] > 0

    def test_find_path_a_star_all_heuristics(self, building):
        for h in ["euclidean", "manhattan", "floor_aware"]:
            result = building.find_path(
                "F1-R101", "F3-RESEARCH1", algorithm="a_star", heuristic=h
            )
            assert len(result["path"]) > 2, \
                f"A*({h}) returned empty path"
            assert result["total_distance"] < float("inf")

    def test_find_path_bfs(self, building):
        result = building.find_path("F1-R101", "F1-R104", algorithm="bfs")
        assert len(result["path"]) >= 2

    def test_find_path_bidirectional(self, building):
        result_bfs = building.find_path(
            "F1-R101", "F2-R204", algorithm="bidirectional_bfs"
        )
        result_dij = building.find_path(
            "F1-R101", "F2-R204", algorithm="bidirectional_dijkstra"
        )
        assert len(result_bfs["path"]) > 0
        assert len(result_dij["path"]) > 0

    def test_invalid_algorithm_raises(self, building):
        with pytest.raises(ValueError, match="Unknown algorithm"):
            building.find_path("F1-R101", "F1-R102", algorithm="invalid_algo")


class TestAlgorithmComparison:
    """Experiment framework: compare_algorithms and batch_compare."""

    def test_compare_algorithms_returns_all_7(self, building):
        result = building.compare_algorithms("F1-R101", "F4-CONF1")
        assert "results" in result
        expected_algos = [
            "bfs", "dijkstra",
            "a_star_euclidean", "a_star_manhattan", "a_star_floor_aware",
            "bidirectional_bfs", "bidirectional_dijkstra",
        ]
        for algo in expected_algos:
            assert algo in result["results"], f"Missing {algo}"
            assert "error" not in result["results"][algo], \
                f"{algo} errored: {result['results'][algo].get('error')}"

    def test_compare_has_comparison_summary(self, building):
        result = building.compare_algorithms("F1-ENTRANCE", "F4-MEET1")
        assert "comparison" in result
        comp = result["comparison"]
        assert "shortest_distance" in comp
        assert "winner_by_distance" in comp

    def test_batch_compare_all_10_scenarios(self, building):
        scenarios_path = os.path.join(DATA_DIR, "test_scenarios.json")
        with open(scenarios_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        scenarios = data["scenarios"]
        result = building.batch_compare(scenarios)

        assert len(result["scenarios"]) == 10
        assert "aggregate" in result
        agg = result["aggregate"]
        assert "avg_distance_m" in agg
        assert "avg_nodes_visited" in agg
        assert "avg_time_ms" in agg
        assert "optimality_rate_vs_dijkstra" in agg


class TestBuildingUtilities:
    """Utility methods: floor layout, node labels, random pairs."""

    def test_get_floor_layout(self, building):
        layout = building.get_floor_layout(1)
        assert layout["floor"] == 1
        assert len(layout["nodes"]) > 0
        assert len(layout["edges"]) > 0

    def test_get_all_node_labels(self, building):
        labels = building.get_all_node_labels()
        assert len(labels) == building.graph.total_vertices
        for item in labels:
            assert "node_id" in item
            assert "name" in item
            assert "floor" in item

    def test_get_building_info(self, building):
        info = building.get_building_info()
        assert info["name"] == "计算机学院教学楼 A"
        assert info["total_vertices"] > 0
        assert info["total_edges"] > 0

    def test_get_random_node_pair_same_floor(self, building):
        for _ in range(10):
            start, goal = building.get_random_node_pair(same_floor=True)
            assert building.graph.has_node(start)
            assert building.graph.has_node(goal)
            s_node = building.graph.get_node(start)
            g_node = building.graph.get_node(goal)
            assert s_node.floor == g_node.floor
