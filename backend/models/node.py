"""Node data structure for indoor navigation graph.

Represents a single vertex in the campus building graph. Each node
corresponds to a physical location: classroom, corridor segment,
stairwell, elevator, entrance, or point of interest.

Supports the AdjacencyListGraph and all pathfinding algorithms.
"""

from enum import Enum
from typing import Any, Dict


class NodeType(Enum):
    """Classification of indoor navigation nodes.

    Used by the Canvas renderer to select appropriate icons/colors,
    and by the Floor-Aware heuristic to apply vertical penalties.
    """

    ROOM = "room"           # Classroom, office, laboratory
    CORRIDOR = "corridor"   # Hallway segment (corridors are segmented)
    STAIR = "stair"         # Stairwell node on a specific floor
    ELEVATOR = "elevator"   # Elevator node on a specific floor
    ENTRANCE = "entrance"   # Building entry/exit point
    POI = "poi"             # Point of interest: canteen, shop, restroom


class Node:
    """A vertex in the indoor navigation graph.

    Each node represents a discrete location within a building floor.
    Coordinates (x, y) use a normalized 0-100 coordinate system for
    resolution-independent Canvas rendering.

    Attributes:
        node_id: Unique identifier, e.g. "F2-R201" or "F1-STAIR-A".
        name: Human-readable label, e.g. "Room 201 - Computer Lab".
        node_type: Classification determining rendering and heuristics.
        floor: Building floor number (1-indexed).
        x: Normalized X coordinate in [0, 100].
        y: Normalized Y coordinate in [0, 100].
        metadata: Optional extra fields (capacity, department, etc.).
    """

    __slots__ = ("node_id", "name", "node_type", "floor",
                 "x", "y", "metadata")

    def __init__(
        self,
        node_id: str,
        name: str,
        node_type: NodeType,
        floor: int,
        x: float = 0.0,
        y: float = 0.0,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        self.node_id = node_id
        self.name = name
        self.node_type = node_type
        self.floor = floor
        self.x = x
        self.y = y
        self.metadata = metadata if metadata is not None else {}

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type.value,
            "floor": self.floor,
            "x": self.x,
            "y": self.y,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        """Deserialize from dictionary."""
        return cls(
            node_id=data["node_id"],
            name=data["name"],
            node_type=NodeType(data["node_type"]),
            floor=data["floor"],
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            metadata=data.get("metadata", {}),
        )

    # ------------------------------------------------------------------
    # Magic methods
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (f"Node(id={self.node_id!r}, name={self.name!r}, "
                f"type={self.node_type.value}, floor={self.floor})")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Node):
            return NotImplemented
        return self.node_id == other.node_id

    def __hash__(self) -> int:
        return hash(self.node_id)
