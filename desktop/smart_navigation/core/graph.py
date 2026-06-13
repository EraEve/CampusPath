"""Extended adjacency-list graph with road-type-aware Edge objects.

Key extension over CampusPath's AdjacencyListGraph:
Instead of storing List[Tuple[str, float]] for neighbors, this stores
List[Edge] objects — enabling transport mode filtering, congestion
awareness, road type routing, and blockage handling.

This is THE central data structure — all algorithms and services
read from and write to this graph.
"""

from typing import Dict, Iterator, List, Optional, Set, Tuple

from .node import NavNode
from .edge import Edge
from ..models.transport import TransportMode, RoadType


class NavGraph:
    """Sparse directed graph with road-type-aware edges.

    Nodes: HashMap (Dict[str, NavNode]) for O(1) lookup.
    Edges: Per-vertex adjacency lists of Edge objects.

    Supports mode-filtered neighbor iteration, congestion updates,
    and blockage toggling — all without auxiliary data structures.
    """

    def __init__(self) -> None:
        self.vertices: Dict[str, NavNode] = {}
        self._edges: Dict[str, List[Edge]] = {}

    # ------------------------------------------------------------------
    # Vertex operations
    # ------------------------------------------------------------------

    def add_node(self, node: NavNode) -> None:
        """Add a vertex to the graph. O(1)."""
        if node.node_id in self.vertices:
            raise ValueError(f"Node '{node.node_id}' already exists.")
        self.vertices[node.node_id] = node
        self._edges[node.node_id] = []

    def remove_node(self, node_id: str) -> None:
        """Remove a vertex and all incident edges. O(|V| + |E|)."""
        if node_id not in self.vertices:
            raise KeyError(f"Node '{node_id}' not found.")
        for other_id in self._edges:
            if other_id == node_id:
                continue
            self._edges[other_id] = [
                e for e in self._edges[other_id] if e.to_id != node_id
            ]
        del self._edges[node_id]
        del self.vertices[node_id]

    def get_node(self, node_id: str) -> Optional[NavNode]:
        """Return the NavNode, or None if not found. O(1)."""
        return self.vertices.get(node_id)

    def has_node(self, node_id: str) -> bool:
        """Return True if node_id is in the graph. O(1)."""
        return node_id in self.vertices

    def get_all_nodes(self) -> List[str]:
        """Return all node IDs. O(|V|)."""
        return list(self.vertices.keys())

    def get_nodes_by_floor(self, floor: int) -> List[str]:
        """Return node IDs on a given floor. O(|V|)."""
        return [nid for nid, n in self.vertices.items() if n.floor == floor]

    def get_nodes_by_scene(self, scene_id: str) -> List[str]:
        """Return node IDs belonging to a specific scene. O(|V|)."""
        return [nid for nid, n in self.vertices.items() if n.scene_id == scene_id]

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(self, edge: Edge) -> None:
        """Add a directed edge. O(1). Overwrites if same from→to exists."""
        if edge.from_id not in self.vertices:
            raise KeyError(f"Source node '{edge.from_id}' not found.")
        if edge.to_id not in self.vertices:
            raise KeyError(f"Target node '{edge.to_id}' not found.")
        if edge.weight < 0:
            raise ValueError(f"Negative edge weight ({edge.weight}) not allowed.")

        neighbors = self._edges[edge.from_id]
        for i, existing in enumerate(neighbors):
            if existing.to_id == edge.to_id:
                neighbors[i] = edge
                return
        neighbors.append(edge)

    def add_simple_edge(self, from_id: str, to_id: str, weight: float,
                        road_type: RoadType = RoadType.PATH,
                        one_way: bool = False,
                        allowed_modes: Optional[Set[TransportMode]] = None,
                        speed_limit: float = 0.0,
                        name: str = "") -> Edge:
        """Convenience method: create and add an edge in one call. Returns the Edge."""
        edge = Edge(
            from_id=from_id, to_id=to_id, weight=weight,
            road_type=road_type, one_way=one_way,
            allowed_modes=allowed_modes or set(),
            speed_limit=speed_limit, name=name,
        )
        self.add_edge(edge)
        return edge

    def add_undirected_edge(self, from_id: str, to_id: str, weight: float,
                            road_type: RoadType = RoadType.PATH,
                            allowed_modes: Optional[Set[TransportMode]] = None,
                            speed_limit: float = 0.0,
                            name: str = "") -> Tuple[Edge, Edge]:
        """Add edges in both directions. Returns (forward, reverse) Edge pair."""
        fwd = self.add_simple_edge(from_id, to_id, weight, road_type,
                                   False, allowed_modes, speed_limit, name)
        rev = self.add_simple_edge(to_id, from_id, weight, road_type,
                                   False, allowed_modes, speed_limit, name)
        return (fwd, rev)

    def remove_edge(self, from_id: str, to_id: str) -> None:
        """Remove a directed edge. O(degree(from_id))."""
        if from_id not in self._edges:
            raise KeyError(f"Source node '{from_id}' not found.")
        self._edges[from_id] = [
            e for e in self._edges[from_id] if e.to_id != to_id
        ]

    def get_edge(self, from_id: str, to_id: str) -> Optional[Edge]:
        """Return the Edge object, or None. O(degree(from_id))."""
        for e in self._edges.get(from_id, []):
            if e.to_id == to_id:
                return e
        return None

    def get_weight(self, from_id: str, to_id: str) -> float:
        """Return effective edge weight, or INF if no edge/blocked."""
        edge = self.get_edge(from_id, to_id)
        if edge is None:
            return float("inf")
        return edge.effective_weight

    def has_edge(self, from_id: str, to_id: str) -> bool:
        """Return True if edge exists. O(degree(from_id))."""
        return self.get_edge(from_id, to_id) is not None

    def get_neighbors(self, node_id: str) -> List[Tuple[str, float]]:
        """Return (neighbor_id, effective_weight) pairs. Basic API for simple algos."""
        return [(e.to_id, e.effective_weight) for e in self._edges.get(node_id, [])]

    def get_edges(self, node_id: str) -> List[Edge]:
        """Return all outgoing Edge objects. O(1) to return list ref."""
        return list(self._edges.get(node_id, []))

    def get_edges_for_mode(self, node_id: str, mode: TransportMode,
                           skip_blocked: bool = True) -> List[Edge]:
        """Return edges usable by the given transport mode.

        Filters by allowed_modes, optionally skips blocked edges.
        This is the PRIMARY neighbor access method for mode-aware algorithms.

        Args:
            node_id: The current node.
            mode: The transport mode to filter by.
            skip_blocked: If True (default), exclude blocked edges.

        Returns:
            List of usable Edge objects.
        """
        result = []
        for edge in self._edges.get(node_id, []):
            if skip_blocked and edge.is_blocked:
                continue
            if edge.allows_mode(mode):
                result.append(edge)
        return result

    # ------------------------------------------------------------------
    # Congestion and blockage
    # ------------------------------------------------------------------

    def apply_congestion(self, from_id: str, to_id: str, factor: float):
        """Set congestion_factor on an edge."""
        edge = self.get_edge(from_id, to_id)
        if edge:
            edge.congestion_factor = factor

    def block_edge(self, from_id: str, to_id: str):
        """Mark an edge as blocked (impassable)."""
        edge = self.get_edge(from_id, to_id)
        if edge:
            edge.is_blocked = True

    def unblock_edge(self, from_id: str, to_id: str):
        """Clear blockage on an edge."""
        edge = self.get_edge(from_id, to_id)
        if edge:
            edge.is_blocked = False

    def reset_traffic(self):
        """Reset all congestion and blockage on all edges."""
        for edges in self._edges.values():
            for edge in edges:
                edge.congestion_factor = 1.0
                edge.is_blocked = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total_vertices(self) -> int:
        return len(self.vertices)

    @property
    def total_edges(self) -> int:
        return sum(len(edges) for edges in self._edges.values())

    def get_floors(self) -> List[int]:
        """Return sorted unique floor numbers."""
        return sorted(set(n.floor for n in self.vertices.values()))

    def get_poi_nodes(self) -> List[NavNode]:
        """Return all nodes with a POI category."""
        return [n for n in self.vertices.values() if n.poi_category is not None]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize entire graph to JSON-compatible dict."""
        nodes = [node.to_dict() for node in self.vertices.values()]
        edges_out = []
        for from_id, edge_list in self._edges.items():
            for edge in edge_list:
                edges_out.append(edge.to_dict())
        return {"nodes": nodes, "edges": edges_out}

    @classmethod
    def from_dict(cls, data: dict, scene_id: str = "") -> "NavGraph":
        """Deserialize from dictionary."""
        graph = cls()
        for node_data in data.get("nodes", []):
            node_data["scene_id"] = scene_id
            node = NavNode.from_dict(node_data)
            graph.add_node(node)
        for edge_data in data.get("edges", []):
            edge = Edge.from_dict(edge_data)
            graph.add_edge(edge)
        return graph

    # ------------------------------------------------------------------
    # Magic methods
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[str]:
        return iter(self.vertices)

    def __len__(self) -> int:
        return self.total_vertices

    def __contains__(self, node_id: str) -> bool:
        return self.has_node(node_id)

    def __repr__(self) -> str:
        return f"NavGraph(vertices={self.total_vertices}, edges={self.total_edges})"
