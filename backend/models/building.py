"""Building Model — multi-floor campus building with vertical connectors.

The Building class loads a JSON map definition, constructs the
AdjacencyListGraph (expanding corridor segments into explicit nodes,
wiring cross-floor connections), and provides a unified interface
for pathfinding and algorithm comparison.

Key responsibilities:
1. Parse campus_building.json into a graph.
2. Expand corridor segments into discrete graph nodes.
3. Create vertical edges (stairs/elevators) connecting floors.
4. Provide find_path() dispatching to any algorithm.
5. Provide compare_algorithms() for experiment framework.
6. Validate map integrity (connectivity, no orphan nodes).
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from .node import Node, NodeType
from .graph import AdjacencyListGraph

# Algorithm imports (lazy to avoid early loading issues)
from ..algorithms.dijkstra import dijkstra
from ..algorithms.a_star import a_star, HEURISTICS
from ..algorithms.bfs import bfs_shortest_path
from ..algorithms.bidirectional import bidirectional_bfs, bidirectional_dijkstra


class Building:
    """Multi-floor teaching building with indoor navigation capabilities.

    Loads from a JSON specification and constructs a weighted graph
    where nodes are rooms/corridors/stairs/elevators and edges are
    walkable paths with distance weights.

    Attributes:
        name: Building display name.
        floors: List of floor numbers.
        graph: The complete navigation graph (all floors + vertical edges).
        stairwell_ids: Stairwell node IDs organized by stairwell name.
        elevator_ids: Elevator node IDs organized by elevator name.
    """

    def __init__(self, json_path: str | None = None) -> None:
        """Initialize the building.

        Args:
            json_path: Path to campus_building.json. If None, uses
                       the default data file bundled with the project.
        """
        self.name: str = ""
        self.floors: List[int] = []
        self.graph: AdjacencyListGraph = AdjacencyListGraph()

        # Track vertical connectors by name for potential constraint queries
        self._vertical_connectors: Dict[str, Any] = {}

        if json_path is not None:
            self.load_from_json(json_path)

    # ------------------------------------------------------------------
    # Map loading
    # ------------------------------------------------------------------

    def load_from_json(self, filepath: str) -> None:
        """Load building map from a JSON specification file.

        Processing steps:
        1. Parse JSON.
        2. Create room/POI/entrance nodes.
        3. Expand corridor segments into discrete nodes.
        4. Add horizontal (same-floor) edges.
        5. Create stair/elevator nodes per floor.
        6. Add vertical (cross-floor) edges.
        7. Validate connectivity.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Map file not found: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        building_data = data["building"]
        self.name = building_data["name"]
        self.floors = building_data["floors"]
        self._vertical_connectors = data.get("vertical_connectors", {})

        # Phase 1: Create floor nodes (rooms + corridor segments)
        floor_data = data["floors"]
        for floor_str, floor_info in floor_data.items():
            floor_num = int(floor_str)
            self._create_floor_nodes(floor_num, floor_info, data)

        # Phase 2: Create vertical connector nodes (stairs, elevators)
        # MUST run before Phase 3 because floor edges reference these nodes.
        self._create_vertical_connectors(data)

        # Phase 3: Add same-floor edges (bidirectional for undirected walking)
        for floor_str, floor_info in floor_data.items():
            floor_num = int(floor_str)
            self._add_floor_edges(floor_num, floor_info)

    def _create_floor_nodes(
        self, floor: int, floor_info: dict, data: dict
    ) -> None:
        """Create all nodes for a single floor.

        Creates room/POI/entrance nodes and corridor segment nodes.
        """
        # Rooms, POIs, entrances
        for room in floor_info.get("rooms", []):
            node = Node(
                node_id=room["id"],
                name=room["name"],
                node_type=NodeType(room["type"]),
                floor=floor,
                x=room["x"],
                y=room["y"],
            )
            self.graph.add_node(node)

        # Corridor segments → explicit nodes
        for corridor in floor_info.get("corridors", []):
            for i, (seg_x, seg_y) in enumerate(corridor["segments"]):
                seg_id = f"{corridor['id']}-SEG{i}"
                node = Node(
                    node_id=seg_id,
                    name=f"{corridor['name']} 第{i+1}段",
                    node_type=NodeType.CORRIDOR,
                    floor=floor,
                    x=seg_x,
                    y=seg_y,
                )
                self.graph.add_node(node)

    def _add_floor_edges(self, floor: int, floor_info: dict) -> None:
        """Add bidirectional edges for a single floor.

        Building corridors are undirected — we add both directions
        for every edge listed in the JSON.
        """
        for edge in floor_info.get("edges", []):
            from_id, to_id, weight = edge[0], edge[1], float(edge[2])
            # Add both directions (undirected graph for walkable paths)
            self.graph.add_edge(from_id, to_id, weight)
            self.graph.add_edge(to_id, from_id, weight)

    def _create_vertical_connectors(self, data: dict) -> None:
        """Create stair/elevator nodes on each floor and connect them.

        Each connector type (STAIR-A, STAIR-B, ELEV-1) has a node on
        each floor it serves. Edges connect adjacent floors with the
        specified transition cost.
        """
        connectors = data.get("vertical_connectors", {})

        # Create stair nodes on each floor
        for stair in connectors.get("stairs", []):
            sid = stair["id"]
            for floor in stair["floors_connected"]:
                node_id = f"F{floor}-{sid}"
                if not self.graph.has_node(node_id):
                    node = Node(
                        node_id=node_id,
                        name=f"{stair['label']} ({floor}F)",
                        node_type=NodeType.STAIR,
                        floor=floor,
                        x=stair["x"],
                        y=stair["y"],
                    )
                    self.graph.add_node(node)

        # Create elevator nodes on each floor
        for elevator in connectors.get("elevators", []):
            eid = elevator["id"]
            for floor in elevator["floors_connected"]:
                node_id = f"F{floor}-{eid}"
                if not self.graph.has_node(node_id):
                    node = Node(
                        node_id=node_id,
                        name=f"{elevator['label']} ({floor}F)",
                        node_type=NodeType.ELEVATOR,
                        floor=floor,
                        x=elevator["x"],
                        y=elevator["y"],
                    )
                    self.graph.add_node(node)

        # Add vertical edges (bidirectional for going up AND down)
        for edge in data.get("vertical_edges", []):
            from_id, to_id, weight = edge[0], edge[1], float(edge[2])
            self.graph.add_edge(from_id, to_id, weight)
            self.graph.add_edge(to_id, from_id, weight)

    # ------------------------------------------------------------------
    # Pathfinding interface
    # ------------------------------------------------------------------

    def find_path(
        self,
        start_id: str,
        goal_id: str,
        algorithm: str = "dijkstra",
        heuristic: str = "euclidean",
        record_steps: bool = False,
    ) -> Dict[str, Any]:
        """Find a path between two nodes using the specified algorithm.

        Args:
            start_id: Starting node ID.
            goal_id: Target node ID.
            algorithm: One of "dijkstra", "a_star", "bfs",
                       "bidirectional_bfs", "bidirectional_dijkstra".
            heuristic: For A*, one of "euclidean", "manhattan", "floor_aware".
            record_steps: If True, include step-by-step data for animation.

        Returns:
            Standardized result dict with path, distance, stats.
        """
        if algorithm == "dijkstra":
            return dijkstra(self.graph, start_id, goal_id, record_steps=record_steps)
        elif algorithm == "a_star":
            return a_star(self.graph, start_id, goal_id, heuristic=heuristic, record_steps=record_steps)
        elif algorithm == "bfs":
            return bfs_shortest_path(self.graph, start_id, goal_id, record_steps=record_steps)
        elif algorithm == "bidirectional_bfs":
            return bidirectional_bfs(self.graph, start_id, goal_id, record_steps=record_steps)
        elif algorithm == "bidirectional_dijkstra":
            return bidirectional_dijkstra(self.graph, start_id, goal_id, record_steps=record_steps)
        else:
            raise ValueError(
                f"Unknown algorithm '{algorithm}'. "
                f"Choose from: dijkstra, a_star, bfs, "
                f"bidirectional_bfs, bidirectional_dijkstra"
            )

    # ------------------------------------------------------------------
    # Experiment framework
    # ------------------------------------------------------------------

    def compare_algorithms(
        self, start_id: str, goal_id: str
    ) -> Dict[str, Any]:
        """Run ALL algorithms on the same (start, goal) pair.

        This is the core experiment function for the course report.
        It runs BFS, Dijkstra, A* (3 heuristics), Bidirectional BFS,
        and Bidirectional Dijkstra — 7 variants total.

        Returns:
            {
                "start": start_id,
                "goal": goal_id,
                "results": {algorithm_name: result_dict, ...},
                "comparison": {
                    "shortest_distance": float,
                    "winner_by_distance": str,
                    "fewest_nodes_visited": int,
                    "winner_by_nodes": str,
                }
            }
        """
        algorithms_to_run = {
            "bfs": lambda: bfs_shortest_path(self.graph, start_id, goal_id),
            "dijkstra": lambda: dijkstra(self.graph, start_id, goal_id),
            "a_star_euclidean": lambda: a_star(
                self.graph, start_id, goal_id, heuristic="euclidean"
            ),
            "a_star_manhattan": lambda: a_star(
                self.graph, start_id, goal_id, heuristic="manhattan"
            ),
            "a_star_floor_aware": lambda: a_star(
                self.graph, start_id, goal_id, heuristic="floor_aware"
            ),
            "bidirectional_bfs": lambda: bidirectional_bfs(
                self.graph, start_id, goal_id
            ),
            "bidirectional_dijkstra": lambda: bidirectional_dijkstra(
                self.graph, start_id, goal_id
            ),
        }

        results = {}
        for name, func in algorithms_to_run.items():
            try:
                results[name] = func()
            except Exception as e:
                results[name] = {"error": str(e)}

        # Build comparison summary
        valid_results = {
            k: v for k, v in results.items()
            if "error" not in v and v["path"]
        }

        comparison = {}
        if valid_results:
            distances = {
                k: v["total_distance"] for k, v in valid_results.items()
                if v["total_distance"] < float("inf")
            }
            nodes_visited = {
                k: v["nodes_visited"] for k, v in valid_results.items()
            }

            if distances:
                comparison["shortest_distance"] = min(distances.values())
                comparison["winner_by_distance"] = min(
                    distances, key=distances.get
                )
            if nodes_visited:
                comparison["fewest_nodes_visited"] = min(nodes_visited.values())
                comparison["winner_by_nodes"] = min(
                    nodes_visited, key=nodes_visited.get
                )

        return {
            "start": start_id,
            "goal": goal_id,
            "results": results,
            "comparison": comparison,
        }

    def batch_compare(
        self, scenarios: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Run compare_algorithms on a batch of (start, goal) pairs.

        Args:
            scenarios: List of {"start": str, "goal": str, "label": str}.

        Returns:
            {
                "scenarios": [{scenario_with_results}, ...],
                "aggregate": {avg_distance, avg_nodes, optimality_rate, ...}
            }
        """
        scenario_results = []
        aggregate_distances = {k: [] for k in [
            "bfs", "dijkstra", "a_star_euclidean", "a_star_manhattan",
            "a_star_floor_aware", "bidirectional_bfs", "bidirectional_dijkstra",
        ]}
        aggregate_nodes = {k: [] for k in aggregate_distances}
        aggregate_times = {k: [] for k in aggregate_distances}

        for scenario in scenarios:
            comparison = self.compare_algorithms(
                scenario["start"], scenario["goal"]
            )
            scenario_results.append({
                "label": scenario.get("label", ""),
                "start": scenario["start"],
                "goal": scenario["goal"],
                "comparison": comparison,
            })

            for algo_name, result in comparison["results"].items():
                if "error" not in result and result["path"]:
                    aggregate_distances[algo_name].append(
                        result["total_distance"]
                    )
                    aggregate_nodes[algo_name].append(
                        result["nodes_visited"]
                    )
                    aggregate_times[algo_name].append(
                        result["execution_time_ms"]
                    )

        # Compute aggregates
        def _avg(lst: List[float]) -> float:
            return round(sum(lst) / len(lst), 2) if lst else 0.0

        aggregate = {
            "avg_distance_m": {
                k: _avg(v) for k, v in aggregate_distances.items()
            },
            "avg_nodes_visited": {
                k: _avg(v) for k, v in aggregate_nodes.items()
            },
            "avg_time_ms": {
                k: _avg(v) for k, v in aggregate_times.items()
            },
        }

        # Optimality rate: % of scenarios where algorithm matches Dijkstra
        dijkstra_dists = aggregate_distances["dijkstra"]
        optimality = {}
        for algo_name in aggregate_distances:
            if algo_name == "dijkstra":
                continue
            correct = sum(
                1 for i, d in enumerate(aggregate_distances[algo_name])
                if i < len(dijkstra_dists) and abs(d - dijkstra_dists[i]) < 1e-6
            )
            total = len(aggregate_distances[algo_name])
            optimality[algo_name] = round(correct / total, 3) if total > 0 else 0.0
        aggregate["optimality_rate_vs_dijkstra"] = optimality

        return {
            "scenarios": scenario_results,
            "aggregate": aggregate,
        }

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def get_floor_layout(self, floor: int) -> dict:
        """Return floor data for Canvas rendering.

        Returns:
            {"floor": int, "name": str, "nodes": [...], "edges": [...]}
        """
        floor_nodes = [
            node.to_dict()
            for nid, node in self.graph.vertices.items()
            if node.floor == floor
        ]
        # Collect edges where both endpoints are on this floor
        floor_nids = {n["node_id"] for n in floor_nodes}
        floor_edges: List[List] = []
        for from_id, neighbors in self.graph.adjacency.items():
            if from_id in floor_nids:
                for to_id, weight in neighbors:
                    if to_id in floor_nids:
                        floor_edges.append([from_id, to_id, weight])
        return {
            "floor": floor,
            "name": f"第{floor}层",
            "nodes": floor_nodes,
            "edges": floor_edges,
        }

    def get_all_node_labels(self) -> List[Dict[str, str]]:
        """Return all nodes for dropdown selectors."""
        return [
            {
                "node_id": nid,
                "name": node.name,
                "floor": node.floor,
                "type": node.node_type.value,
            }
            for nid, node in self.graph.vertices.items()
        ]

    def get_building_info(self) -> dict:
        """Return building metadata."""
        return {
            "name": self.name,
            "floors": self.floors,
            "total_vertices": self.graph.total_vertices,
            "total_edges": self.graph.total_edges,
        }

    def get_random_node_pair(
        self, same_floor: bool = True
    ) -> Tuple[str, str]:
        """Return a random (start, goal) node pair.

        Useful for quick testing and demo scenarios.

        Args:
            same_floor: If True, both nodes are on the same floor.
        """
        import random
        if same_floor:
            floor = random.choice(self.floors)
            candidates = self.graph.get_nodes_by_floor(floor)
        else:
            candidates = self.graph.get_all_nodes()

        if len(candidates) < 2:
            # Fallback: use any two nodes
            candidates = self.graph.get_all_nodes()

        start, goal = random.sample(candidates, 2)
        return start, goal

    def validate(self) -> List[str]:
        """Validate graph integrity.

        Returns a list of warning/error messages. Empty list = valid.
        """
        issues = []

        # Check no isolated nodes (at least one incident edge)
        for nid in self.graph:
            neighbors = self.graph.get_neighbors(nid)
            has_incoming = any(
                nid in (to for to, _ in self.graph.get_neighbors(other))
                for other in self.graph
                if other != nid
            )
            if not neighbors and not has_incoming:
                issues.append(f"Isolated node: {nid}")

        # Check all edge endpoints exist
        for from_id, neighbors in self.graph.adjacency.items():
            for to_id, _ in neighbors:
                if not self.graph.has_node(to_id):
                    issues.append(
                        f"Edge {from_id}→{to_id}: target not found"
                    )

        # Check vertical connectors exist on all floors
        for floor in self.floors:
            floor_nodes = self.graph.get_nodes_by_floor(floor)
            if len(floor_nodes) < 3:
                issues.append(
                    f"Floor {floor} has only {len(floor_nodes)} node(s)"
                )

        return issues

    def __repr__(self) -> str:
        return (f"Building(name={self.name!r}, floors={self.floors}, "
                f"vertices={self.graph.total_vertices}, "
                f"edges={self.graph.total_edges})")
