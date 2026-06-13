"""Vehicle Simulator — animates vehicle movement along routes.

Uses tkinter's `after()` timer to advance vehicles along their planned
paths at scaled speed, updating positions and ETAs in real time.

The simulation speed is configurable (e.g., 1× = real time, 10× = fast).
"""

from typing import Callable, List, Optional

from ..core.graph import NavGraph
from ..models.vehicle import Vehicle, VehicleStatus
from ..services.vehicle_service import VehicleService


class VehicleSimulator:
    """Animates vehicles along routes using tkinter timers.

    Usage:
        sim = VehicleSimulator(root, graph, vehicle_service)
        sim.add_vehicle_to_sim("V001", path, speed=30)
        sim.start(interval_ms=100)
    """

    def __init__(
        self,
        root,  # tkinter.Tk
        graph: NavGraph,
        vehicle_service: VehicleService,
        on_update: Optional[Callable] = None,
    ):
        self._root = root
        self._graph = graph
        self._vehicles = vehicle_service
        self._on_update = on_update
        self._running = False
        self._timer_id: Optional[str] = None
        self._interval_ms = 100      # update every 100ms
        self._speed_scale = 10.0     # simulation speed multiplier

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start(self, interval_ms: int = 100):
        """Start the vehicle simulation loop."""
        if self._running:
            return
        self._running = True
        self._interval_ms = interval_ms
        self._schedule_next()

    def stop(self):
        """Stop the simulation."""
        self._running = False
        if self._timer_id:
            self._root.after_cancel(self._timer_id)
            self._timer_id = None

    def is_running(self) -> bool:
        """Return True if the simulation is active."""
        return self._running

    def set_speed_scale(self, scale: float):
        """Set simulation speed multiplier (1.0 = real time, 10.0 = 10×)."""
        self._speed_scale = max(0.1, min(scale, 100.0))

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    def _schedule_next(self):
        """Schedule the next simulation tick."""
        if not self._running:
            return
        self._timer_id = self._root.after(self._interval_ms, self._tick)

    def _tick(self):
        """Advance all running vehicles by one time step."""
        if not self._running:
            return

        # Real elapsed = interval_ms / 1000 seconds
        # Simulation time = real_elapsed * speed_scale
        dt = (self._interval_ms / 1000.0) * self._speed_scale

        self._vehicles.update_positions(dt)

        if self._on_update:
            self._on_update()

        self._schedule_next()

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def create_and_add_vehicle(
        self,
        vehicle_id: str,
        name: str,
        route_path: List[str],
        speed_kmh: float = 30.0,
    ) -> Vehicle:
        """Create a vehicle and add it to the simulation."""
        return self._vehicles.add_vehicle(vehicle_id, name, route_path, speed_kmh)
