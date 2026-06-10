"""Adjacency-List Graph for indoor navigation.

A sparse, directed-graph implementation optimized for building floor plans
where |E| ≈ 2|V| (each node connects to 2-4 neighbors on average).

Key design decisions for the Data Structures course:
1. Adjacency LIST (not matrix): O(|V|+|E|) space, O(degree(v)) neighbor
   iteration — ideal for sparse building graphs.
2. Vertices stored in a HashMap (Python dict): O(1) node lookup by ID.
3. Edges stored per-vertex: List[(neighbor_id, weight)] for fast traversal.
4. Supports directed edges; undirected graphs add both directions.
5. Full serialization round-trip: to_dict() / from_dict().

This is one of the THREE core data structures demonstrated in the course
report (alongside MinHeap and Queue/Stack).
"""

from typing import Dict, List, Optional, Tuple, Iterator

from .node import Node


class AdjacencyListGraph:
    """Sparse graph using adjacency lists.

    Nodes are stored in a HashMap (vertices: Dict[str, Node]).
    Edges are stored as per-vertex adjacency lists of (neighbor_id, weight).

    All vertex access is O(1). Edge existence checks are O(degree(v)).
    """

    def __init__(self) -> None:
        self.vertices: Dict[str, Node] = {}           # node_id → Node
        self.adjacency: Dict[str, List[Tuple[str, float]]] = {}  # node_id → [(neighbor_id, weight)]

    # ------------------------------------------------------------------
    # Vertex operations
    # ------------------------------------------------------------------

    def add_node(self, node: Node) -> None:
        """Add a vertex to the graph. O(1).

        Raises ValueError if node_id already exists.
        """
        if node.node_id in self.vertices:
            raise ValueError(f"Node '{node.node_id}' already exists in graph.")
        self.vertices[node.node_id] = node
        self.adjacency[node.node_id] = []

    def remove_node(self, node_id: str) -> None:
        """Remove a vertex and all incident edges. O(|V| + |E|).

        This scans ALL adjacency lists to remove incoming edges,
        then deletes the vertex and its outgoing edges.
        """
        if node_id not in self.vertices:
            raise KeyError(f"Node '{node_id}' not found.")

        # Remove incoming edges from all other vertices
        for other_id in self.adjacency:
            if other_id == node_id:
                continue
            self.adjacency[other_id] = [
                (nid, w) for nid, w in self.adjacency[other_id]
                if nid != node_id
            ]

        # Remove the vertex and its outgoing edges
        del self.adjacency[node_id]
        del self.vertices[node_id]

    def get_node(self, node_id: str) -> Optional[Node]:
        """Return the Node object, or None if not found. O(1)."""
        return self.vertices.get(node_id)

    def has_node(self, node_id: str) -> bool:
        """Return True if node_id is a vertex in the graph. O(1)."""
        return node_id in self.vertices

    def get_all_nodes(self) -> List[str]:
        """Return all node IDs. O(|V|)."""
        return list(self.vertices.keys())

    def get_nodes_by_floor(self, floor: int) -> List[str]:
        """Return node IDs on a given floor. O(|V|)."""
        return [
            nid for nid, node in self.vertices.items()
            if node.floor == floor
        ]

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def add_edge(self, from_id: str, to_id: str, weight: float) -> None:
        """Add a directed edge from_id → to_id with given weight. O(1).

        Raises KeyError if either endpoint does not exist.
        """
        if from_id not in self.vertices:
            raise KeyError(f"Source node '{from_id}' not found.")
        if to_id not in self.vertices:
            raise KeyError(f"Target node '{to_id}' not found.")
        if weight < 0:
            raise ValueError(f"Negative edge weight ({weight}) not allowed.")

        # Overwrite if edge already exists
        neighbors = self.adjacency[from_id]
        for i, (nid, _) in enumerate(neighbors):
            if nid == to_id:
                neighbors[i] = (to_id, weight)
                return
        neighbors.append((to_id, weight))

    def remove_edge(self, from_id: str, to_id: str) -> None:
        """Remove a directed edge from_id → to_id. O(degree(from_id))."""
        if from_id not in self.adjacency:
            raise KeyError(f"Source node '{from_id}' not found.")
        self.adjacency[from_id] = [
            (nid, w) for nid, w in self.adjacency[from_id]
            if nid != to_id
        ]

    def get_neighbors(self, node_id: str) -> List[Tuple[str, float]]:
        """Return (neighbor_id, weight) pairs. O(1) to return, O(degree) to copy."""
        return list(self.adjacency.get(node_id, []))

    def get_weight(self, from_id: str, to_id: str) -> float:
        """Return edge weight, or -1.0 if no edge exists. O(degree(from_id))."""
        for nid, w in self.adjacency.get(from_id, []):
            if nid == to_id:
                return w
        return -1.0

    def has_edge(self, from_id: str, to_id: str) -> bool:
        """Return True if edge from_id → to_id exists. O(degree(from_id))."""
        return self.get_weight(from_id, to_id) >= 0

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def total_vertices(self) -> int:
        """Total number of vertices in the graph."""
        return len(self.vertices)

    @property
    def total_edges(self) -> int:
        """Total number of directed edges in the graph."""
        return sum(len(neighbors) for neighbors in self.adjacency.values())

    # ------------------------------------------------------------------
    # Serialization (JSON-compatible)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialize the entire graph to a JSON-compatible dictionary.

        Returns:
            {
                "nodes": [ {...node_dict...}, ... ],
                "edges": [ [from_id, to_id, weight], ... ]
            }
        """
        nodes = [node.to_dict() for node in self.vertices.values()]
        edges: List[List] = []
        for from_id, neighbors in self.adjacency.items():
            for to_id, weight in neighbors:
                edges.append([from_id, to_id, weight])
        return {"nodes": nodes, "edges": edges}

    @classmethod
    def from_dict(cls, data: dict) -> "AdjacencyListGraph":
        """Deserialize from a dictionary (inverse of to_dict)."""
        graph = cls()
        for node_data in data.get("nodes", []):
            node = Node.from_dict(node_data)
            graph.add_node(node)
        for edge in data.get("edges", []):
            from_id, to_id, weight = edge[0], edge[1], edge[2]
            graph.add_edge(from_id, to_id, weight)
        return graph

    # ------------------------------------------------------------------
    # Magic methods
    # ------------------------------------------------------------------

    def __iter__(self) -> Iterator[str]:
        """Iterate over all node IDs. Enables 'for nid in graph'."""
        return iter(self.vertices)

    def __len__(self) -> int:
        """Return the number of vertices. Enables len(graph)."""
        return self.total_vertices

    def __contains__(self, node_id: str) -> bool:
        """Enable 'node_id in graph' syntax."""
        return self.has_node(node_id)

    def __repr__(self) -> str:
        return (f"AdjacencyListGraph(vertices={self.total_vertices}, "
                f"edges={self.total_edges})")
