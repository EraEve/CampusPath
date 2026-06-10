"""Tests for AdjacencyListGraph — the core graph data structure.

Covers: node/edge CRUD, neighbor iteration, multi-floor topology,
serialization round-trip, and edge case handling.
"""

import pytest
from backend.models.node import Node, NodeType
from backend.models.graph import AdjacencyListGraph


def _make_node(nid: str, floor: int = 1, x: float = 0, y: float = 0,
               ntype: NodeType = NodeType.ROOM) -> Node:
    """Helper: create a minimal Node for testing."""
    return Node(node_id=nid, name=nid, node_type=ntype, floor=floor, x=x, y=y)


class TestGraphVertexOps:
    """Vertex addition, removal, and access."""

    def test_add_node(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        assert g.has_node("A")
        assert g.total_vertices == 1

    def test_add_duplicate_node_raises(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        with pytest.raises(ValueError, match="already exists"):
            g.add_node(_make_node("A"))

    def test_remove_node_cleans_edges(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_edge("A", "B", 5.0)
        g.add_edge("B", "A", 5.0)

        g.remove_node("A")

        assert not g.has_node("A")
        assert g.has_node("B")
        # B's adjacency should no longer reference A
        assert not g.has_edge("B", "A")
        assert g.total_edges == 0

    def test_get_node_returns_none_for_missing(self):
        g = AdjacencyListGraph()
        assert g.get_node("nonexistent") is None

    def test_get_all_nodes(self):
        g = AdjacencyListGraph()
        for nid in ["A", "B", "C"]:
            g.add_node(_make_node(nid))
        assert set(g.get_all_nodes()) == {"A", "B", "C"}

    def test_get_nodes_by_floor(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("F1-R1", floor=1))
        g.add_node(_make_node("F1-R2", floor=1))
        g.add_node(_make_node("F2-R1", floor=2))
        assert len(g.get_nodes_by_floor(1)) == 2
        assert len(g.get_nodes_by_floor(2)) == 1
        assert g.get_nodes_by_floor(3) == []


class TestGraphEdgeOps:
    """Edge addition, removal, and access."""

    def test_add_and_get_edge(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_edge("A", "B", 3.5)

        assert g.has_edge("A", "B")
        assert not g.has_edge("B", "A")  # directed
        assert g.get_weight("A", "B") == 3.5

    def test_add_edge_nonexistent_raises(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        with pytest.raises(KeyError, match="not found"):
            g.add_edge("A", "B", 1.0)

    def test_add_edge_negative_weight_raises(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        with pytest.raises(ValueError, match="Negative"):
            g.add_edge("A", "B", -1.0)

    def test_update_existing_edge(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_edge("A", "B", 5.0)
        g.add_edge("A", "B", 10.0)  # update
        assert g.get_weight("A", "B") == 10.0
        assert g.total_edges == 1  # not duplicated

    def test_remove_edge(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_edge("A", "B", 5.0)
        g.remove_edge("A", "B")
        assert not g.has_edge("A", "B")

    def test_get_neighbors(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        g.add_node(_make_node("C"))
        g.add_edge("A", "B", 1.0)
        g.add_edge("A", "C", 2.0)

        neighbors = g.get_neighbors("A")
        neighbor_ids = {nid for nid, _ in neighbors}
        assert neighbor_ids == {"B", "C"}


class TestGraphSerialization:
    """Round-trip JSON serialization."""

    def test_to_dict_from_dict_roundtrip(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A", floor=1, x=10, y=20, ntype=NodeType.ROOM))
        g.add_node(_make_node("B", floor=1, x=30, y=40, ntype=NodeType.CORRIDOR))
        g.add_edge("A", "B", 5.0)
        g.add_edge("B", "A", 5.0)

        data = g.to_dict()
        g2 = AdjacencyListGraph.from_dict(data)

        assert g2.total_vertices == g.total_vertices
        assert g2.total_edges == g.total_edges
        assert g2.has_node("A") and g2.has_node("B")
        assert g2.has_edge("A", "B") and g2.has_edge("B", "A")
        assert g2.get_node("A").x == 10
        assert g2.get_node("A").y == 20

    def test_empty_graph_roundtrip(self):
        g = AdjacencyListGraph()
        data = g.to_dict()
        g2 = AdjacencyListGraph.from_dict(data)
        assert g2.total_vertices == 0


class TestGraphMagicMethods:
    """__iter__, __len__, __contains__."""

    def test_iter_yields_node_ids(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        g.add_node(_make_node("B"))
        assert set(g) == {"A", "B"}

    def test_len_returns_vertex_count(self):
        g = AdjacencyListGraph()
        assert len(g) == 0
        g.add_node(_make_node("A"))
        assert len(g) == 1

    def test_contains(self):
        g = AdjacencyListGraph()
        g.add_node(_make_node("A"))
        assert "A" in g
        assert "B" not in g
