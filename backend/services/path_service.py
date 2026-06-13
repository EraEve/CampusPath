"""Path Planning Service — orchestrates pathfinding across algorithms.

Responsibilities:
- Validate inputs (start, end, waypoints)
- Dispatch to the correct algorithm with the right parameters
- Handle multi-segment paths (with waypoints)
- Compute time and cost estimates on found paths
- Maintain search history
"""

from typing import Any, Dict, List, Optional

from backend.core.nav_graph import NavGraph
from backend.models.transport import TransportMode
from backend.models.path_result import PathResult
from backend.algorithms.extended_dijkstra import dijkstra
from backend.algorithms.extended_a_star import a_star
from backend.algorithms.extended_bfs import bfs_shortest_path
from backend.algorithms.extended_bidirectional import bidirectional_dijkstra, bidirectional_bfs
from backend.algorithms.congestion_avoidance import congestion_avoidance_dijkstra
from backend.algorithms.multi_criteria import multi_criteria_dijkstra

INF = float("inf")


class PathService:
    """High-level pathfinding orchestration.

    Usage:
        svc = PathService()
        result = svc.find_path(graph, "N001", "N025", mode=TransportMode.DRIVING)
    """

    def __init__(self):
        self.history: List[PathResult] = []
        self.max_history = 20

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def find_path(
        self,
        graph: NavGraph,
        start_id: str,
        goal_id: str,
        transport_mode: TransportMode = TransportMode.WALKING,
        algorithm: str = "dijkstra",
        heuristic: str = "euclidean",
        waypoints: Optional[List[str]] = None,
        highway_priority: bool = False,
        congestion_avoidance: bool = False,
        congestion_threshold: float = 1.5,
        multi_criteria: bool = False,
        w_distance: float = 0.4,
        w_time: float = 0.4,
        w_cost: float = 0.2,
        blocked_edges: Optional[set] = None,
    ) -> PathResult:
        """Find the optimal path between two nodes.

        If waypoints are provided, the path is split into segments:
        start → waypoint[0] → waypoint[1] → ... → goal.

        Args:
            graph: The navigation graph.
            start_id: Starting node ID.
            goal_id: Target node ID.
            transport_mode: Mode of transport.
            algorithm: "dijkstra", "a_star", "bfs", "bidirectional_dijkstra",
                      "bidirectional_bfs", "congestion_avoidance", "multi_criteria".
            heuristic: For A*: "euclidean", "manhattan", "floor_aware".
            waypoints: Optional intermediate nodes to visit in order.
            highway_priority: Prefer highways (reduces highway edge weights).
            congestion_avoidance: Penalize congested edges.
            congestion_threshold: Factor threshold for congestion avoidance.
            multi_criteria: Use weighted multi-criteria optimization.
            w_distance, w_time, w_cost: Weights for multi-criteria.
            blocked_edges: Set of (from, to) tuples that are blocked.

        Returns:
            PathResult with path, distances, times, costs.
        """
        # Validate
        if not graph.has_node(start_id):
            raise ValueError(f"Start node '{start_id}' not found.")
        if not graph.has_node(goal_id):
            raise ValueError(f"Goal node '{goal_id}' not found.")

        # Waypoint-based multi-segment routing
        if waypoints and len(waypoints) > 0:
            return self._find_path_with_waypoints(
                graph, start_id, goal_id, waypoints, transport_mode,
                algorithm, heuristic, highway_priority,
                congestion_avoidance, congestion_threshold,
                multi_criteria, w_distance, w_time, w_cost, blocked_edges,
            )

        # Single-segment routing
        return self._find_single_path(
            graph, start_id, goal_id, transport_mode,
            algorithm, heuristic, highway_priority,
            congestion_avoidance, congestion_threshold,
            multi_criteria, w_distance, w_time, w_cost, blocked_edges,
        )

    def _find_single_path(
        self, graph, start_id, goal_id, transport_mode,
        algorithm, heuristic, highway_priority,
        congestion_avoidance, congestion_threshold,
        multi_criteria, w_distance, w_time, w_cost, blocked_edges,
    ) -> PathResult:
        """Execute a single-segment pathfinding query."""
        if algorithm == "multi_criteria" or multi_criteria:
            raw = multi_criteria_dijkstra(
                graph, start_id, goal_id, transport_mode,
                w_distance, w_time, w_cost, blocked_edges,
            )
            result = PathResult(
                path=raw["path"],
                total_distance=raw["total_distance"],
                total_time=raw["total_time"],
                total_cost=raw["total_cost"],
                nodes_visited=raw["nodes_visited"],
                execution_time_ms=raw["execution_time_ms"],
                algorithm="multi_criteria",
                transport_mode=transport_mode,
                criteria=["distance", "time", "cost"],
            )
        elif algorithm == "congestion_avoidance" or congestion_avoidance:
            raw = congestion_avoidance_dijkstra(
                graph, start_id, goal_id, transport_mode,
                congestion_threshold, highway_priority, blocked_edges,
            )
            result = PathResult(
                path=raw["path"],
                total_distance=raw["total_distance"],
                nodes_visited=raw["nodes_visited"],
                execution_time_ms=raw["execution_time_ms"],
                algorithm="congestion_avoidance",
                transport_mode=transport_mode,
                congestion_avoided=True,
                blocked_edges_avoided=raw.get("congested_edges_avoided", []),
            )
        elif algorithm == "a_star":
            raw = a_star(
                graph, start_id, goal_id, heuristic, transport_mode,
                False, highway_priority, blocked_edges,
            )
            result = PathResult(
                path=raw["path"],
                total_distance=raw["total_distance"],
                nodes_visited=raw["nodes_visited"],
                execution_time_ms=raw["execution_time_ms"],
                algorithm=f"a_star_{heuristic}",
                transport_mode=transport_mode,
                heuristic=heuristic,
            )
        elif algorithm == "bfs":
            raw = bfs_shortest_path(
                graph, start_id, goal_id, transport_mode, False, blocked_edges,
            )
            result = PathResult(
                path=raw["path"],
                total_distance=raw["total_distance"],
                nodes_visited=raw["nodes_visited"],
                execution_time_ms=raw["execution_time_ms"],
                algorithm="bfs",
                transport_mode=transport_mode,
            )
        elif algorithm == "bidirectional_dijkstra":
            raw = bidirectional_dijkstra(
                graph, start_id, goal_id, transport_mode, False,
            )
            result = PathResult(
                path=raw["path"],
                total_distance=raw["total_distance"],
                nodes_visited=raw["nodes_visited"],
                execution_time_ms=raw["execution_time_ms"],
                algorithm="bidirectional_dijkstra",
                transport_mode=transport_mode,
            )
        elif algorithm == "bidirectional_bfs":
            raw = bidirectional_bfs(
                graph, start_id, goal_id, transport_mode, False,
            )
            result = PathResult(
                path=raw["path"],
                total_distance=raw["total_distance"],
                nodes_visited=raw["nodes_visited"],
                execution_time_ms=raw["execution_time_ms"],
                algorithm="bidirectional_bfs",
                transport_mode=transport_mode,
            )
        else:  # default: dijkstra
            raw = dijkstra(
                graph, start_id, goal_id, transport_mode,
                False, congestion_threshold, highway_priority, blocked_edges,
            )
            result = PathResult(
                path=raw["path"],
                total_distance=raw["total_distance"],
                nodes_visited=raw["nodes_visited"],
                execution_time_ms=raw["execution_time_ms"],
                algorithm="dijkstra",
                transport_mode=transport_mode,
            )

        # Compute time and cost estimates for non-multi-criteria results
        if result.total_time == 0.0 and result.is_reachable:
            result.total_time = self._estimate_time(graph, result.path, transport_mode)
        if result.total_cost == 0.0 and result.is_reachable:
            result.total_cost = self._estimate_cost(graph, result.path)

        self._add_to_history(result)
        return result

    def _find_path_with_waypoints(
        self, graph, start_id, goal_id, waypoints,
        transport_mode, algorithm, heuristic, highway_priority,
        congestion_avoidance, congestion_threshold,
        multi_criteria, w_distance, w_time, w_cost, blocked_edges,
    ) -> PathResult:
        """Route through multiple waypoints by chaining single-segment queries."""
        all_path = []
        total_dist = 0.0
        total_time = 0.0
        total_cost = 0.0
        total_visited = 0
        total_ms = 0.0

        segments = [start_id] + list(waypoints) + [goal_id]
        for i in range(len(segments) - 1):
            seg_result = self._find_single_path(
                graph, segments[i], segments[i + 1], transport_mode,
                algorithm, heuristic, highway_priority,
                congestion_avoidance, congestion_threshold,
                multi_criteria, w_distance, w_time, w_cost, blocked_edges,
            )
            if not seg_result.is_reachable:
                return PathResult(algorithm=f"{algorithm}_waypoints")

            if all_path:
                all_path.extend(seg_result.path[1:])  # skip duplicate junction
            else:
                all_path.extend(seg_result.path)

            total_dist += seg_result.total_distance
            total_time += seg_result.total_time
            total_cost += seg_result.total_cost
            total_visited += seg_result.nodes_visited
            total_ms += seg_result.execution_time_ms

        result = PathResult(
            path=all_path,
            total_distance=total_dist,
            total_time=total_time,
            total_cost=total_cost,
            nodes_visited=total_visited,
            execution_time_ms=total_ms,
            algorithm=f"{algorithm}_waypoints",
            transport_mode=transport_mode,
            waypoints=waypoints,
        )
        self._add_to_history(result)
        return result

    # ------------------------------------------------------------------
    # Estimation helpers
    # ------------------------------------------------------------------

    def _estimate_time(self, graph: NavGraph, path: List[str],
                       mode: TransportMode) -> float:
        """Estimate travel time in seconds along a path."""
        total_seconds = 0.0
        default_speeds = {
            TransportMode.WALKING: 5.0,
            TransportMode.DRIVING: 40.0,
            TransportMode.BUS: 30.0,
            TransportMode.SUBWAY: 55.0,
            TransportMode.TRAIN: 80.0,
        }
        default_ms = (default_speeds.get(mode, 5.0) / 3.6)  # km/h → m/s

        for i in range(len(path) - 1):
            edge = graph.get_edge(path[i], path[i + 1])
            if edge:
                dist = edge.weight
                speed = edge.speed_limit if edge.speed_limit > 0 else default_ms * 3.6
                speed_ms = speed / 3.6
                total_seconds += dist / speed_ms if speed_ms > 0 else dist / 1.4
        return total_seconds

    def _estimate_cost(self, graph: NavGraph, path: List[str]) -> float:
        """Estimate monetary cost along a path."""
        total_cost = 0.0
        for i in range(len(path) - 1):
            edge = graph.get_edge(path[i], path[i + 1])
            if edge:
                km = edge.weight / 1000.0
                if edge.road_type.value == "highway":
                    total_cost += km * 1.0
                elif edge.road_type.value == "main_road":
                    total_cost += km * 0.2
        return round(total_cost, 2)

    # ------------------------------------------------------------------
    # History management
    # ------------------------------------------------------------------

    def _add_to_history(self, result: PathResult):
        """Add a result to search history, maintaining max size."""
        self.history.insert(0, result)
        if len(self.history) > self.max_history:
            self.history = self.history[:self.max_history]

    def get_history(self) -> List[PathResult]:
        """Return all saved path history entries."""
        return self.history

    def clear_history(self):
        """Clear all path history."""
        self.history.clear()

    # ------------------------------------------------------------------
    # Path comparison
    # ------------------------------------------------------------------

    def compare_algorithms(
        self,
        graph: NavGraph,
        start_id: str,
        goal_id: str,
        transport_mode: TransportMode = TransportMode.WALKING,
    ) -> List[PathResult]:
        """Run all applicable algorithms and return comparison results."""
        algorithms = [
            ("dijkstra", {}),
            ("a_star", {"heuristic": "euclidean"}),
            ("a_star", {"heuristic": "manhattan"}),
            ("bfs", {}),
            ("bidirectional_dijkstra", {}),
            ("bidirectional_bfs", {}),
            ("congestion_avoidance", {}),
            ("multi_criteria", {}),
        ]

        results = []
        for algo, opts in algorithms:
            try:
                if algo == "a_star":
                    result = self.find_path(
                        graph, start_id, goal_id, transport_mode,
                        algorithm=algo, heuristic=opts.get("heuristic", "euclidean"),
                    )
                else:
                    result = self.find_path(
                        graph, start_id, goal_id, transport_mode, algorithm=algo,
                    )
                results.append(result)
            except Exception as e:
                results.append(PathResult(algorithm=f"{algo}_error"))
        return results
