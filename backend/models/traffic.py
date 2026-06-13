"""Traffic state and event models for real-time navigation."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple


class CongestionLevel(Enum):
    """Traffic congestion severity levels."""
    NORMAL = "normal"       # green — free flowing
    MODERATE = "moderate"   # yellow — some slowdown
    HEAVY = "heavy"         # orange — significant delay
    BLOCKED = "blocked"     # red — impassable

    def __str__(self) -> str:
        labels = {"normal": "畅通", "moderate": "缓行", "heavy": "拥堵", "blocked": "阻塞"}
        return labels.get(self.value, self.value)

    @property
    def factor(self) -> float:
        """Weight multiplier applied to edge weight."""
        return {CongestionLevel.NORMAL: 1.0, CongestionLevel.MODERATE: 1.5,
                CongestionLevel.HEAVY: 3.0, CongestionLevel.BLOCKED: float("inf")}[self]


@dataclass
class BlockageEvent:
    """A traffic blockage or fault on a specific edge."""
    edge_key: Tuple[str, str]   # (from_id, to_id)
    description: str
    timestamp: float = 0.0

    def __repr__(self) -> str:
        return f"Blockage({self.edge_key[0]}→{self.edge_key[1]}: {self.description})"


@dataclass
class TrafficState:
    """Current traffic conditions on a map.

    Tracks congestion factors per edge and active blockage events.
    """
    congestion: Dict[Tuple[str, str], CongestionLevel] = field(default_factory=dict)
    blockages: List[BlockageEvent] = field(default_factory=list)

    def get_level(self, from_id: str, to_id: str) -> CongestionLevel:
        """Get congestion level for an edge (defaults to NORMAL)."""
        return self.congestion.get((from_id, to_id), CongestionLevel.NORMAL)

    def set_level(self, from_id: str, to_id: str, level: CongestionLevel):
        """Set congestion level for an edge."""
        self.congestion[(from_id, to_id)] = level

    def is_blocked(self, from_id: str, to_id: str) -> bool:
        """Check if an edge is blocked."""
        return self.get_level(from_id, to_id) == CongestionLevel.BLOCKED

    def add_blockage(self, from_id: str, to_id: str, description: str = ""):
        """Add a blockage event and mark the edge as blocked."""
        import time
        self.set_level(from_id, to_id, CongestionLevel.BLOCKED)
        self.blockages.append(BlockageEvent(
            edge_key=(from_id, to_id),
            description=description,
            timestamp=time.time(),
        ))

    def clear_blockage(self, from_id: str, to_id: str):
        """Remove a blockage and reset to normal."""
        self.set_level(from_id, to_id, CongestionLevel.NORMAL)
        self.blockages = [b for b in self.blockages if b.edge_key != (from_id, to_id)]

    def clear_all(self):
        """Reset all traffic conditions."""
        self.congestion.clear()
        self.blockages.clear()

    def to_dict(self) -> dict:
        return {
            "congestion": {f"{k[0]}->{k[1]}": v.value for k, v in self.congestion.items()},
            "blockages": [{"edge": f"{b.edge_key[0]}->{b.edge_key[1]}",
                           "description": b.description} for b in self.blockages],
        }
