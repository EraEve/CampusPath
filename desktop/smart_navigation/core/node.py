"""Extended navigation node with POI category and scene awareness.

Based on CampusPath's Node but extended for outdoor/geographic maps
with POI categories, scene IDs, and larger coordinate space.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class NavNodeType(Enum):
    """Extended node type classification for multi-scene navigation."""
    ROOM = "room"
    CORRIDOR = "corridor"
    STAIR = "stair"
    ELEVATOR = "elevator"
    ENTRANCE = "entrance"
    POI = "poi"
    INTERSECTION = "intersection"   # Road crossing
    BUS_STOP = "bus_stop"
    SUBWAY_STATION = "subway_station"
    TRAIN_STATION = "train_station"
    PARKING = "parking"
    HOSPITAL = "hospital"
    RESTAURANT = "restaurant"
    SCENIC_SPOT = "scenic_spot"

    def __str__(self) -> str:
        labels = {
            "room": "房间", "corridor": "走廊", "stair": "楼梯",
            "elevator": "电梯", "entrance": "入口", "poi": "兴趣点",
            "intersection": "路口", "bus_stop": "公交站",
            "subway_station": "地铁站", "train_station": "火车站",
            "parking": "停车场", "hospital": "医院", "restaurant": "餐厅",
            "scenic_spot": "景点",
        }
        return labels.get(self.value, self.value)


@dataclass
class NavNode:
    """A vertex in the navigation graph.

    Extends the CampusPath Node with:
    - scene_id for multi-map support
    - poi_category for nearby search
    - Larger coordinate range (0-1000) for outdoor maps

    Attributes:
        node_id: Unique identifier within the scene, e.g. "N001".
        name: Human-readable label, e.g. "Main Gate".
        node_type: Classification for rendering and routing logic.
        floor: Floor number (0=ground, negative=underground).
        x, y: Normalized coordinates in [0, 1000].
        scene_id: Which map this node belongs to.
        poi_category: For POI nodes — enables nearby search filtering.
        metadata: Optional extra fields.
    """
    node_id: str
    name: str
    node_type: NavNodeType = NavNodeType.INTERSECTION
    floor: int = 0
    x: float = 0.0
    y: float = 0.0
    scene_id: str = ""
    poi_category: Optional[Any] = None   # POICategory enum
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dictionary."""
        from ..models.transport import POICategory
        result = {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type.value,
            "floor": self.floor,
            "x": self.x,
            "y": self.y,
            "scene_id": self.scene_id,
            "poi_category": self.poi_category.value if isinstance(self.poi_category, POICategory) else self.poi_category,
            "metadata": self.metadata,
        }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NavNode":
        """Deserialize from dictionary."""
        from ..models.transport import POICategory
        poi_cat = data.get("poi_category")
        if isinstance(poi_cat, str) and poi_cat:
            try:
                poi_cat = POICategory(poi_cat)
            except ValueError:
                poi_cat = None
        return cls(
            node_id=data["node_id"],
            name=data["name"],
            node_type=NavNodeType(data.get("node_type", "intersection")),
            floor=data.get("floor", 0),
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            scene_id=data.get("scene_id", ""),
            poi_category=poi_cat,
            metadata=data.get("metadata", {}),
        )

    def __repr__(self) -> str:
        return (f"NavNode(id={self.node_id!r}, name={self.name!r}, "
                f"type={self.node_type.value}, floor={self.floor})")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, NavNode):
            return NotImplemented
        return self.node_id == other.node_id

    def __hash__(self) -> int:
        return hash(self.node_id)
