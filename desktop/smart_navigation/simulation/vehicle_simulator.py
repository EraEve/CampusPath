"""Vehicle Simulator — animates vehicle movement along routes.

Uses a generic timer callback interface to advance vehicles along their
planned paths at scaled speed, updating positions and ETAs in real time.

Timer interface (framework-agnostic):
    schedule_timer(ms, callback) -> token
    cancel_timer(token) -> None

The simulation speed is configurable (e.g., 1× = real time, 10× = fast).
"""

from typing import Any, Callable, List, Optional

from ..core.graph import NavGraph
from ..models.vehicle import Vehicle, VehicleStatus
from ..services.vehicle_service import VehicleService

# Sentinel for "no timer set"
_NO_TIMER = object()


class VehicleSimulator:
    """Animates vehicles along routes using a generic timer interface.

    Usage (tkinter — backward compatible):
        sim = VehicleSimulator(root, graph, vehicle_service)
        sim.start(interval_ms=100)

    Usage (wxPython / generic):
        sim = VehicleSimulator(
            graph, vehicle_service,
            schedule_timer=wx_frame.schedule_timer,
            cancel_timer=wx_frame.cancel_timer,
        )
        sim.start(interval_ms=100)
    """

    def __init__(
        self,
        graph: NavGraph,
        vehicle_service: VehicleService,
        on_update: Optional[Callable] = None,
        schedule_timer: Optional[Callable[[int, Callable], Any]] = None,
        cancel_timer: Optional[Callable[[Any], None]] = None,
        root=None,  # tkinter backward compat
    ):
        self._graph = graph
        self._vehicles = vehicle_service
        self._on_update = on_update
        self._running = False
        self._timer_token: Any = _NO_TIMER
        self._interval_ms = 100      # update every 100ms
        self._speed_scale = 10.0     # simulation speed multiplier

        # Resolve timer interface — prefer explicit callbacks, fall back to
        # tkinter root.after / root.after_cancel.
        if schedule_timer is not None and cancel_timer is not None:
            self._schedule_timer = schedule_timer
            self._cancel_timer = cancel_timer
        elif root is not None and hasattr(root, "after"):
            self._schedule_timer = lambda ms, cb: root.after(ms, cb)
            self._cancel_timer = lambda tok: root.after_cancel(tok)
        else:
            raise ValueError(
                "VehicleSimulator requires either (schedule_timer + cancel_timer) "
                "or a tkinter root with after()/after_cancel()."
            )

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
        if self._timer_token is not _NO_TIMER:
            self._cancel_timer(self._timer_token)
            self._timer_token = _NO_TIMER

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
        self._timer_token = self._schedule_timer(self._interval_ms, self._tick)

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
