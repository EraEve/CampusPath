"""Smart Navigation API Routes — Phase 3: REST + SSE layer.

Provides 30+ endpoints for the "智慧导航" (SmartNav) page:
- Map/Scene management (4)
- Pathfinding (4)
- POI Search (2)
- Traffic management (4)
- Vehicle tracking (5)
- Real-time navigation (5 + SSE stream)
- Simulation control (5)
- Metadata (1)

All follow the existing app.py pattern: {"success": True/False, "data": ...}

SSE stream: GET /api/smart/navigation/stream
    Events: navigation_update, traffic_update, vehicle_update, alert, heartbeat

Usage — register in app.py:
    from backend.routes_smart import register_smart_routes
    register_smart_routes(app)
"""

import json
import queue
import threading
import time
from typing import Any, Dict, List, Optional

from flask import Response, jsonify, request, stream_with_context

from backend.core.map_manager import MapManager
from backend.core.nav_graph import NavGraph
from backend.models.transport import TransportMode, POICategory, SceneType, RoadType
from backend.models.traffic import CongestionLevel, TrafficState
from backend.models.vehicle import Vehicle, VehicleStatus
from backend.models.path_result import PathResult
from backend.services.path_service import PathService
from backend.services.search_service import SearchService
from backend.services.traffic_service import TrafficService
from backend.services.vehicle_service import VehicleService
from backend.services.navigation_service import NavigationService
from backend.simulation.traffic_simulator import TrafficSimulator
from backend.simulation.vehicle_simulator import VehicleSimulator

# ═══════════════════════════════════════════════════════════════════════════
# Global singletons (lazy-init)
# ═══════════════════════════════════════════════════════════════════════════

_map_manager: Optional[MapManager] = None
_path_service: Optional[PathService] = None
_search_service: Optional[SearchService] = None
_traffic_service: Optional[TrafficService] = None
_vehicle_service: Optional[VehicleService] = None
_navigation_service: Optional[NavigationService] = None
_traffic_simulator: Optional[TrafficSimulator] = None
_vehicle_simulator: Optional[VehicleSimulator] = None
_active_scene_id: Optional[str] = None

# SSE subscribers: list of queue.Queue — each active SSE client has one
_sse_subscribers: List[queue.Queue] = []
_sse_lock = threading.Lock()

# Valid values for validation
VALID_ALGORITHMS = [
    "dijkstra", "a_star", "bfs", "bidirectional_dijkstra",
    "bidirectional_bfs", "congestion_avoidance", "multi_criteria",
]
VALID_HEURISTICS = ["euclidean", "manhattan", "floor_aware"]
VALID_MODES = [m.value for m in TransportMode]
VALID_ROAD_TYPES = [r.value for r in RoadType]
VALID_CONGESTION_LEVELS = [c.value for c in CongestionLevel]
VALID_POI_CATEGORIES = [p.value for p in POICategory]


# ═══════════════════════════════════════════════════════════════════════════
# Lazy init helpers
# ═══════════════════════════════════════════════════════════════════════════

def _init_all():
    """Initialize all singletons and load demo maps."""
    global _map_manager, _path_service, _search_service
    global _traffic_service, _vehicle_service, _navigation_service
    global _traffic_simulator, _vehicle_simulator, _active_scene_id

    if _map_manager is None:
        _map_manager = MapManager()
        _map_manager.load_all_demo_maps()
        if _map_manager._scenes:
            _active_scene_id = list(_map_manager._scenes.keys())[0]

    if _path_service is None:
        _path_service = PathService()
    if _search_service is None:
        _search_service = SearchService()
    if _traffic_service is None:
        _traffic_service = TrafficService()
    if _vehicle_service is None:
        _vehicle_service = VehicleService()
    if _navigation_service is None:
        _navigation_service = NavigationService()

    # Initialize simulators lazily when needed


def _get_graph() -> Optional[NavGraph]:
    """Get the currently active graph."""
    _init_all()
    if _active_scene_id and _map_manager:
        graph = _map_manager.get_graph(_active_scene_id)
        if graph and _traffic_service and _traffic_service._graph is None:
            _traffic_service.set_graph(graph)
        if graph and _vehicle_service and _vehicle_service._graph is None:
            _vehicle_service.set_graph(graph)
        return graph
    return None


def _get_active_scene_id() -> str:
    """Get the active scene ID, initializing if needed."""
    _init_all()
    return _active_scene_id or ""


# ═══════════════════════════════════════════════════════════════════════════
# SSE: broadcast helpers
# ═══════════════════════════════════════════════════════════════════════════

def _sse_broadcast(event: str, data: Any):
    """Push an event to all connected SSE clients."""
    with _sse_lock:
        dead = []
        for q in _sse_subscribers:
            try:
                q.put_nowait({"event": event, "data": data})
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_subscribers.remove(q)


def _sse_subscribe() -> queue.Queue:
    """Create a new SSE subscriber queue (max 200 backlog)."""
    q: queue.Queue = queue.Queue(maxsize=200)
    with _sse_lock:
        _sse_subscribers.append(q)
    return q


def _sse_unsubscribe(q: queue.Queue):
    """Remove a subscriber queue."""
    with _sse_lock:
        if q in _sse_subscribers:
            _sse_subscribers.remove(q)


def _on_navigation_alert(alert: dict):
    """Callback for NavigationService alerts → SSE broadcast."""
    _sse_broadcast("alert", alert)


def _on_traffic_update():
    """Callback for TrafficSimulator → SSE broadcast."""
    if _traffic_service:
        _sse_broadcast("traffic_update", _traffic_service.get_traffic_summary())


def _on_vehicle_update():
    """Callback for VehicleSimulator → SSE broadcast."""
    if _vehicle_service:
        vehicles = [v.to_dict() for v in _vehicle_service.list_vehicles()]
        _sse_broadcast("vehicle_update", {"vehicles": vehicles, "count": len(vehicles)})


# ═══════════════════════════════════════════════════════════════════════════
# Helpers: validation & serialization
# ═══════════════════════════════════════════════════════════════════════════

def _error(msg: str, code: int = 400):
    """Return a standard error response."""
    return jsonify({"success": False, "message": msg}), code


def _ok(data: Any = None, **kwargs):
    """Return a standard success response."""
    result = {"success": True}
    if data is not None:
        result["data"] = data
    result.update(kwargs)
    return jsonify(result)


def _path_result_to_dict(pr: PathResult) -> dict:
    """Convert PathResult to JSON-safe dict with extra computed fields."""
    d = pr.to_dict()
    d["path_length"] = pr.path_length
    d["is_reachable"] = pr.is_reachable
    if pr.path:
        graph = _get_graph()
        d["path_names"] = [
            (graph.get_node(nid).name if graph and graph.get_node(nid) else nid)
            for nid in pr.path
        ]
        # Path coordinates for frontend rendering
        if graph:
            coords = []
            for nid in pr.path:
                node = graph.get_node(nid)
                if node:
                    coords.append({"x": node.x, "y": node.y, "node_id": nid,
                                   "name": node.name, "floor": node.floor})
            d["path_coords"] = coords
    return d


def _scene_to_dict(scene) -> dict:
    """Convert SceneMap to dict."""
    return {
        "scene_id": scene.scene_id,
        "name": scene.name,
        "scene_type": scene.scene_type.value,
        "scene_type_label": str(scene.scene_type),
        "transport_modes": [m.value for m in scene.transport_modes],
        "transport_mode_labels": [str(m) for m in scene.transport_modes],
        "description": scene.description,
        "node_count": scene.node_count,
        "edge_count": scene.edge_count,
        "bounds": scene.bounds,
        "is_outdoor": scene.scene_type.is_outdoor,
        "is_indoor": scene.scene_type.is_indoor,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Route registration
# ═══════════════════════════════════════════════════════════════════════════

def register_smart_routes(app):
    """Register all Smart Navigation routes on the Flask app."""

    # ======================================================================
    # 1. MAP / SCENE MANAGEMENT (4 endpoints)
    # ======================================================================

    @app.route("/api/smart/scenes", methods=["GET"])
    def api_smart_scenes():
        """GET /api/smart/scenes — List all loaded map scenes."""
        try:
            _init_all()
            scenes = _map_manager.list_scenes()
            return _ok({
                "scenes": [_scene_to_dict(s) for s in scenes],
                "active_scene_id": _active_scene_id,
                "count": len(scenes),
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/scenes/<scene_id>", methods=["GET"])
    def api_smart_scene_detail(scene_id):
        """GET /api/smart/scenes/<id> — Get scene metadata and nodes."""
        try:
            _init_all()
            scene = _map_manager.get_scene(scene_id)
            if not scene:
                return _error(f"Scene '{scene_id}' not found.", 404)

            graph = _map_manager.get_graph(scene_id)
            nodes = []
            edges = []
            seen_edges = set()
            if graph:
                for node in graph.vertices.values():
                    nodes.append({
                        "node_id": node.node_id,
                        "name": node.name,
                        "type": node.node_type.value,
                        "type_label": str(node.node_type) if hasattr(node.node_type, '__str__') else node.node_type.value,
                        "floor": node.floor,
                        "x": node.x, "y": node.y,
                        "poi_category": node.poi_category.value if node.poi_category else None,
                    })
                # Collect all edges (deduplicate by (from, to) key)
                for from_id in graph:
                    for edge in graph.get_edges(from_id):
                        key = (edge.from_id, edge.to_id)
                        if key not in seen_edges:
                            seen_edges.add(key)
                            edges.append({
                                "from": edge.from_id,
                                "to": edge.to_id,
                                "weight": round(edge.weight, 1),
                                "road_type": edge.road_type.value,
                                "name": edge.name or "",
                            })

            return _ok({
                "scene": _scene_to_dict(scene),
                "nodes": nodes,
                "edges": edges,
                "node_count": len(nodes),
                "edge_count": len(edges),
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/scenes/<scene_id>/activate", methods=["POST"])
    def api_smart_scene_activate(scene_id):
        """POST /api/smart/scenes/<id>/activate — Set active scene for all operations."""
        global _active_scene_id
        try:
            _init_all()
            scene = _map_manager.get_scene(scene_id)
            if not scene:
                return _error(f"Scene '{scene_id}' not found.", 404)

            _active_scene_id = scene_id
            graph = _map_manager.get_graph(scene_id)
            if graph:
                if _traffic_service:
                    _traffic_service.set_graph(graph)
                if _vehicle_service:
                    _vehicle_service.set_graph(graph)
                if _traffic_simulator and _traffic_simulator.is_running():
                    _traffic_simulator.set_graph(graph)
                if _vehicle_simulator and _vehicle_simulator.is_running():
                    _vehicle_simulator.set_graph(graph)

            _sse_broadcast("scene_changed", {"scene_id": scene_id, "name": scene.name})
            return _ok({"active_scene_id": scene_id, "name": scene.name})
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/scenes/<scene_id>/stats", methods=["GET"])
    def api_smart_scene_stats(scene_id):
        """GET /api/smart/scenes/<id>/stats — Graph statistics for a scene."""
        try:
            _init_all()
            graph = _map_manager.get_graph(scene_id)
            if not graph:
                return _error(f"Scene '{scene_id}' not found.", 404)

            # Compute stats
            degrees = []
            poi_counts = {}
            type_counts = {}
            floor_counts = {}
            for nid in graph:
                node = graph.vertices.get(nid)
                deg = len(graph.get_edges(nid))
                degrees.append(deg)
                if node:
                    t = node.node_type.value
                    type_counts[t] = type_counts.get(t, 0) + 1
                    floor_counts[node.floor] = floor_counts.get(node.floor, 0) + 1
                    if node.poi_category:
                        cat = node.poi_category.value
                        poi_counts[cat] = poi_counts.get(cat, 0) + 1

            return _ok({
                "scene_id": scene_id,
                "total_nodes": graph.total_vertices,
                "total_edges": graph.total_edges,
                "avg_degree": round(sum(degrees) / len(degrees), 2) if degrees else 0,
                "min_degree": min(degrees) if degrees else 0,
                "max_degree": max(degrees) if degrees else 0,
                "type_distribution": type_counts,
                "floor_distribution": floor_counts,
                "poi_distribution": poi_counts,
                "density": round(graph.total_edges / max(graph.total_vertices, 1), 2),
            })
        except Exception as e:
            return _error(str(e), 500)

    # ======================================================================
    # 2. PATHFINDING (4 endpoints)
    # ======================================================================

    @app.route("/api/smart/path", methods=["POST"])
    def api_smart_path():
        """POST /api/smart/path — Find a path with full options.

        Body: {
            "start": "N001", "goal": "N025",
            "transport_mode": "driving",      // walking/driving/bus/train/subway
            "algorithm": "dijkstra",           // dijkstra/a_star/bfs/bidirectional_*
            "heuristic": "euclidean",          // for a_star
            "highway_priority": false,
            "congestion_avoidance": false,
            "congestion_threshold": 1.5,
            "multi_criteria": false,
            "w_distance": 0.4, "w_time": 0.4, "w_cost": 0.2,
            "blocked_edges": [["N001","N002"], ...],
            "scene_id": "campus"               // optional, uses active if omitted
        }
        """
        try:
            data = request.get_json(silent=True) or {}
            start = data.get("start", "")
            goal = data.get("goal", "")

            if not start or not goal:
                return _error("Both 'start' and 'goal' are required.")

            # Scene
            scene_id = data.get("scene_id", _get_active_scene_id())
            graph = _map_manager.get_graph(scene_id) if _map_manager else None
            if not graph:
                return _error("No active scene. Load maps first.", 500)

            # Validate nodes
            if not graph.has_node(start):
                return _error(f"Start node '{start}' not found.", 404)
            if not graph.has_node(goal):
                return _error(f"Goal node '{goal}' not found.", 404)

            # Parse options
            mode_str = data.get("transport_mode", "driving")
            if mode_str not in VALID_MODES:
                return _error(f"Invalid transport mode '{mode_str}'. Valid: {VALID_MODES}")
            mode = TransportMode(mode_str)

            algo = data.get("algorithm", "dijkstra")
            if algo not in VALID_ALGORITHMS:
                return _error(f"Invalid algorithm '{algo}'. Valid: {VALID_ALGORITHMS}")

            heuristic = data.get("heuristic", "euclidean")
            if heuristic not in VALID_HEURISTICS:
                return _error(f"Invalid heuristic '{heuristic}'. Valid: {VALID_HEURISTICS}")

            highway_priority = data.get("highway_priority", False)
            congestion_avoidance = data.get("congestion_avoidance", False)
            congestion_threshold = float(data.get("congestion_threshold", 1.5))
            multi_criteria = data.get("multi_criteria", False)
            w_distance = float(data.get("w_distance", 0.4))
            w_time = float(data.get("w_time", 0.4))
            w_cost = float(data.get("w_cost", 0.2))
            blocked_edges = set(
                tuple(e) for e in data.get("blocked_edges", [])
            ) if data.get("blocked_edges") else None

            if not _path_service:
                return _error("Path service not initialized.", 500)

            result = _path_service.find_path(
                graph, start, goal,
                transport_mode=mode,
                algorithm=algo,
                heuristic=heuristic,
                highway_priority=highway_priority,
                congestion_avoidance=congestion_avoidance,
                congestion_threshold=congestion_threshold,
                multi_criteria=multi_criteria,
                w_distance=w_distance,
                w_time=w_time,
                w_cost=w_cost,
                blocked_edges=blocked_edges,
            )

            return _ok({
                "result": _path_result_to_dict(result),
                "scene_id": scene_id,
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/compare", methods=["POST"])
    def api_smart_compare():
        """POST /api/smart/compare — Compare all 8 algorithms on a start→goal pair.

        Body: {
            "start": "N001", "goal": "N025",
            "transport_mode": "walking",
            "scene_id": "campus"       // optional
        }
        """
        try:
            data = request.get_json(silent=True) or {}
            start = data.get("start", "")
            goal = data.get("goal", "")

            if not start or not goal:
                return _error("Both 'start' and 'goal' are required.")

            scene_id = data.get("scene_id", _get_active_scene_id())
            graph = _map_manager.get_graph(scene_id) if _map_manager else None
            if not graph:
                return _error("No active scene.", 500)

            if not graph.has_node(start):
                return _error(f"Start node '{start}' not found.", 404)
            if not graph.has_node(goal):
                return _error(f"Goal node '{goal}' not found.", 404)

            mode_str = data.get("transport_mode", "walking")
            if mode_str not in VALID_MODES:
                return _error(f"Invalid transport mode '{mode_str}'.")
            mode = TransportMode(mode_str)

            if not _path_service:
                return _error("Path service not initialized.", 500)

            results = _path_service.compare_algorithms(graph, start, goal, mode)
            comparison = {
                "start": start,
                "goal": goal,
                "transport_mode": mode.value,
                "scene_id": scene_id,
                "algorithm_count": len(results),
                "results": [
                    _path_result_to_dict(r) for r in results if r.algorithm and "_error" not in r.algorithm
                ],
                "errors": [
                    {"algorithm": r.algorithm, "reachable": False}
                    for r in results if "_error" in (r.algorithm or "")
                ],
                "summary": {
                    "shortest_distance": min(
                        (r.total_distance for r in results if r.is_reachable), default=float("inf")
                    ),
                    "fastest_path": min(
                        (r.total_time for r in results if r.is_reachable), default=float("inf")
                    ),
                    "least_visited": min(
                        (r.nodes_visited for r in results if r.is_reachable), default=float("inf")
                    ),
                },
            }
            return _ok(comparison)
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/path/waypoints", methods=["POST"])
    def api_smart_path_waypoints():
        """POST /api/smart/path/waypoints — Multi-waypoint routing.

        Body: {
            "start": "N001", "goal": "N025",
            "waypoints": ["N010", "N015"],
            ... same options as /api/smart/path
        }
        """
        try:
            data = request.get_json(silent=True) or {}
            start = data.get("start", "")
            goal = data.get("goal", "")
            waypoints = data.get("waypoints", [])

            if not start or not goal:
                return _error("Both 'start' and 'goal' are required.")
            if not waypoints or len(waypoints) == 0:
                return _error("At least one waypoint is required. Use /api/smart/path for direct routing.")

            scene_id = data.get("scene_id", _get_active_scene_id())
            graph = _map_manager.get_graph(scene_id) if _map_manager else None
            if not graph:
                return _error("No active scene.", 500)

            for wp in waypoints:
                if not graph.has_node(wp):
                    return _error(f"Waypoint '{wp}' not found.", 404)

            mode_str = data.get("transport_mode", "driving")
            if mode_str not in VALID_MODES:
                return _error(f"Invalid transport mode '{mode_str}'.")
            mode = TransportMode(mode_str)

            algo = data.get("algorithm", "dijkstra")
            if algo not in VALID_ALGORITHMS:
                return _error(f"Invalid algorithm '{algo}'.")

            if not _path_service:
                return _error("Path service not initialized.", 500)

            result = _path_service.find_path(
                graph, start, goal,
                transport_mode=mode,
                algorithm=algo,
                heuristic=data.get("heuristic", "euclidean"),
                waypoints=waypoints,
                highway_priority=data.get("highway_priority", False),
                congestion_avoidance=data.get("congestion_avoidance", False),
                multi_criteria=data.get("multi_criteria", False),
            )

            return _ok({
                "result": _path_result_to_dict(result),
                "segments": len(waypoints) + 1,
                "scene_id": scene_id,
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/path/accessible", methods=["POST"])
    def api_smart_path_accessible():
        """POST /api/smart/path/accessible — Wheelchair-accessible routing (no stairs).

        Body: {
            "start": "N001", "goal": "N025",
            "transport_mode": "walking",
            "scene_id": "campus"
        }
        """
        try:
            data = request.get_json(silent=True) or {}
            start = data.get("start", "")
            goal = data.get("goal", "")

            if not start or not goal:
                return _error("Both 'start' and 'goal' are required.")

            scene_id = data.get("scene_id", _get_active_scene_id())
            graph = _map_manager.get_graph(scene_id) if _map_manager else None
            if not graph:
                return _error("No active scene.", 500)

            if not graph.has_node(start):
                return _error(f"Start node '{start}' not found.", 404)
            if not graph.has_node(goal):
                return _error(f"Goal node '{goal}' not found.", 404)

            mode = TransportMode(data.get("transport_mode", "walking"))

            # Build blocked_edges = all stairs
            blocked_edges = set()
            for from_id in graph:
                for edge in graph.get_edges(from_id):
                    if edge.road_type.value == "stairs" or (
                        hasattr(edge, 'is_stairs') and edge.is_stairs
                    ):
                        blocked_edges.add((edge.from_id, edge.to_id))

            if not _path_service:
                return _error("Path service not initialized.", 500)

            result = _path_service.find_path(
                graph, start, goal,
                transport_mode=mode,
                algorithm="dijkstra",
                blocked_edges=blocked_edges,
            )

            return _ok({
                "result": _path_result_to_dict(result),
                "blocked_stairs_count": len(blocked_edges),
                "scene_id": scene_id,
            })
        except Exception as e:
            return _error(str(e), 500)

    # ======================================================================
    # 3. POI SEARCH (2 endpoints)
    # ======================================================================

    @app.route("/api/smart/search/nearby", methods=["GET"])
    def api_smart_search_nearby():
        """GET /api/smart/search/nearby — Search POIs near a node or coordinates.

        Query params:
            center_node=N001    — center node ID (or use cx,cy)
            cx=500&cy=300       — center coordinates (alternative)
            categories=scenic,food — comma-separated category filter
            radius=200          — max search radius
            max_results=20
            scene_id=campus     — optional
        """
        try:
            _init_all()
            scene_id = request.args.get("scene_id", _get_active_scene_id())
            graph = _map_manager.get_graph(scene_id) if _map_manager else None
            if not graph:
                return _error("No active scene.", 500)

            center_node = request.args.get("center_node", "")
            cx = float(request.args.get("cx", 0))
            cy = float(request.args.get("cy", 0))
            categories_str = request.args.get("categories", "")
            categories = [c.strip() for c in categories_str.split(",") if c.strip()] if categories_str else None
            radius = float(request.args.get("radius", float("inf")))
            max_results = int(request.args.get("max_results", 20))

            if not _search_service:
                return _error("Search service not initialized.", 500)

            results = _search_service.search_nearby(
                graph,
                center_node_id=center_node if center_node else None,
                center_x=cx if not center_node else 0,
                center_y=cy if not center_node else 0,
                categories=categories,
                radius=radius,
                max_results=max_results,
            )

            return _ok({
                "results": results,
                "count": len(results),
                "scene_id": scene_id,
                "center_node": center_node or None,
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/search/categories", methods=["GET"])
    def api_smart_search_categories():
        """GET /api/smart/search/categories — POI category summary with counts."""
        try:
            _init_all()
            scene_id = request.args.get("scene_id", _get_active_scene_id())
            graph = _map_manager.get_graph(scene_id) if _map_manager else None
            if not graph:
                return _error("No active scene.", 500)

            if not _search_service:
                return _error("Search service not initialized.", 500)

            categories = _search_service.get_poi_categories(graph)
            total_pois = sum(c["count"] for c in categories)
            return _ok({
                "categories": categories,
                "total_pois": total_pois,
                "scene_id": scene_id,
            })
        except Exception as e:
            return _error(str(e), 500)

    # ======================================================================
    # 4. TRAFFIC MANAGEMENT (4 endpoints)
    # ======================================================================

    @app.route("/api/smart/traffic", methods=["GET"])
    def api_smart_traffic():
        """GET /api/smart/traffic — Current traffic summary."""
        try:
            _init_all()
            if not _traffic_service:
                return _error("Traffic service not initialized.", 500)

            summary = _traffic_service.get_traffic_summary()
            return _ok(summary)
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/traffic/congestion", methods=["POST"])
    def api_smart_traffic_congestion():
        """POST /api/smart/traffic/congestion — Set congestion on an edge.

        Body: {
            "from": "N001", "to": "N002",
            "level": "heavy"      // normal/moderate/heavy/blocked
        }
        """
        try:
            _init_all()
            data = request.get_json(silent=True) or {}
            from_id = data.get("from", "")
            to_id = data.get("to", "")
            level_str = data.get("level", "normal")

            if not from_id or not to_id:
                return _error("Both 'from' and 'to' are required.")

            if level_str not in VALID_CONGESTION_LEVELS:
                return _error(f"Invalid congestion level '{level_str}'. Valid: {VALID_CONGESTION_LEVELS}")

            graph = _get_graph()
            if graph and not graph.get_edge(from_id, to_id):
                return _error(f"Edge '{from_id}→{to_id}' not found.", 404)

            if not _traffic_service:
                return _error("Traffic service not initialized.", 500)
            if graph:
                _traffic_service.set_graph(graph)

            if level_str == "blocked":
                _traffic_service.block_edge(from_id, to_id, description="手动设置阻塞")
            else:
                level = CongestionLevel(level_str)
                _traffic_service.set_congestion(from_id, to_id, level)

            _sse_broadcast("traffic_update", _traffic_service.get_traffic_summary())
            return _ok({
                "edge": f"{from_id}→{to_id}",
                "level": level_str,
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/traffic/blockage", methods=["POST"])
    def api_smart_traffic_blockage():
        """POST /api/smart/traffic/blockage — Block or unblock an edge.

        Body: {
            "from": "N001", "to": "N002",
            "action": "block",       // "block" or "unblock"
            "description": "施工中"
        }
        """
        try:
            _init_all()
            data = request.get_json(silent=True) or {}
            from_id = data.get("from", "")
            to_id = data.get("to", "")
            action = data.get("action", "block")

            if not from_id or not to_id:
                return _error("Both 'from' and 'to' are required.")

            graph = _get_graph()
            if graph and not graph.get_edge(from_id, to_id):
                return _error(f"Edge '{from_id}→{to_id}' not found.", 404)

            if not _traffic_service:
                return _error("Traffic service not initialized.", 500)
            if graph:
                _traffic_service.set_graph(graph)

            if action == "unblock":
                _traffic_service.unblock_edge(from_id, to_id)
                msg = f"Edge {from_id}→{to_id} unblocked."
            else:
                _traffic_service.block_edge(
                    from_id, to_id,
                    description=data.get("description", "手动阻塞"),
                )
                msg = f"Edge {from_id}→{to_id} blocked."

            _sse_broadcast("traffic_update", _traffic_service.get_traffic_summary())
            return _ok({"message": msg})
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/traffic", methods=["DELETE"])
    def api_smart_traffic_clear():
        """DELETE /api/smart/traffic — Clear all traffic conditions."""
        try:
            _init_all()
            if not _traffic_service:
                return _error("Traffic service not initialized.", 500)
            _traffic_service.clear_all()
            _sse_broadcast("traffic_update", {"congested_edges": 0, "blocked_edges": 0})
            return _ok({"message": "All traffic conditions cleared."})
        except Exception as e:
            return _error(str(e), 500)

    # ======================================================================
    # 5. VEHICLE TRACKING (5 endpoints)
    # ======================================================================

    @app.route("/api/smart/vehicles", methods=["GET"])
    def api_smart_vehicles():
        """GET /api/smart/vehicles — List all tracked vehicles."""
        try:
            _init_all()
            if not _vehicle_service:
                return _error("Vehicle service not initialized.", 500)

            vehicles = _vehicle_service.list_vehicles()
            return _ok({
                "vehicles": [v.to_dict() for v in vehicles],
                "count": len(vehicles),
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/vehicles", methods=["POST"])
    def api_smart_vehicles_add():
        """POST /api/smart/vehicles — Add a new vehicle with a route.

        Body: {
            "vehicle_id": "V001",
            "name": "Bus Line 1",
            "route_path": ["N001", "N005", "N025"],
            "speed_kmh": 30,
            "max_speed_kmh": 60
        }
        """
        try:
            _init_all()
            data = request.get_json(silent=True) or {}
            vehicle_id = data.get("vehicle_id", "")
            name = data.get("name", vehicle_id)
            route_path = data.get("route_path", [])
            speed_kmh = float(data.get("speed_kmh", 30))
            max_speed = float(data.get("max_speed_kmh", 60))

            if not vehicle_id:
                return _error("'vehicle_id' is required.")
            if len(route_path) < 2:
                return _error("'route_path' must have at least 2 nodes.")

            graph = _get_graph()
            if not graph:
                return _error("No active scene.", 500)

            for nid in route_path:
                if not graph.has_node(nid):
                    return _error(f"Node '{nid}' in route_path not found.", 404)

            if not _vehicle_service:
                return _error("Vehicle service not initialized.", 500)
            if graph:
                _vehicle_service.set_graph(graph)

            if _vehicle_service.get_vehicle(vehicle_id):
                return _error(f"Vehicle '{vehicle_id}' already exists.", 409)

            vehicle = _vehicle_service.add_vehicle(
                vehicle_id, name, route_path, speed_kmh, max_speed,
            )
            _sse_broadcast("vehicle_added", vehicle.to_dict())
            return _ok({"vehicle": vehicle.to_dict()})
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/vehicles/<vehicle_id>", methods=["DELETE"])
    def api_smart_vehicles_remove(vehicle_id):
        """DELETE /api/smart/vehicles/<id> — Remove a vehicle."""
        try:
            _init_all()
            if not _vehicle_service:
                return _error("Vehicle service not initialized.", 500)

            if not _vehicle_service.remove_vehicle(vehicle_id):
                return _error(f"Vehicle '{vehicle_id}' not found.", 404)

            _sse_broadcast("vehicle_removed", {"vehicle_id": vehicle_id})
            return _ok({"message": f"Vehicle '{vehicle_id}' removed."})
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/vehicles/<vehicle_id>/speed", methods=["PUT"])
    def api_smart_vehicles_speed(vehicle_id):
        """PUT /api/smart/vehicles/<id>/speed — Set vehicle speed.

        Body: {"speed_kmh": 50}
        """
        try:
            _init_all()
            data = request.get_json(silent=True) or {}
            speed = float(data.get("speed_kmh", 30))

            if not _vehicle_service:
                return _error("Vehicle service not initialized.", 500)

            vehicle = _vehicle_service.get_vehicle(vehicle_id)
            if not vehicle:
                return _error(f"Vehicle '{vehicle_id}' not found.", 404)

            _vehicle_service.set_vehicle_speed(vehicle_id, speed)
            _sse_broadcast("vehicle_updated", vehicle.to_dict())
            return _ok({"vehicle": vehicle.to_dict()})
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/vehicles/<vehicle_id>/control", methods=["PUT"])
    def api_smart_vehicles_control(vehicle_id):
        """PUT /api/smart/vehicles/<id>/control — Start or stop a vehicle.

        Body: {"action": "stop"}  // "start" or "stop"
        """
        try:
            _init_all()
            data = request.get_json(silent=True) or {}
            action = data.get("action", "stop")

            if not _vehicle_service:
                return _error("Vehicle service not initialized.", 500)

            vehicle = _vehicle_service.get_vehicle(vehicle_id)
            if not vehicle:
                return _error(f"Vehicle '{vehicle_id}' not found.", 404)

            if action == "start":
                _vehicle_service.start_vehicle(vehicle_id)
            else:
                _vehicle_service.stop_vehicle(vehicle_id)

            _sse_broadcast("vehicle_updated", vehicle.to_dict())
            return _ok({"vehicle": vehicle.to_dict(), "action": action})
        except Exception as e:
            return _error(str(e), 500)

    # ======================================================================
    # 6. REAL-TIME NAVIGATION (5 endpoints + SSE)
    # ======================================================================

    @app.route("/api/smart/navigation/start", methods=["POST"])
    def api_smart_navigation_start():
        """POST /api/smart/navigation/start — Begin real-time navigation.

        Body: {
            "planned_path": ["N001","N002",...,"N025"],
            "goal_id": "N025",
            "transport_mode": "driving",
            "scene_id": "campus"     // optional
        }
        """
        try:
            _init_all()
            data = request.get_json(silent=True) or {}
            planned_path = data.get("planned_path", [])
            goal_id = data.get("goal_id", "")
            mode_str = data.get("transport_mode", "driving")

            if len(planned_path) < 2:
                return _error("'planned_path' must have at least 2 nodes.")
            if not goal_id:
                return _error("'goal_id' is required.")

            scene_id = data.get("scene_id", _get_active_scene_id())
            graph = _map_manager.get_graph(scene_id) if _map_manager else None
            if not graph:
                return _error("No active scene.", 500)

            if mode_str not in VALID_MODES:
                return _error(f"Invalid transport mode '{mode_str}'.")
            mode = TransportMode(mode_str)

            if not _navigation_service:
                return _error("Navigation service not initialized.", 500)
            if _traffic_service and graph:
                _traffic_service.set_graph(graph)

            _navigation_service.start_navigation(
                graph=graph,
                planned_path=planned_path,
                goal_id=goal_id,
                transport_mode=mode,
                traffic_service=_traffic_service,
                on_alert=_on_navigation_alert,
            )

            progress = _navigation_service.get_progress()
            _sse_broadcast("navigation_started", {"goal_id": goal_id, "progress": progress})
            return _ok({
                "progress": progress,
                "alerts": _navigation_service.get_alerts(5),
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/navigation/update", methods=["POST"])
    def api_smart_navigation_update():
        """POST /api/smart/navigation/update — Report current position.

        Body: {
            "node_id": "N005"         // current node, or
            "x": 500, "y": 300        // current coordinates
        }
        """
        try:
            _init_all()
            if not _navigation_service or not _navigation_service.is_active:
                return _error("Navigation is not active.", 400)

            data = request.get_json(silent=True) or {}
            node_id = data.get("node_id", "")
            x = data.get("x", None)
            y = data.get("y", None)

            if node_id:
                on_path = _navigation_service.update_position(node_id)
            elif x is not None and y is not None:
                _navigation_service.update_position_xy(float(x), float(y))
                on_path = not _navigation_service.has_deviation
            else:
                return _error("Provide 'node_id' or 'x'+'y' coordinates.")

            progress = _navigation_service.get_progress()
            _sse_broadcast("navigation_update", {
                "progress": progress,
                "has_deviation": _navigation_service.has_deviation,
                "on_path": on_path,
            })

            return _ok({
                "progress": progress,
                "on_path": on_path,
                "has_deviation": _navigation_service.has_deviation,
                "deviation_node": _navigation_service.deviation_node,
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/navigation/reroute", methods=["POST"])
    def api_smart_navigation_reroute():
        """POST /api/smart/navigation/reroute — Trigger rerouting from current position."""
        try:
            _init_all()
            if not _navigation_service or not _navigation_service.is_active:
                return _error("Navigation is not active.", 400)

            result = _navigation_service.reroute()
            if result is None:
                return _error("Rerouting failed — no path found.", 500)

            _sse_broadcast("navigation_rerouted", {"new_path": result.get("path", [])})
            return _ok({
                "new_path": result.get("path", []),
                "reroute_success": True,
                "alerts": _navigation_service.get_alerts(5),
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/navigation/stop", methods=["POST"])
    def api_smart_navigation_stop():
        """POST /api/smart/navigation/stop — End navigation."""
        try:
            _init_all()
            if not _navigation_service:
                return _error("Navigation service not initialized.", 500)
            _navigation_service.stop_navigation()
            _sse_broadcast("navigation_stopped", {})
            return _ok({"message": "Navigation stopped."})
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/navigation/status", methods=["GET"])
    def api_smart_navigation_status():
        """GET /api/smart/navigation/status — Current navigation progress & alerts."""
        try:
            _init_all()
            if not _navigation_service:
                return _ok({
                    "is_active": False,
                    "progress": None,
                    "alerts": [],
                })

            return _ok({
                "is_active": _navigation_service.is_active,
                "progress": _navigation_service.get_progress() if _navigation_service.is_active else None,
                "has_deviation": _navigation_service.has_deviation,
                "alerts": _navigation_service.get_alerts(20),
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/navigation/stream", methods=["GET"])
    def api_smart_navigation_stream():
        """GET /api/smart/navigation/stream — SSE real-time event stream.

        Events emitted:
            heartbeat (every 15s)
            navigation_update — position changes
            traffic_update — congestion changes
            vehicle_update — vehicle position changes
            scene_changed — active scene switched
            alert — navigation alerts
        """
        def event_stream():
            q = _sse_subscribe()
            heartbeat_interval = 15
            last_heartbeat = time.time()

            try:
                # Send initial state
                initial = {
                    "active_scene": _get_active_scene_id(),
                    "navigation_active": _navigation_service.is_active if _navigation_service else False,
                }
                yield f"event: init\ndata: {json.dumps(initial, ensure_ascii=False)}\n\n"

                while True:
                    try:
                        msg = q.get(timeout=heartbeat_interval)
                        event = msg.get("event", "message")
                        data = msg.get("data", {})
                        yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                        last_heartbeat = time.time()
                    except queue.Empty:
                        # Send heartbeat
                        now = time.time()
                        if now - last_heartbeat >= heartbeat_interval:
                            yield f"event: heartbeat\ndata: {json.dumps({'t': int(now)})}\n\n"
                            last_heartbeat = now
            except GeneratorExit:
                pass
            finally:
                _sse_unsubscribe(q)

        return Response(
            stream_with_context(event_stream()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    # ======================================================================
    # 7. SIMULATION CONTROL (5 endpoints)
    # ======================================================================

    @app.route("/api/smart/simulation/traffic/start", methods=["POST"])
    def api_smart_simulation_traffic_start():
        """POST /api/smart/simulation/traffic/start — Start traffic simulator.

        Body: {"interval_ms": 3000}  // optional, default 3000ms
        """
        global _traffic_simulator
        try:
            _init_all()
            data = request.get_json(silent=True) or {}
            interval_ms = int(data.get("interval_ms", 3000))

            graph = _get_graph()
            if not graph:
                return _error("No active scene.", 500)

            if not _traffic_service:
                return _error("Traffic service not initialized.", 500)

            if _traffic_simulator is None:
                _traffic_simulator = TrafficSimulator(
                    graph, _traffic_service, on_update=_on_traffic_update,
                )
            else:
                _traffic_simulator.set_graph(graph)

            if _traffic_simulator.is_running():
                return _ok({"message": "Traffic simulator already running."})

            _traffic_simulator.start(interval_ms)
            return _ok({
                "message": f"Traffic simulator started (interval={interval_ms}ms).",
                "interval_ms": interval_ms,
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/simulation/traffic/stop", methods=["POST"])
    def api_smart_simulation_traffic_stop():
        """POST /api/smart/simulation/traffic/stop — Stop traffic simulator."""
        try:
            if _traffic_simulator:
                _traffic_simulator.stop()
                return _ok({"message": "Traffic simulator stopped."})
            return _ok({"message": "Traffic simulator was not running."})
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/simulation/vehicle/start", methods=["POST"])
    def api_smart_simulation_vehicle_start():
        """POST /api/smart/simulation/vehicle/start — Start vehicle simulator.

        Body: {
            "interval_ms": 100,       // optional, default 100ms
            "speed_scale": 10.0       // optional, default 10x
        }
        """
        global _vehicle_simulator
        try:
            _init_all()
            data = request.get_json(silent=True) or {}
            interval_ms = int(data.get("interval_ms", 100))
            speed_scale = float(data.get("speed_scale", 10.0))

            graph = _get_graph()
            if not graph:
                return _error("No active scene.", 500)

            if not _vehicle_service:
                return _error("Vehicle service not initialized.", 500)

            if _vehicle_simulator is None:
                _vehicle_simulator = VehicleSimulator(
                    graph, _vehicle_service, on_update=_on_vehicle_update,
                )
            else:
                _vehicle_simulator.set_graph(graph)

            _vehicle_simulator.set_speed_scale(speed_scale)

            if _vehicle_simulator.is_running():
                return _ok({"message": "Vehicle simulator already running."})

            _vehicle_simulator.start(interval_ms)
            return _ok({
                "message": f"Vehicle simulator started (interval={interval_ms}ms, scale={speed_scale}x).",
                "interval_ms": interval_ms,
                "speed_scale": speed_scale,
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/simulation/vehicle/stop", methods=["POST"])
    def api_smart_simulation_vehicle_stop():
        """POST /api/smart/simulation/vehicle/stop — Stop vehicle simulator."""
        try:
            if _vehicle_simulator:
                _vehicle_simulator.stop()
                return _ok({"message": "Vehicle simulator stopped."})
            return _ok({"message": "Vehicle simulator was not running."})
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/simulation/status", methods=["GET"])
    def api_smart_simulation_status():
        """GET /api/smart/simulation/status — Get all simulator states."""
        try:
            return _ok({
                "traffic_simulator": {
                    "running": _traffic_simulator.is_running() if _traffic_simulator else False,
                },
                "vehicle_simulator": {
                    "running": _vehicle_simulator.is_running() if _vehicle_simulator else False,
                    "speed_scale": _vehicle_simulator._speed_scale if _vehicle_simulator else 10.0,
                },
                "active_scene_id": _get_active_scene_id(),
            })
        except Exception as e:
            return _error(str(e), 500)

    # ======================================================================
    # 8. META (1 endpoint)
    # ======================================================================

    @app.route("/api/smart/meta", methods=["GET"])
    def api_smart_meta():
        """GET /api/smart/meta — All SmartNav metadata: algorithms, modes, categories, scenes."""
        try:
            _init_all()
            scenes = _map_manager.list_scenes() if _map_manager else []
            return _ok({
                "algorithms": [
                    {"id": "dijkstra", "name": "Dijkstra", "weighted": True, "description": "加权最短路径，经典算法"},
                    {"id": "a_star", "name": "A*", "weighted": True, "description": "启发式搜索，支持多距离函数",
                     "heuristics": VALID_HEURISTICS},
                    {"id": "bfs", "name": "BFS", "weighted": False, "description": "广度优先，无权图最短步数"},
                    {"id": "bidirectional_dijkstra", "name": "双向 Dijkstra", "weighted": True, "description": "两端同时搜索，加速寻路"},
                    {"id": "bidirectional_bfs", "name": "双向 BFS", "weighted": False, "description": "双向无权搜索"},
                    {"id": "congestion_avoidance", "name": "避堵路径", "weighted": True, "description": "规避拥堵路段的最优路径"},
                    {"id": "multi_criteria", "name": "多目标优化", "weighted": True, "description": "距离+时间+成本多因素权衡"},
                    {"id": "reroute", "name": "实时重路由", "weighted": True, "description": "偏离路线后自动重新规划"},
                ],
                "transport_modes": [
                    {"id": m.value, "label": str(m), "speed_kmh": {"walking": 5, "driving": 40, "bus": 30, "train": 80, "subway": 55}.get(m.value, 0)}
                    for m in TransportMode
                ],
                "poi_categories": [
                    {"id": p.value, "label": str(p)} for p in POICategory
                ],
                "congestion_levels": [
                    {"id": c.value, "label": str(c), "factor": c.factor} for c in CongestionLevel
                ],
                "scenes": [
                    _scene_to_dict(s) for s in scenes
                ],
                "active_scene_id": _get_active_scene_id(),
                "heuristics": [
                    {"id": "euclidean", "label": "欧几里得距离", "description": "直线距离估计"},
                    {"id": "manhattan", "label": "曼哈顿距离", "description": "网格距离估计"},
                    {"id": "floor_aware", "label": "楼层感知", "description": "包含垂直移动惩罚"},
                ],
            })
        except Exception as e:
            return _error(str(e), 500)

    # ======================================================================
    # 9. PATH SEARCH HISTORY (bonus)
    # ======================================================================

    @app.route("/api/smart/history", methods=["GET"])
    def api_smart_history():
        """GET /api/smart/history — Recent path search history."""
        try:
            if not _path_service:
                return _ok({"history": [], "count": 0})
            history = _path_service.get_history()
            return _ok({
                "history": [_path_result_to_dict(h) for h in history],
                "count": len(history),
            })
        except Exception as e:
            return _error(str(e), 500)

    @app.route("/api/smart/history", methods=["DELETE"])
    def api_smart_history_clear():
        """DELETE /api/smart/history — Clear path search history."""
        try:
            if _path_service:
                _path_service.clear_history()
            return _ok({"message": "History cleared."})
        except Exception as e:
            return _error(str(e), 500)

    # ======================================================================
    # 10. MAP NODE DETAIL (bonus — cross-scene node lookup)
    # ======================================================================

    @app.route("/api/smart/nodes/<scene_id>/<node_id>", methods=["GET"])
    def api_smart_node_detail(scene_id, node_id):
        """GET /api/smart/nodes/<scene>/<node> — Node detail with neighbors."""
        try:
            _init_all()
            graph = _map_manager.get_graph(scene_id) if _map_manager else None
            if not graph:
                return _error(f"Scene '{scene_id}' not found.", 404)

            node = graph.get_node(node_id)
            if not node:
                return _error(f"Node '{node_id}' not found.", 404)

            neighbors = []
            for edge in graph.get_edges(node_id):
                neighbor_node = graph.get_node(edge.to_id)
                neighbors.append({
                    "node_id": edge.to_id,
                    "name": neighbor_node.name if neighbor_node else edge.to_id,
                    "distance": round(edge.weight, 1),
                    "road_type": edge.road_type.value,
                    "congestion": str(_traffic_service.get_congestion(node_id, edge.to_id))
                        if _traffic_service else "normal",
                })

            return _ok({
                "node_id": node.node_id,
                "name": node.name,
                "type": node.node_type.value,
                "floor": node.floor,
                "x": node.x, "y": node.y,
                "poi_category": node.poi_category.value if node.poi_category else None,
                "neighbors": neighbors,
                "degree": len(neighbors),
            })
        except Exception as e:
            return _error(str(e), 500)

    # Done registering
    print(f"[routes_smart] Registered 30+ SmartNav endpoints + SSE stream.")
