"""Traffic Simulator — generates periodic congestion/blockage events.

Uses threading.Timer to periodically modify congestion levels
and create blockage events on random edges, simulating real-time traffic
conditions for demonstration purposes.
"""

import random
import threading
from typing import Callable, List, Optional

from backend.core.nav_graph import NavGraph
from backend.models.traffic import CongestionLevel
from backend.services.traffic_service import TrafficService


class TrafficSimulator:
    """Periodic traffic event generator for real-time demonstrations.

    Usage:
        sim = TrafficSimulator(graph, traffic_service)
        sim.start(interval_ms=3000)   # update every 3 seconds
        sim.stop()
    """

    def __init__(
        self,
        graph: NavGraph,
        traffic_service: TrafficService,
        on_update: Optional[Callable] = None,
    ):
        self._graph = graph
        self._traffic = traffic_service
        self._on_update = on_update
        self._running = False
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()
        self._interval_ms = 3000

        # Collect all edge keys for random selection
        self._edge_keys: List[tuple] = []
        self._refresh_edge_list()

    def _refresh_edge_list(self):
        """Rebuild the list of all edge keys."""
        self._edge_keys = []
        if self._graph is None:
            return
        for from_id in self._graph:
            for edge in self._graph.get_edges(from_id):
                # Only include main roads and highways (more likely to have traffic)
                if edge.road_type.value in ("main_road", "highway", "one_way"):
                    self._edge_keys.append((edge.from_id, edge.to_id))

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def set_graph(self, graph: NavGraph):
        """Update the active graph."""
        with self._lock:
            self._graph = graph
            self._refresh_edge_list()

    def start(self, interval_ms: int = 3000):
        """Start generating traffic events."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._interval_ms = interval_ms
            self._refresh_edge_list()
        self._schedule_next()

    def stop(self):
        """Stop generating traffic events."""
        with self._lock:
            self._running = False
            if self._timer:
                self._timer.cancel()
                self._timer = None

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
        self._timer = threading.Timer(self._interval_ms / 1000.0, self._tick)
        self._timer.daemon = True
        self._timer.start()

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
        with self._lock:
            edge_keys = list(self._edge_keys)
        if edge_keys:
            num_congest = max(1, len(edge_keys) // 5)
            for _ in range(num_congest):
                edge = random.choice(edge_keys)
                level = random.choice([
                    CongestionLevel.MODERATE,
                    CongestionLevel.MODERATE,
                    CongestionLevel.HEAVY,
                ])
                self._traffic.set_congestion(edge[0], edge[1], level)

            # 4. Random blockage (5% chance)
            if random.random() < 0.05:
                edge = random.choice(edge_keys)
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
