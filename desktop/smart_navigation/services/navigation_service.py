"""Navigation Service — real-time navigation monitoring.

Tracks a vehicle's progress along a planned path, detects deviations,
triggers rerouting on blockages, and generates alerts.

This is the central coordinator for the real-time navigation feature.
"""

import time
from typing import Any, Callable, Dict, List, Optional

from ..core.graph import NavGraph
from ..models.transport import TransportMode
from ..models.path_result import PathResult
from ..models.vehicle import Vehicle
from ..algorithms.reroute import reroute_from_position, find_nearest_path_node
from .traffic_service import TrafficService


class NavigationService:
    """Real-time navigation monitor with deviation detection and rerouting.

    Usage:
        nav = NavigationService()
        nav.start_navigation(graph, planned_path, transport_mode)
        nav.update_position(current_node_id)  # called periodically
        if nav.has_deviation:
            nav.reroute()
    """

    def __init__(self):
        self._graph: Optional[NavGraph] = None
        self._planned_path: List[str] = []
        self._current_node: Optional[str] = None
        self._transport_mode: TransportMode = TransportMode.DRIVING
        self._goal_id: str = ""
        self._traffic_service: Optional[TrafficService] = None

        # State
        self.is_active: bool = False
        self.has_deviation: bool = False
        self.deviation_node: Optional[str] = None
        self.alerts: List[dict] = []
        self._on_alert: Optional[Callable] = None
        self._position_history: List[str] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_navigation(
        self,
        graph: NavGraph,
        planned_path: List[str],
        goal_id: str,
        transport_mode: TransportMode = TransportMode.DRIVING,
        traffic_service: Optional[TrafficService] = None,
        on_alert: Optional[Callable] = None,
    ):
        """Begin real-time navigation along a planned path.

        Args:
            graph: The navigation graph.
            planned_path: The path to follow (list of node IDs).
            goal_id: The destination node ID.
            transport_mode: Mode of transport.
            traffic_service: Optional traffic service for blockage awareness.
            on_alert: Optional callback(alert_dict) for alert notifications.
        """
        self._graph = graph
        self._planned_path = list(planned_path)
        self._goal_id = goal_id
        self._transport_mode = transport_mode
        self._traffic_service = traffic_service
        self._on_alert = on_alert
        self.is_active = True
        self.has_deviation = False
        self.deviation_node = None
        self.alerts = []
        self._position_history = []

        if planned_path:
            self._current_node = planned_path[0]

        self._add_alert("info", f"导航已开始，目的地: {goal_id}")

    def stop_navigation(self):
        """End navigation."""
        self.is_active = False
        self._add_alert("info", "导航已结束")

    # ------------------------------------------------------------------
    # Position tracking
    # ------------------------------------------------------------------

    def update_position(self, node_id: str) -> bool:
        """Report the current node position. Returns True if on-path."""
        if not self.is_active:
            return True

        self._current_node = node_id
        self._position_history.append(node_id)

        # Check if we've reached the goal
        if node_id == self._goal_id:
            self._add_alert("success", "已到达目的地！")
            self.is_active = False
            return True

        # Check for deviation
        on_path = node_id in self._planned_path
        if not on_path:
            self.has_deviation = True
            self.deviation_node = node_id
            self._add_alert("warning", f"偏离路线！当前位置: {node_id}")

        # Check for blockages ahead (if traffic service available)
        if self._traffic_service:
            self._check_blockages_ahead(node_id)

        return on_path

    def update_position_xy(self, x: float, y: float):
        """Update position by coordinates (finds nearest path node)."""
        if not self.is_active or not self._graph:
            return

        nearest = find_nearest_path_node(self._graph, self._planned_path, x, y)
        if nearest:
            self.update_position(nearest)

    # ------------------------------------------------------------------
    # Rerouting
    # ------------------------------------------------------------------

    def reroute(self) -> Optional[Dict[str, Any]]:
        """Reroute from current position to goal, avoiding known blockages.

        Returns:
            Reroute result dict with merged path, or None if rerouting fails.
        """
        if not self.is_active or not self._graph or not self._current_node:
            return None

        # Collect blocked edges from traffic service
        blocked_edges = set()
        if self._traffic_service:
            for blockage in self._traffic_service.get_blockages():
                blocked_edges.add(blockage.edge_key)

        result = reroute_from_position(
            self._graph,
            self._planned_path,
            self._current_node,
            self._goal_id,
            self._transport_mode,
            blocked_edges,
        )

        if result and result["path"]:
            self._planned_path = result["path"]
            self.has_deviation = False
            self.deviation_node = None
            self._add_alert(
                "info",
                f"已重新规划路线，避开 {len(blocked_edges)} 处阻塞"
            )
        else:
            self._add_alert("error", "重新规划路线失败！")

        return result

    # ------------------------------------------------------------------
    # Blockage checking
    # ------------------------------------------------------------------

    def _check_blockages_ahead(self, current_node_id: str):
        """Check if any edges ahead on the path are blocked."""
        if not self._traffic_service or current_node_id not in self._planned_path:
            return

        try:
            idx = self._planned_path.index(current_node_id)
            for i in range(idx, len(self._planned_path) - 1):
                f = self._planned_path[i]
                t = self._planned_path[i + 1]
                if self._traffic_service.is_blocked(f, t):
                    self._add_alert(
                        "danger",
                        f"前方道路阻塞: {f}→{t}",
                    )
                    break
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    def _add_alert(self, level: str, message: str):
        """Add an alert and notify callback."""
        alert = {
            "level": level,       # info, warning, danger, success, error
            "message": message,
            "timestamp": time.time(),
            "node": self._current_node,
        }
        self.alerts.append(alert)

        # Keep only last 50 alerts
        if len(self.alerts) > 50:
            self.alerts = self.alerts[-50:]

        if self._on_alert:
            self._on_alert(alert)

    def get_alerts(self, max_count: int = 20) -> List[dict]:
        """Return recent alerts, newest first."""
        return list(reversed(self.alerts[-max_count:]))

    def clear_alerts(self):
        """Clear all alerts."""
        self.alerts.clear()

    # ------------------------------------------------------------------
    # Progress info
    # ------------------------------------------------------------------

    def get_progress(self) -> dict:
        """Return current navigation progress."""
        if not self._planned_path or not self._current_node:
            return {"pct": 0.0, "remaining_nodes": 0, "next_node": None}

        total = len(self._planned_path)
        try:
            idx = self._planned_path.index(self._current_node)
            pct = (idx / (total - 1)) * 100.0 if total > 1 else 100.0
        except ValueError:
            pct = 0.0
            idx = 0

        next_node = None
        if idx + 1 < total:
            next_id = self._planned_path[idx + 1]
            if self._graph:
                node = self._graph.get_node(next_id)
                next_node = node.name if node else next_id
            else:
                next_node = next_id

        return {
            "pct": round(pct, 1),
            "current_node": self._current_node,
            "remaining_nodes": total - idx - 1,
            "next_node": next_node,
            "goal_id": self._goal_id,
        }
