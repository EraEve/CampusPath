"""Vehicle model for vehicle monitoring feature."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class VehicleStatus(Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    DELAYED = "delayed"

    def __str__(self) -> str:
        labels = {"running": "运行中", "stopped": "已停止", "delayed": "延误"}
        return labels.get(self.value, self.value)


@dataclass
class Vehicle:
    """A tracked vehicle with position, speed, route, and ETA info."""
    vehicle_id: str
    name: str
    route_path: list = field(default_factory=list)      # node IDs along its route
    current_position_index: int = 0                      # index into route_path
    speed_kmh: float = 0.0                               # current speed km/h
    max_speed_kmh: float = 60.0
    status: VehicleStatus = VehicleStatus.STOPPED
    eta_seconds: float = 0.0                             # estimated seconds to destination
    x: float = 0.0                                       # current canvas x
    y: float = 0.0                                       # current canvas y
    next_stop: Optional[str] = None                      # next node name

    @property
    def progress_pct(self) -> float:
        """Route progress as percentage (0-100)."""
        if not self.route_path or len(self.route_path) < 2:
            return 0.0
        return (self.current_position_index / (len(self.route_path) - 1)) * 100.0

    @property
    def is_at_destination(self) -> bool:
        """Return True if the vehicle has reached its destination."""
        return self.current_position_index >= len(self.route_path) - 1

    def to_dict(self) -> dict:
        return {
            "vehicle_id": self.vehicle_id,
            "name": self.name,
            "speed_kmh": self.speed_kmh,
            "status": self.status.value,
            "eta_seconds": self.eta_seconds,
            "progress_pct": self.progress_pct,
            "next_stop": self.next_stop,
        }
