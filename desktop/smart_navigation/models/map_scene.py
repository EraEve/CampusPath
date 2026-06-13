"""SceneMap dataclass for map metadata."""

from dataclasses import dataclass, field
from typing import List, Optional

from .transport import SceneType, TransportMode


@dataclass
class SceneMap:
    """Metadata for a loaded map scene."""
    scene_id: str
    name: str
    scene_type: SceneType
    transport_modes: List[TransportMode] = field(default_factory=list)
    description: str = ""
    node_count: int = 0
    edge_count: int = 0
    bounds: dict = field(default_factory=lambda: {"min_x": 0, "min_y": 0, "max_x": 1000, "max_y": 600})
    file_path: Optional[str] = None

    def __repr__(self) -> str:
        return (f"SceneMap(id={self.scene_id}, name={self.name}, "
                f"type={self.scene_type}, nodes={self.node_count}, edges={self.edge_count})")
