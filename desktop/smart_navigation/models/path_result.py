"""Standardized pathfinding result dataclass.

Extends the CampusPath result dict format into a proper dataclass
with additional fields for multi-modal, multi-criteria, and real-time
navigation support.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .transport import TransportMode


@dataclass
class PathResult:
    """Result of a single pathfinding query.

    All algorithms return this standardized format for fair comparison
    and consistent consumption by the GUI and services.
    """
    path: List[str] = field(default_factory=list)
    total_distance: float = 0.0           # meters
    total_time: float = 0.0               # seconds (based on speed limits)
    total_cost: float = 0.0               # arbitrary cost units
    nodes_visited: int = 0
    execution_time_ms: float = 0.0
    steps: List[Dict[str, Any]] = field(default_factory=list)
    algorithm: str = ""
    transport_mode: Optional[TransportMode] = None
    criteria: List[str] = field(default_factory=list)
    waypoints: List[str] = field(default_factory=list)
    blocked_edges_avoided: List[str] = field(default_factory=list)
    congestion_avoided: bool = False
    heuristic: Optional[str] = None

    @property
    def path_length(self) -> int:
        """Number of nodes in the path."""
        return len(self.path)

    @property
    def is_reachable(self) -> bool:
        """Return True if a valid path was found."""
        return len(self.path) > 0 and self.total_distance < float("inf")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "path": self.path,
            "total_distance": self.total_distance,
            "total_time": self.total_time,
            "total_cost": self.total_cost,
            "nodes_visited": self.nodes_visited,
            "execution_time_ms": self.execution_time_ms,
            "algorithm": self.algorithm,
            "transport_mode": self.transport_mode.value if self.transport_mode else None,
            "criteria": self.criteria,
            "waypoints": self.waypoints,
            "blocked_edges_avoided": self.blocked_edges_avoided,
            "congestion_avoided": self.congestion_avoided,
            "heuristic": self.heuristic,
        }

    def __repr__(self) -> str:
        return (
            f"PathResult(algo={self.algorithm}, mode={self.transport_mode}, "
            f"nodes={self.path_length}, dist={self.total_distance:.1f}m, "
            f"time={self.total_time:.1f}s, cost={self.total_cost:.1f})"
        )
