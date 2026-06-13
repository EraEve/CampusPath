"""Vehicle Service — manages vehicle tracking and ETA computation.

Handles vehicle registration, position updates along paths,
ETA calculation, and status management.
"""

import time
from typing import Dict, List, Optional

from backend.core.nav_graph import NavGraph
from backend.models.vehicle import Vehicle, VehicleStatus
from backend.models.transport import TransportMode


class VehicleService:
    """Manages tracked vehicles on the navigation graph.

    Usage:
        svc = VehicleService()
        svc.set_graph(graph)
        v = svc.add_vehicle("V001", "Bus 1", path, speed=30.0)
        svc.update_positions(dt=1.0)
    """

    def __init__(self):
        self._graph: Optional[NavGraph] = None
        self._vehicles: Dict[str, Vehicle] = {}

    def set_graph(self, graph: NavGraph):
        """Set the active graph."""
        self._graph = graph

    # ------------------------------------------------------------------
    # Vehicle CRUD
    # ------------------------------------------------------------------

    def add_vehicle(
        self,
        vehicle_id: str,
        name: str,
        route_path: List[str],
        speed_kmh: float = 30.0,
        max_speed_kmh: float = 60.0,
    ) -> Vehicle:
        """Register a new vehicle with a route path.

        Args:
            vehicle_id: Unique vehicle identifier.
            name: Human-readable vehicle name.
            route_path: Ordered list of node IDs defining the route.
            speed_kmh: Initial speed in km/h.
            max_speed_kmh: Maximum speed in km/h.

        Returns:
            The created Vehicle object.
        """
        if self._graph and route_path:
            start_node = self._graph.get_node(route_path[0])
            x = start_node.x if start_node else 0.0
            y = start_node.y if start_node else 0.0
        else:
            x, y = 0.0, 0.0

        vehicle = Vehicle(
            vehicle_id=vehicle_id,
            name=name,
            route_path=list(route_path),
            current_position_index=0,
            speed_kmh=speed_kmh,
            max_speed_kmh=max_speed_kmh,
            status=VehicleStatus.RUNNING,
            x=x, y=y,
            next_stop=self._get_node_name(route_path[1]) if len(route_path) > 1 else None,
        )
        self._compute_eta(vehicle)
        self._vehicles[vehicle_id] = vehicle
        return vehicle

    def remove_vehicle(self, vehicle_id: str) -> bool:
        """Remove a vehicle from tracking. Returns False if not found."""
        if vehicle_id in self._vehicles:
            del self._vehicles[vehicle_id]
            return True
        return False

    def get_vehicle(self, vehicle_id: str) -> Optional[Vehicle]:
        """Return a vehicle by ID."""
        return self._vehicles.get(vehicle_id)

    def list_vehicles(self) -> List[Vehicle]:
        """Return all tracked vehicles."""
        return list(self._vehicles.values())

    # ------------------------------------------------------------------
    # Position updates
    # ------------------------------------------------------------------

    def update_positions(self, dt_seconds: float = 1.0):
        """Advance all running vehicles along their routes by dt_seconds.

        Args:
            dt_seconds: Time delta in seconds (simulation time).
        """
        for vehicle in self._vehicles.values():
            if vehicle.status != VehicleStatus.RUNNING:
                continue
            if vehicle.is_at_destination:
                vehicle.status = VehicleStatus.STOPPED
                continue

            self._advance_vehicle(vehicle, dt_seconds)
            self._compute_eta(vehicle)

    def _advance_vehicle(self, vehicle: Vehicle, dt_seconds: float):
        """Move a vehicle along its route for dt_seconds."""
        if not self._graph or len(vehicle.route_path) < 2:
            return

        speed_ms = vehicle.speed_kmh / 3.6
        remaining_dist = speed_ms * dt_seconds

        while remaining_dist > 0 and vehicle.current_position_index < len(vehicle.route_path) - 1:
            current_node_id = vehicle.route_path[vehicle.current_position_index]
            next_node_id = vehicle.route_path[vehicle.current_position_index + 1]

            curr_node = self._graph.get_node(current_node_id)
            next_node = self._graph.get_node(next_node_id)
            if curr_node is None or next_node is None:
                break

            # Distance to next node
            dx = next_node.x - vehicle.x if vehicle.x > 0 else next_node.x - curr_node.x
            dy = next_node.y - vehicle.y if vehicle.y > 0 else next_node.y - curr_node.y
            dist_to_next = (dx * dx + dy * dy) ** 0.5

            if dist_to_next <= 0:
                # Arrived at the node
                vehicle.current_position_index += 1
                vehicle.x = next_node.x
                vehicle.y = next_node.y
                # Update next stop
                idx = vehicle.current_position_index
                if idx + 1 < len(vehicle.route_path):
                    vehicle.next_stop = self._get_node_name(
                        vehicle.route_path[idx + 1]
                    )
                else:
                    vehicle.next_stop = None
                continue

            if remaining_dist >= dist_to_next:
                # Pass through this node
                remaining_dist -= dist_to_next
                vehicle.current_position_index += 1
                vehicle.x = next_node.x
                vehicle.y = next_node.y
                idx = vehicle.current_position_index
                if idx + 1 < len(vehicle.route_path):
                    vehicle.next_stop = self._get_node_name(
                        vehicle.route_path[idx + 1]
                    )
                else:
                    vehicle.next_stop = None
            else:
                # Stop partway between nodes
                fraction = remaining_dist / dist_to_next
                vehicle.x += dx * fraction
                vehicle.y += dy * fraction
                remaining_dist = 0

    def _compute_eta(self, vehicle: Vehicle):
        """Compute remaining time to destination."""
        if not self._graph or vehicle.is_at_destination:
            vehicle.eta_seconds = 0.0
            return

        total_dist = 0.0
        for i in range(vehicle.current_position_index, len(vehicle.route_path) - 1):
            edge = self._graph.get_edge(
                vehicle.route_path[i], vehicle.route_path[i + 1]
            )
            if edge:
                total_dist += edge.weight

        speed_ms = max(vehicle.speed_kmh, 1.0) / 3.6
        vehicle.eta_seconds = total_dist / speed_ms

    def _get_node_name(self, node_id: str) -> str:
        """Get human-readable node name."""
        if self._graph:
            node = self._graph.get_node(node_id)
            if node:
                return node.name
        return node_id

    # ------------------------------------------------------------------
    # Control
    # ------------------------------------------------------------------

    def set_vehicle_speed(self, vehicle_id: str, speed_kmh: float):
        """Update a vehicle's speed."""
        vehicle = self._vehicles.get(vehicle_id)
        if vehicle:
            vehicle.speed_kmh = max(0.0, min(speed_kmh, vehicle.max_speed_kmh))

    def stop_vehicle(self, vehicle_id: str):
        """Stop a vehicle."""
        vehicle = self._vehicles.get(vehicle_id)
        if vehicle:
            vehicle.status = VehicleStatus.STOPPED

    def start_vehicle(self, vehicle_id: str):
        """Start/resume a vehicle."""
        vehicle = self._vehicles.get(vehicle_id)
        if vehicle and not vehicle.is_at_destination:
            vehicle.status = VehicleStatus.RUNNING
