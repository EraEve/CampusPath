"""Traffic Simulator — generates periodic congestion/blockage events.

Uses a generic timer callback interface to periodically modify congestion
levels and create blockage events on random edges, simulating real-time
traffic conditions for demonstration purposes.

Timer interface (framework-agnostic):
    schedule_timer(ms, callback) -> token
    cancel_timer(token) -> None

Backward compatible: if ``root`` has an ``after`` method (tkinter), it is
auto-adapted.  For wxPython, pass ``schedule_timer`` / ``cancel_timer``.
"""

import random
from typing import Any, Callable, List, Optional

from ..core.graph import NavGraph
from ..models.traffic import CongestionLevel
from ..services.traffic_service import TrafficService

# Sentinel for "no timer set"
_NO_TIMER = object()


class TrafficSimulator:
    """Periodic traffic event generator for real-time demonstrations.

    Usage (tkinter — backward compatible):
        sim = TrafficSimulator(root, graph, traffic_service)
        sim.start(interval_ms=3000)

    Usage (wxPython / generic):
        sim = TrafficSimulator(
            graph, traffic_service,
            schedule_timer=wx_frame.schedule_timer,
            cancel_timer=wx_frame.cancel_timer,
        )
        sim.start(interval_ms=3000)
    """

    def __init__(
        self,
        graph: NavGraph,
        traffic_service: TrafficService,
        on_update: Optional[Callable] = None,
        schedule_timer: Optional[Callable[[int, Callable], Any]] = None,
        cancel_timer: Optional[Callable[[Any], None]] = None,
        root=None,  # tkinter backward compat
    ):
        self._graph = graph
        self._traffic = traffic_service
        self._on_update = on_update
        self._running = False
        self._timer_token: Any = _NO_TIMER
        self._interval_ms = 3000

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
                "TrafficSimulator requires either (schedule_timer + cancel_timer) "
                "or a tkinter root with after()/after_cancel()."
            )

        # Collect all edge keys for random selection
        self._edge_keys: List[tuple] = []
        self._refresh_edge_list()

    def _refresh_edge_list(self):
        """Rebuild the list of all edge keys."""
        self._edge_keys = []
        for from_id in self._graph:
            for edge in self._graph.get_edges(from_id):
                # Only include main roads and highways (more likely to have traffic)
                if edge.road_type.value in ("main_road", "highway", "one_way"):
                    self._edge_keys.append((edge.from_id, edge.to_id))

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def start(self, interval_ms: int = 3000):
        """Start generating traffic events."""
        if self._running:
            return
        self._running = True
        self._interval_ms = interval_ms
        self._refresh_edge_list()
        self._schedule_next()

    def stop(self):
        """Stop generating traffic events."""
        self._running = False
        if self._timer_token is not _NO_TIMER:
            self._cancel_timer(self._timer_token)
            self._timer_token = _NO_TIMER

    def is_running(self) -> bool:
        """Return True if the simulator is active."""
        return self._running

    # ------------------------------------------------------------------
    # Event generation
    # ------------------------------------------------------------------

    def _schedule_next(self):
        """Schedule the next traffic event."""
        if not self._running:
            return
        self._timer_token = self._schedule_timer(self._interval_ms, self._tick)

    def _tick(self):
        """Generate one round of traffic events."""
        if not self._running or not self._edge_keys:
            self._schedule_next()
            return

        # 1. Randomly clear some old congestion (40% chance per congested edge)
        congested = self._traffic.get_all_congested()
        for entry in congested:
            if random.random() < 0.4:
                self._traffic.clear_congestion(entry["from"], entry["to"])

        # 2. Clear some old blockages (30% chance per blockage)
        blockages = self._traffic.get_blockages()
        for b in blockages:
            if random.random() < 0.3:
                self._traffic.unblock_edge(b.edge_key[0], b.edge_key[1])

        # 3. Add new congestion to random edges (20% of edges)
        num_congest = max(1, len(self._edge_keys) // 5)
        for _ in range(num_congest):
            edge = random.choice(self._edge_keys)
            level = random.choice([
                CongestionLevel.MODERATE,
                CongestionLevel.MODERATE,
                CongestionLevel.HEAVY,
            ])
            self._traffic.set_congestion(edge[0], edge[1], level)

        # 4. Random blockage (5% chance)
        if random.random() < 0.05 and self._edge_keys:
            edge = random.choice(self._edge_keys)
            self._traffic.block_edge(
                edge[0], edge[1],
                description=random.choice([
                    "交通事故", "道路施工", "临时管制", "车辆故障"
                ])
            )

        # Notify
        if self._on_update:
            self._on_update()

        self._schedule_next()
