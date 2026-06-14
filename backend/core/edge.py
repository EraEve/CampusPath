"""Road-type-aware Edge dataclass.

The critical extension over CampusPath's simple (neighbor_id, weight) tuple.
Each edge carries road type, transport mode, speed limit, and congestion
metadata — enabling mode-aware routing, highway priority, and real-time
traffic response.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

from backend.models.transport import RoadType, TransportMode


def _safe_road_type(value):
    """Parse RoadType safely, falling back to PATH on ValueError."""
    try:
        return RoadType(value)
    except (ValueError, TypeError):
        return RoadType.PATH


# Default allowed modes per road type
DEFAULT_ALLOWED_MODES: Dict[RoadType, Set[TransportMode]] = {
    RoadType.PATH: {TransportMode.WALKING},
    RoadType.MAIN_ROAD: {TransportMode.DRIVING, TransportMode.WALKING, TransportMode.BUS},
    RoadType.HIGHWAY: {TransportMode.DRIVING, TransportMode.BUS},
    RoadType.ONE_WAY_STREET: {TransportMode.DRIVING, TransportMode.BUS},
    RoadType.WALKING_PATH: {TransportMode.WALKING},
    RoadType.BUS_LANE: {TransportMode.BUS},
    RoadType.SUBWAY_TUNNEL: {TransportMode.SUBWAY},
    RoadType.TRAIN_TRACK: {TransportMode.TRAIN},
}


@dataclass
class Edge:
    """A directed edge in the navigation graph with full road-type metadata.

    Attributes:
        from_id: Source node ID.
        to_id: Destination node ID.
        weight: Base distance in meters.
        road_type: Road classification (PATH, HIGHWAY, etc.).
        one_way: If True, this is a directed edge only (no reverse).
        allowed_modes: Set of transport modes permitted on this edge.
        speed_limit: Speed limit in km/h (0 = no limit / walking pace).
        congestion_factor: Multiplier on weight (1.0 = normal, >1.0 = congested).
        is_blocked: If True, edge is impassable.
        name: Optional human-readable road/edge name.
        metadata: Optional extra fields.
    """
    from_id: str
    to_id: str
    weight: float = 0.0
    road_type: RoadType = RoadType.PATH
    one_way: bool = False
    allowed_modes: Set[TransportMode] = field(default_factory=set)
    speed_limit: float = 0.0       # km/h
    congestion_factor: float = 1.0
    is_blocked: bool = False
    name: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Auto-populate allowed_modes from road_type if not explicitly set."""
        if not self.allowed_modes:
            self.allowed_modes = DEFAULT_ALLOWED_MODES.get(
                self.road_type, {TransportMode.WALKING}
            ).copy()

    @property
    def effective_weight(self) -> float:
        """Weight adjusted for congestion and blockage."""
        if self.is_blocked:
            return float("inf")
        return self.weight * self.congestion_factor

    def allows_mode(self, mode: TransportMode) -> bool:
        """Check if this edge can be traversed with the given transport mode."""
        return mode in self.allowed_modes

    @property
    def edge_key(self) -> tuple:
        """Return (from_id, to_id) tuple for dictionary lookups."""
        return (self.from_id, self.to_id)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return {
            "from": self.from_id,
            "to": self.to_id,
            "weight": self.weight,
            "road_type": self.road_type.value,
            "one_way": self.one_way,
            "allowed_modes": [m.value for m in self.allowed_modes],
            "speed_limit": self.speed_limit,
            "name": self.name,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Edge":
        """Deserialize from dictionary."""
        allowed_modes = set()
        for m_str in data.get("allowed_modes", []):
            try:
                allowed_modes.add(TransportMode(m_str))
            except ValueError:
                pass
        return cls(
            from_id=data["from"],
            to_id=data["to"],
            weight=data.get("weight", 0.0),
            road_type=_safe_road_type(data.get("road_type", "path")),
            one_way=data.get("one_way", False),
            allowed_modes=allowed_modes,
            speed_limit=data.get("speed_limit", 0.0),
            name=data.get("name", ""),
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        arrow = "→" if not self.one_way else "⇒"
        return (f"Edge({self.from_id}{arrow}{self.to_id}, "
                f"w={self.weight:.0f}, {self.road_type.value})")

    def __hash__(self) -> int:
        return hash((self.from_id, self.to_id))
