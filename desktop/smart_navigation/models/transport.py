"""Transport mode, road type, POI category, and scene type enums.

These enums drive road-type-aware routing, POI search filtering,
and map scene selection throughout the entire system.
"""

from enum import Enum


class TransportMode(Enum):
    """Modes of transport for path planning."""
    DRIVING = "driving"
    WALKING = "walking"
    BUS = "bus"
    TRAIN = "train"
    SUBWAY = "subway"

    def __str__(self) -> str:
        labels = {
            "driving": "驾车",
            "walking": "步行",
            "bus": "公交",
            "train": "火车",
            "subway": "地铁",
        }
        return labels.get(self.value, self.value)


class RoadType(Enum):
    """Road classification for edge metadata and filtering.

    Each road type determines which transport modes can use it
    and affects routing decisions (highway priority, congestion, etc.).
    """
    PATH = "path"               # Footpath, sidewalk
    MAIN_ROAD = "main_road"     # Regular city road
    HIGHWAY = "highway"         # Expressway / freeway
    ONE_WAY_STREET = "one_way"  # One-direction street
    WALKING_PATH = "walking"    # Pedestrian-only path
    BUS_LANE = "bus_lane"       # Bus-only lane
    SUBWAY_TUNNEL = "subway"    # Underground subway tunnel
    TRAIN_TRACK = "train"       # Railway track

    def __str__(self) -> str:
        labels = {
            "path": "小路",
            "main_road": "大路",
            "highway": "高速",
            "one_way": "单行线",
            "walking": "步行道",
            "bus_lane": "公交道",
            "subway": "地铁隧道",
            "train": "铁路",
        }
        return labels.get(self.value, self.value)


class POICategory(Enum):
    """Point-of-interest categories for nearby search."""
    SCENIC_SPOT = "scenic"
    FOOD = "food"
    PARKING = "parking"
    HOSPITAL = "hospital"

    def __str__(self) -> str:
        labels = {
            "scenic": "景点",
            "food": "美食",
            "parking": "停车场",
            "hospital": "医院",
        }
        return labels.get(self.value, self.value)


class SceneType(Enum):
    """Map scene classification: indoor/outdoor × location type."""
    OUTDOOR_CAMPUS = "outdoor_campus"
    INDOOR_MALL = "indoor_mall"
    OUTDOOR_CITY = "outdoor_city"
    UNDERGROUND = "underground"

    def __str__(self) -> str:
        labels = {
            "outdoor_campus": "室外校园",
            "indoor_mall": "室内商场",
            "outdoor_city": "室外城市",
            "underground": "地下通道",
        }
        return labels.get(self.value, self.value)

    @property
    def is_outdoor(self) -> bool:
        """Return True if this is an outdoor scene."""
        return self in (SceneType.OUTDOOR_CAMPUS, SceneType.OUTDOOR_CITY)

    @property
    def is_indoor(self) -> bool:
        """Return True if this is an indoor scene."""
        return self in (SceneType.INDOOR_MALL,)
