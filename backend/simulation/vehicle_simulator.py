"""Vehicle Simulator — animates vehicle movement along routes.

Uses threading.Timer to advance vehicles along their planned
paths at scaled speed, updating positions and ETAs in real time.

The simulation speed is configurable (e.g., 1x = real time, 10x = fast).
"""

import threading
from typing import Callable, List, Optional

from backend.core.nav_graph import NavGraph
from backend.models.vehicle import Vehicle, VehicleStatus
from backend.services.vehicle_service import VehicleService


class VehicleSimulator:
    """Animates vehicles along routes using threading timers.

    Usage:
        sim = VehicleSimulator(graph, vehicle_service)
        sim.add_vehicle_to_sim("V001", path, speed=30)
        sim.start(interval_ms=100)
    """

    def __init__(
        self,
        graph: NavGraph,
        vehicle_service: VehicleService,
        on_update: Optional[Callable] = None,
    ):
        self._graph = graph
        self._vehicles = vehicle_service
        self._on_update = on_update
        self._running = False
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._interval_ms = 100      # update every 100ms
        self._speed_scale = 10.0     # simulation speed multiplier

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def set_graph(self, graph: NavGraph):
        """Update the active graph."""
        with self._lock:
            self._graph = graph

    def start(self, interval_ms: int = 100):
        """Start the vehicle simulation loop."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._interval_ms = interval_ms
        self._schedule_next()

    def stop(self):
        """Stop the simulation."""
        with self._lock:
            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None

    def is_running(self) -> bool:
        """Return True if the simulation is active."""
        return self._running

    def set_speed_scale(self, scale: float):
        """Set simulation speed multiplier (1.0 = real time, 10.0 = 10x)."""
        self._speed_scale = max(0.1, min(scale, 100.0))

    # ------------------------------------------------------------------
    # Simulation loop
    # ------------------------------------------------------------------

    def _schedule_next(self):
        """Schedule the next simulation tick."""
        if not self._running:
            return
        self._timer = threading.Timer(self._interval_ms / 1000.0, self._tick)
        self._timer.daemon = True
        self._timer.start()

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
