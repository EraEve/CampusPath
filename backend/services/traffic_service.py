"""Traffic Service — manages traffic state on a navigation graph.

Provides query and update APIs for congestion levels and blockages.
Works with TrafficSimulator for real-time updates.
"""

from typing import Dict, List, Optional, Tuple

from backend.core.nav_graph import NavGraph
from backend.models.traffic import TrafficState, CongestionLevel, BlockageEvent


class TrafficService:
    """Manages traffic conditions on a navigation graph.

    Usage:
        svc = TrafficService()
        svc.set_graph(graph)
        svc.set_congestion("N001", "N002", CongestionLevel.HEAVY)
    """

    def __init__(self):
        self._graph: Optional[NavGraph] = None
        self._state = TrafficState()

    def set_graph(self, graph: NavGraph):
        """Set the active graph and reset traffic state."""
        self._graph = graph
        self._state.clear_all()

    # ------------------------------------------------------------------
    # Congestion
    # ------------------------------------------------------------------

    def set_congestion(self, from_id: str, to_id: str,
                       level: CongestionLevel):
        """Set congestion level on an edge."""
        self._state.set_level(from_id, to_id, level)
        if self._graph:
            edge = self._graph.get_edge(from_id, to_id)
            if edge:
                edge.congestion_factor = level.factor

    def get_congestion(self, from_id: str, to_id: str) -> CongestionLevel:
        """Get congestion level for an edge."""
        return self._state.get_level(from_id, to_id)

    def get_all_congested(self) -> List[dict]:
        """Return all edges with non-normal congestion."""
        result = []
        for (f, t), level in self._state.congestion.items():
            if level != CongestionLevel.NORMAL:
                edge_name = ""
                if self._graph:
                    e = self._graph.get_edge(f, t)
                    if e:
                        edge_name = e.name or f"{f}→{t}"
                result.append({
                    "from": f, "to": t, "level": level.value,
                    "label": str(level), "name": edge_name,
                })
        return result

    def clear_congestion(self, from_id: str, to_id: str):
        """Reset an edge to normal."""
        self._state.set_level(from_id, to_id, CongestionLevel.NORMAL)
        if self._graph:
            edge = self._graph.get_edge(from_id, to_id)
            if edge:
                edge.congestion_factor = 1.0

    # ------------------------------------------------------------------
    # Blockage
    # ------------------------------------------------------------------

    def block_edge(self, from_id: str, to_id: str,
                   description: str = ""):
        """Block an edge (impassable)."""
        self._state.add_blockage(from_id, to_id, description)
        if self._graph:
            self._graph.block_edge(from_id, to_id)

    def unblock_edge(self, from_id: str, to_id: str):
        """Remove a blockage."""
        self._state.clear_blockage(from_id, to_id)
        if self._graph:
            self._graph.unblock_edge(from_id, to_id)

    def get_blockages(self) -> List[BlockageEvent]:
        """Return all active blockages."""
        return self._state.blockages

    def is_blocked(self, from_id: str, to_id: str) -> bool:
        """Check if an edge is blocked."""
        return self._state.is_blocked(from_id, to_id)

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def clear_all(self):
        """Reset all traffic conditions."""
        self._state.clear_all()
        if self._graph:
            self._graph.reset_traffic()

    def get_traffic_summary(self) -> dict:
        """Return a summary of current traffic conditions."""
        congested = self.get_all_congested()
        blocked = len(self._state.blockages)
        return {
            "congested_edges": len(congested),
            "blocked_edges": blocked,
            "congested_details": congested,
            "blockages": [{"edge": f"{b.edge_key[0]}→{b.edge_key[1]}",
                          "desc": b.description} for b in self._state.blockages],
        }

    def get_state(self) -> TrafficState:
        """Return the raw traffic state."""
        return self._state
