"""CampusPath + SmartNav Flask API Server.

Provides 57 REST endpoints + SSE stream across two route modules:

Core campus indoor navigation (app.py — 22 endpoints):
- Building metadata, floor layouts, node listings
- Single-path finding (any algorithm), algorithm comparison, batch benchmarking
- Algorithm step data (for animation), turn-by-turn directions
- Room search & detail, graph statistics & validation
- Accessible (wheelchair) routing with elevator wait simulation
- Recent search history, metadata

Smart Navigation (routes_smart.py — 35 endpoints + SSE + health):
- Map/Scene management, POI search, traffic & congestion
- Vehicle tracking, real-time navigation with SSE stream
- Simulation control (traffic + vehicle), history, cross-scene node detail

Usage:
    python backend/app.py
    → http://localhost:5001
"""

import json
import os
import sys

# Ensure backend package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from backend.models.building import Building
from backend.algorithms.a_star import HEURISTICS
from backend.routes_smart import register_smart_routes

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)

# Register Smart Navigation routes (Phase 3: 30+ REST endpoints + SSE)
register_smart_routes(app)

# Load the campus building map
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
BUILDING_JSON = os.path.join(DATA_DIR, "campus_building.json")
SCENARIOS_JSON = os.path.join(DATA_DIR, "test_scenarios.json")

building = Building(BUILDING_JSON)

VALID_ALGORITHMS = [
    "dijkstra",
    "a_star",
    "bfs",
    "bidirectional_bfs",
    "bidirectional_dijkstra",
]


# ---------------------------------------------------------------------------
# Static file serving (SPA)
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """Serve the main SPA page."""
    return send_from_directory(app.static_folder, "app.html")


@app.route("/<path:path>")
def static_files(path):
    """Serve all static assets (CSS, JS)."""
    return send_from_directory(app.static_folder, path)


# ---------------------------------------------------------------------------
# API: Building information
# ---------------------------------------------------------------------------

@app.route("/api/building", methods=["GET"])
def api_building_info():
    """GET /api/building — Building metadata."""
    try:
        info = building.get_building_info()
        return jsonify({"success": True, "data": info})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/building/floor/<int:floor_num>", methods=["GET"])
def api_floor_layout(floor_num):
    """GET /api/building/floor/<n> — Single-floor layout for Canvas rendering."""
    try:
        if floor_num not in building.floors:
            return jsonify({
                "success": False,
                "message": f"Floor {floor_num} not found. Valid: {building.floors}"
            }), 404

        layout = building.get_floor_layout(floor_num)
        return jsonify({"success": True, "data": layout})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/building/all-nodes", methods=["GET"])
def api_all_nodes():
    """GET /api/building/all-nodes — All nodes for dropdown selectors."""
    try:
        nodes = building.get_all_node_labels()
        return jsonify({"success": True, "data": {"nodes": nodes}})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Pathfinding
# ---------------------------------------------------------------------------

@app.route("/api/path", methods=["POST"])
def api_find_path():
    """POST /api/path — Find a single path.

    Request body:
        {
            "start": "F1-R101",
            "goal": "F4-CONF1",
            "algorithm": "dijkstra",       // default: "dijkstra"
            "heuristic": "euclidean",       // only for a_star
            "record_steps": false           // set true for animation data
        }
    """
    try:
        data = request.get_json(silent=True) or {}
        start = data.get("start", "")
        goal = data.get("goal", "")
        algorithm = data.get("algorithm", "dijkstra")
        heuristic = data.get("heuristic", "euclidean")
        record_steps = data.get("record_steps", False)

        # Validate
        if not start or not goal:
            return jsonify({
                "success": False,
                "message": "Both 'start' and 'goal' are required."
            }), 400

        if algorithm not in VALID_ALGORITHMS:
            return jsonify({
                "success": False,
                "message": f"Unknown algorithm '{algorithm}'. "
                           f"Valid: {VALID_ALGORITHMS}"
            }), 400

        if not building.graph.has_node(start):
            return jsonify({
                "success": False,
                "message": f"Start node '{start}' not found."
            }), 404

        if not building.graph.has_node(goal):
            return jsonify({
                "success": False,
                "message": f"Goal node '{goal}' not found."
            }), 404

        result = building.find_path(
            start, goal,
            algorithm=algorithm,
            heuristic=heuristic,
            record_steps=record_steps,
        )

        # Strip steps if not requested (reduce response size)
        if not record_steps:
            result.pop("steps", None)

        return jsonify({"success": True, "data": result})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Algorithm comparison
# ---------------------------------------------------------------------------

@app.route("/api/compare", methods=["POST"])
def api_compare_algorithms():
    """POST /api/compare — Compare all algorithms on one (start, goal) pair.

    Request body: {"start": "F1-R101", "goal": "F4-CONF1"}
    """
    try:
        data = request.get_json(silent=True) or {}
        start = data.get("start", "")
        goal = data.get("goal", "")

        if not start or not goal:
            return jsonify({
                "success": False,
                "message": "Both 'start' and 'goal' are required."
            }), 400

        if not building.graph.has_node(start):
            return jsonify({
                "success": False,
                "message": f"Start node '{start}' not found."
            }), 404

        if not building.graph.has_node(goal):
            return jsonify({
                "success": False,
                "message": f"Goal node '{goal}' not found."
            }), 404

        comparison = building.compare_algorithms(start, goal)

        # Strip steps from individual results to keep response lean
        for algo_name, result in comparison["results"].items():
            if isinstance(result, dict):
                result.pop("steps", None)

        return jsonify({"success": True, "data": comparison})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/batch-compare", methods=["POST"])
def api_batch_compare():
    """POST /api/batch-compare — Run batch comparison on predefined scenarios.

    Request body (optional):
        {
            "same_floor": true,     // if true, filter to same-floor scenarios
            "custom_scenarios": []  // optional custom list of {start, goal, label}
        }
    """
    try:
        data = request.get_json(silent=True) or {}
        same_floor = data.get("same_floor", False)
        custom = data.get("custom_scenarios", None)

        if custom:
            scenarios = custom
        else:
            # Load predefined scenarios
            with open(SCENARIOS_JSON, "r", encoding="utf-8") as f:
                all_scenarios = json.load(f)["scenarios"]

            if same_floor:
                scenarios = [
                    s for s in all_scenarios
                    if s["category"].startswith("same_floor")
                ]
            else:
                scenarios = all_scenarios

        batch_result = building.batch_compare(scenarios)

        # Strip verbose step data
        for scenario in batch_result["scenarios"]:
            for algo_name, result in scenario["comparison"].get("results", {}).items():
                if isinstance(result, dict):
                    result.pop("steps", None)

        return jsonify({"success": True, "data": batch_result})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Algorithm steps (for animation)
# ---------------------------------------------------------------------------

@app.route("/api/algorithm-steps/<algorithm>", methods=["GET"])
def api_algorithm_steps(algorithm):
    """GET /api/algorithm-steps/<algo>?start=X&goal=Y&heuristic=Z

    Returns step-by-step search data for frontend animation.
    """
    try:
        start = request.args.get("start", "")
        goal = request.args.get("goal", "")
        heuristic = request.args.get("heuristic", "euclidean")

        if not start or not goal:
            return jsonify({
                "success": False,
                "message": "Query params 'start' and 'goal' are required."
            }), 400

        if algorithm not in VALID_ALGORITHMS:
            return jsonify({
                "success": False,
                "message": f"Unknown algorithm '{algorithm}'."
            }), 400

        result = building.find_path(
            start, goal,
            algorithm=algorithm,
            heuristic=heuristic,
        )

        result_with_steps = building.find_path(
            start, goal,
            algorithm=algorithm,
            heuristic=heuristic,
            record_steps=True,
        )

        return jsonify({
            "success": True,
            "data": {
                "path": result_with_steps["path"],
                "total_distance": result_with_steps["total_distance"],
                "nodes_visited": result_with_steps["nodes_visited"],
                "execution_time_ms": result_with_steps["execution_time_ms"],
                "steps": result_with_steps["steps"],
            }
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Available algorithms and heuristics (metadata)
# ---------------------------------------------------------------------------

@app.route("/api/meta/algorithms", methods=["GET"])
def api_meta_algorithms():
    """GET /api/meta/algorithms — List available algorithms."""
    return jsonify({
        "success": True,
        "data": {
            "algorithms": [
                {"id": "dijkstra", "name": "Dijkstra", "weighted": True},
                {"id": "a_star", "name": "A*", "weighted": True, "heuristics": list(HEURISTICS.keys())},
                {"id": "bfs", "name": "BFS", "weighted": False},
                {"id": "bidirectional_bfs", "name": "Bidirectional BFS", "weighted": False},
                {"id": "bidirectional_dijkstra", "name": "Bidirectional Dijkstra", "weighted": True},
            ],
            "heuristics": {
                "euclidean": "欧几里得距离 — 直线距离估计",
                "manhattan": "曼哈顿距离 — 网格距离估计",
                "floor_aware": "楼层感知 — 包含垂直移动惩罚",
            }
        }
    })


# ---------------------------------------------------------------------------
# API: Turn-by-turn directions
# ---------------------------------------------------------------------------

@app.route("/api/directions", methods=["POST"])
def api_directions():
    """POST /api/directions — Convert a path node list to turn-by-turn text.

    Request body:
        {
            "path": ["F1-R101", "F1-COR-01-SEG0", ..., "F4-CONF1"]
        }
    """
    try:
        data = request.get_json(silent=True) or {}
        path = data.get("path", [])

        if not path or len(path) < 2:
            return jsonify({
                "success": False,
                "message": "Path must contain at least 2 nodes."
            }), 400

        directions = building.generate_directions(path)
        return jsonify({"success": True, "data": {"directions": directions}})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Accessible (wheelchair) pathfinding
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# API: Room search
# ---------------------------------------------------------------------------

@app.route("/api/rooms/search", methods=["GET"])
def api_room_search():
    """GET /api/rooms/search?q=R101&floor=1&type=room

    Fuzzy search rooms by name, floor, and/or type.
    All query params are optional — omit to list all rooms.
    """
    try:
        query = request.args.get("q", "").lower()
        floor_str = request.args.get("floor", "")
        type_str = request.args.get("type", "").lower()

        all_nodes = building.get_all_node_labels()
        results = []

        for node in all_nodes:
            # Filter by floor
            if floor_str and str(node["floor"]) != floor_str:
                continue
            # Filter by type
            if type_str and node["type"] != type_str:
                continue
            # Filter by name/id (fuzzy)
            if query:
                name_lower = node["name"].lower()
                id_lower = node["node_id"].lower()
                if query not in name_lower and query not in id_lower:
                    continue
            results.append(node)

        return jsonify({
            "success": True,
            "count": len(results),
            "data": {"rooms": results},
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Graph statistics
# ---------------------------------------------------------------------------

@app.route("/api/building/stats", methods=["GET"])
def api_building_stats():
    """GET /api/building/stats — Comprehensive graph statistics."""
    try:
        stats = building.get_graph_stats()
        return jsonify({"success": True, "data": stats})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Building validation
# ---------------------------------------------------------------------------

@app.route("/api/building/validate", methods=["GET"])
def api_building_validate():
    """GET /api/building/validate — Validate map integrity."""
    try:
        issues = building.validate()
        return jsonify({
            "success": True,
            "data": {
                "valid": len(issues) == 0,
                "issue_count": len(issues),
                "issues": issues,
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Recent searches (server-side cache)
# ---------------------------------------------------------------------------

_recent_searches: list = []  # in-memory cache, max 10 entries
_MAX_RECENT = 10


@app.route("/api/recent", methods=["GET"])
def api_recent_get():
    """GET /api/recent — List recent searches."""
    return jsonify({
        "success": True,
        "count": len(_recent_searches),
        "data": {"recent": _recent_searches},
    })


@app.route("/api/recent", methods=["POST"])
def api_recent_add():
    """POST /api/recent — Add a search to recent history.

    Request body: {"start": "F1-R101", "goal": "F4-CONF1", "algorithm": "dijkstra"}
    """
    try:
        data = request.get_json(silent=True) or {}
        entry = {
            "start": data.get("start", "?"),
            "goal": data.get("goal", "?"),
            "algorithm": data.get("algorithm", "dijkstra"),
        }
        # Deduplicate: remove existing identical entry
        global _recent_searches
        _recent_searches = [
            r for r in _recent_searches
            if not (r["start"] == entry["start"] and r["goal"] == entry["goal"])
        ]
        _recent_searches.insert(0, entry)
        _recent_searches = _recent_searches[:_MAX_RECENT]

        return jsonify({
            "success": True,
            "count": len(_recent_searches),
            "data": {"recent": _recent_searches},
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Room detail (capacity, purpose, adjacent rooms)
# ---------------------------------------------------------------------------

# Room metadata: generated capacity & purpose data for each room type
_ROOM_META = {
    # 1F
    "F1-ENTRANCE": {"capacity": 200, "purpose": "主入口，人员进出通道", "features": ["门禁系统", "信息屏", "轮椅坡道"]},
    "F1-LOBBY": {"capacity": 80, "purpose": "大厅接待与等候区", "features": ["服务台", "休息座椅", "校园地图"]},
    "F1-R101": {"capacity": 120, "purpose": "大型阶梯教室，用于公共课与讲座", "features": ["投影仪", "扩音系统", "无障碍座位"]},
    "F1-R102": {"capacity": 120, "purpose": "大型阶梯教室，用于公共课与讲座", "features": ["投影仪", "扩音系统"]},
    "F1-R103": {"capacity": 60, "purpose": "标准教室，用于小班教学", "features": ["白板", "多媒体讲台"]},
    "F1-R104": {"capacity": 60, "purpose": "标准教室，用于小班教学", "features": ["白板", "多媒体讲台"]},
    "F1-CANTEEN": {"capacity": 200, "purpose": "学生食堂，提供早中晚三餐", "features": ["自助取餐", "微波炉", "饮水机"]},
    "F1-RESTROOM-W": {"capacity": 10, "purpose": "西侧公共卫生间", "features": ["无障碍厕位", "母婴室"]},
    "F1-RESTROOM-E": {"capacity": 10, "purpose": "东侧公共卫生间", "features": ["无障碍厕位"]},
    "F1-OFFICE": {"capacity": 4, "purpose": "安保办公室，校园安全管理", "features": ["监控屏幕", "对讲系统"]},
    # 2F
    "F2-R201": {"capacity": 80, "purpose": "多媒体教室，配备电脑与投影设备", "features": ["电脑终端", "投影仪", "空调"]},
    "F2-R202": {"capacity": 80, "purpose": "多媒体教室，配备电脑与投影设备", "features": ["电脑终端", "投影仪", "空调"]},
    "F2-R203": {"capacity": 40, "purpose": "学生自习室，安静学习空间", "features": ["独立座位", "台灯", "充电插座"]},
    "F2-R204": {"capacity": 40, "purpose": "学生自习室，安静学习空间", "features": ["独立座位", "台灯", "充电插座"]},
    "F2-OFF201": {"capacity": 6, "purpose": "教师办公室（西区），教师日常工作与备课", "features": ["办公桌", "打印机", "书柜"]},
    "F2-OFF202": {"capacity": 6, "purpose": "教师办公室（东区），教师日常工作与备课", "features": ["办公桌", "打印机", "书柜"]},
    "F2-COMPLAB1": {"capacity": 50, "purpose": "计算机实验室A，编程与实验课程", "features": ["50台工作站", "千兆网络", "教学广播系统"]},
    "F2-COMPLAB2": {"capacity": 50, "purpose": "计算机实验室B，编程与实验课程", "features": ["50台工作站", "千兆网络", "教学广播系统"]},
    "F2-LOUNGE": {"capacity": 30, "purpose": "学生休息区，课间放松与社交", "features": ["沙发", "自动售货机", "饮水机"]},
    "F2-RESTROOM-W": {"capacity": 8, "purpose": "西侧公共卫生间", "features": ["无障碍厕位"]},
    "F2-RESTROOM-E": {"capacity": 8, "purpose": "东侧公共卫生间", "features": ["无障碍厕位"]},
    # 3F
    "F3-R301": {"capacity": 40, "purpose": "综合实验室，多学科实验教学", "features": ["实验台", "通风橱", "安全洗眼器"]},
    "F3-R302": {"capacity": 40, "purpose": "综合实验室，多学科实验教学", "features": ["实验台", "通风橱", "安全洗眼器"]},
    "F3-R303": {"capacity": 20, "purpose": "研讨室，小组讨论与学术交流", "features": ["圆桌", "白板墙", "视频会议设备"]},
    "F3-R304": {"capacity": 20, "purpose": "研讨室，小组讨论与学术交流", "features": ["圆桌", "白板墙", "视频会议设备"]},
    "F3-RESEARCH1": {"capacity": 15, "purpose": "AI研究实验室，机器学习与深度学习研究", "features": ["GPU服务器", "深度学习工作站", "大屏显示器"]},
    "F3-RESEARCH2": {"capacity": 15, "purpose": "大数据实验室，数据挖掘与分布式计算", "features": ["Hadoop集群", "Spark环境", "数据可视化大屏"]},
    "F3-RESEARCH3": {"capacity": 12, "purpose": "网络安全实验室，渗透测试与防御研究", "features": ["隔离网络", "攻防演练平台", "密码学设备"]},
    "F3-SEMINAR": {"capacity": 12, "purpose": "学术研讨室，学术报告与论文答辩", "features": ["投影仪", "视频会议", "录音设备"]},
    "F3-RESTROOM-W": {"capacity": 8, "purpose": "西侧公共卫生间", "features": ["无障碍厕位"]},
    "F3-RESTROOM-E": {"capacity": 8, "purpose": "东侧公共卫生间", "features": ["无障碍厕位"]},
    # 4F
    "F4-CONF1": {"capacity": 200, "purpose": "大报告厅，学术报告与大型会议", "features": ["舞台灯光", "音响系统", "同声传译", "直播设备"]},
    "F4-CONF2": {"capacity": 200, "purpose": "大报告厅，学术报告与大型会议", "features": ["舞台灯光", "音响系统", "同声传译", "直播设备"]},
    "F4-MEET1": {"capacity": 30, "purpose": "中型会议室，院系会议与接待", "features": ["视频会议", "投影仪", "茶水间"]},
    "F4-MEET2": {"capacity": 30, "purpose": "中型会议室，院系会议与接待", "features": ["视频会议", "投影仪", "茶水间"]},
    "F4-LIBRARY": {"capacity": 60, "purpose": "图书资料室，专业书籍与期刊阅览", "features": ["书架区", "阅览座位", "电子检索终端"]},
    "F4-ROOFTOP": {"capacity": 50, "purpose": "天台入口，户外休息与观景平台", "features": ["遮阳棚", "绿植", "长椅"]},
    "F4-LOUNGE": {"capacity": 20, "purpose": "教师休息室，课间休息与备课", "features": ["沙发", "咖啡机", "报刊架"]},
    "F4-RESTROOM-W": {"capacity": 8, "purpose": "西侧公共卫生间", "features": ["无障碍厕位"]},
    "F4-RESTROOM-E": {"capacity": 8, "purpose": "东侧公共卫生间", "features": ["无障碍厕位"]},
}


def _get_room_meta(room_id: str) -> dict:
    """Get room metadata; generate defaults for corridor/stair/elevator nodes."""
    if room_id in _ROOM_META:
        return dict(_ROOM_META[room_id])
    # Generate defaults for structural nodes
    if "COR" in room_id:
        return {"capacity": 0, "purpose": "走廊通道，用于连接各房间", "features": []}
    if "STAIR" in room_id:
        return {"capacity": 0, "purpose": "楼梯间，楼层间垂直通道（非无障碍）", "features": ["扶手", "应急照明"]}
    if "ELEV" in room_id:
        return {"capacity": 15, "purpose": "电梯，无障碍垂直交通（轮椅可通行）", "features": ["无障碍按钮", "语音播报", "应急电话"]}
    return {"capacity": 0, "purpose": "建筑物节点", "features": []}


def _get_adjacent_rooms(room_id: str) -> list:
    """Return list of adjacent room info for a given node."""
    adj = []
    for neighbor_id, weight in building.graph.get_neighbors(room_id):
        node = building.graph.vertices.get(neighbor_id)
        if node:
            adj.append({
                "node_id": neighbor_id,
                "name": node.name,
                "type": node.node_type.value,
                "floor": node.floor,
                "distance_m": round(weight, 1),
            })
    # Sort by floor then name
    adj.sort(key=lambda x: (x["floor"], x["name"]))
    return adj


@app.route("/api/room/<room_id>", methods=["GET"])
def api_room_detail(room_id):
    """GET /api/room/<room_id> — Room detail with capacity, purpose, adjacent rooms."""
    try:
        node = building.graph.vertices.get(room_id)
        if not node:
            return jsonify({
                "success": False,
                "message": f"Room '{room_id}' not found."
            }), 404

        meta = _get_room_meta(room_id)
        adjacent = _get_adjacent_rooms(room_id)

        return jsonify({
            "success": True,
            "data": {
                "node_id": room_id,
                "name": node.name,
                "type": node.node_type.value,
                "floor": node.floor,
                "x": node.x,
                "y": node.y,
                "capacity": meta["capacity"],
                "purpose": meta["purpose"],
                "features": meta.get("features", []),
                "adjacent_rooms": adjacent,
                "degree": len(adjacent),
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Degree distribution histogram data
# ---------------------------------------------------------------------------

@app.route("/api/building/degree-distribution", methods=["GET"])
def api_degree_distribution():
    """GET /api/building/degree-distribution — Degree histogram + isolated nodes."""
    try:
        from collections import Counter

        degrees = []
        isolated = []
        for nid in building.graph:
            node = building.graph.vertices.get(nid)
            deg = len(building.graph.get_neighbors(nid))
            degrees.append(deg)
            if deg == 0:
                isolated.append({
                    "node_id": nid,
                    "name": node.name if node else nid,
                    "type": node.node_type.value if node else "unknown",
                    "floor": node.floor if node else 0,
                })

        # Build histogram buckets
        counter = Counter(degrees)
        max_deg = max(degrees) if degrees else 0
        histogram = []
        for d in range(max_deg + 1):
            histogram.append({
                "degree": d,
                "count": counter.get(d, 0),
                "label": f"度={d}",
            })

        return jsonify({
            "success": True,
            "data": {
                "histogram": histogram,
                "isolated_nodes": isolated,
                "isolated_count": len(isolated),
                "total_nodes": len(degrees),
                "avg_degree": round(sum(degrees) / len(degrees), 2) if degrees else 0,
                "max_degree": max_deg,
                "min_degree": min(degrees) if degrees else 0,
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Isolated nodes detail
# ---------------------------------------------------------------------------

@app.route("/api/building/isolated-nodes", methods=["GET"])
def api_isolated_nodes():
    """GET /api/building/isolated-nodes — List all isolated (disconnected) nodes."""
    try:
        isolated = []
        for nid in building.graph:
            node = building.graph.vertices.get(nid)
            deg = len(building.graph.get_neighbors(nid))
            if deg == 0:
                isolated.append({
                    "node_id": nid,
                    "name": node.name if node else nid,
                    "type": node.node_type.value if node else "unknown",
                    "floor": node.floor if node else 0,
                    "x": node.x if node else 0,
                    "y": node.y if node else 0,
                })

        return jsonify({
            "success": True,
            "data": {
                "isolated_nodes": isolated,
                "count": len(isolated),
                "healthy": len(isolated) == 0,
            }
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Batch benchmark with aggregate chart data
# ---------------------------------------------------------------------------

@app.route("/api/batch-benchmark", methods=["POST"])
def api_batch_benchmark():
    """POST /api/batch-benchmark — Run all 10 scenarios, return Chart.js-ready data.

    Returns per-scenario results + aggregate metrics for summary charts.
    """
    try:
        data = request.get_json(silent=True) or {}
        scenario_ids = data.get("scenario_ids", None)  # None = all

        with open(SCENARIOS_JSON, "r", encoding="utf-8") as f:
            all_scenarios = json.load(f)["scenarios"]

        if scenario_ids:
            scenarios = [s for s in all_scenarios if s["id"] in scenario_ids]
        else:
            scenarios = all_scenarios

        batch_result = building.batch_compare(scenarios)

        # Build Chart.js-ready aggregate data
        algo_labels = [
            "bfs", "dijkstra", "a_star_euclidean", "a_star_manhattan",
            "a_star_floor_aware", "bidirectional_bfs", "bidirectional_dijkstra",
        ]
        algo_display = [
            "BFS", "Dijkstra", "A* Euclid", "A* Manhattan",
            "A* Floor", "Bi-BFS", "Bi-Dijkstra",
        ]

        agg = batch_result["aggregate"]

        chart_data = {
            "labels": algo_display,
            "datasets": {
                "avg_distance": [agg["avg_distance_m"].get(a, 0) for a in algo_labels],
                "avg_nodes": [agg["avg_nodes_visited"].get(a, 0) for a in algo_labels],
                "avg_time": [agg["avg_time_ms"].get(a, 0) for a in algo_labels],
            },
            "optimality": {
                k.replace("_", " "): v
                for k, v in agg.get("optimality_rate_vs_dijkstra", {}).items()
            },
            "scenario_count": len(scenarios),
            "scenario_labels": [s["label"] for s in scenarios],
        }

        # Strip verbose step data
        for scenario in batch_result["scenarios"]:
            for algo_name, result in scenario["comparison"].get("results", {}).items():
                if isinstance(result, dict):
                    result.pop("steps", None)

        return jsonify({
            "success": True,
            "data": {
                "scenarios": batch_result["scenarios"],
                "aggregate": batch_result["aggregate"],
                "chart_data": chart_data,
            }
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# API: Elevator wait time simulation
# ---------------------------------------------------------------------------

@app.route("/api/accessible-path", methods=["POST"])
def api_accessible_path():
    """POST /api/accessible-path — Wheelchair-accessible routing (no stairs).

    Request body:
        {
            "start": "F1-R101",
            "goal": "F4-CONF1",
            "heuristic": "floor_aware",     // optional, default: floor_aware
            "elevator_wait_time_s": 30      // optional, default: 0
        }
    """
    try:
        data = request.get_json(silent=True) or {}
        start = data.get("start", "")
        goal = data.get("goal", "")
        heuristic = data.get("heuristic", "floor_aware")
        elevator_wait = float(data.get("elevator_wait_time_s", 0))

        if not start or not goal:
            return jsonify({
                "success": False,
                "message": "Both 'start' and 'goal' are required."
            }), 400

        if not building.graph.has_node(start):
            return jsonify({
                "success": False,
                "message": f"Start node '{start}' not found."
            }), 404

        if not building.graph.has_node(goal):
            return jsonify({
                "success": False,
                "message": f"Goal node '{goal}' not found."
            }), 404

        # If elevator wait time > 0, temporarily increase elevator edge weights
        saved_weights = {}
        if elevator_wait > 0:
            # Convert wait time to equivalent walking distance (~1.4 m/s walking speed)
            wait_penalty = elevator_wait * 1.4
            for nid, node in building.graph.vertices.items():
                if node.node_type.value == "elevator":
                    for i, (neighbor, w) in enumerate(building.graph.adjacency.get(nid, [])):
                        key = (nid, neighbor)
                        if key not in saved_weights:
                            saved_weights[key] = w
                            building.graph.adjacency[nid][i] = (neighbor, w + wait_penalty)

        try:
            result = building.find_accessible_path(start, goal, heuristic=heuristic)
        finally:
            # Restore original elevator weights
            for (nid, neighbor), orig_w in saved_weights.items():
                for i, (n, w) in enumerate(building.graph.adjacency.get(nid, [])):
                    if n == neighbor:
                        building.graph.adjacency[nid][i] = (neighbor, orig_w)
                        break

        # Add elevator wait info to result
        result["elevator_wait_time_s"] = elevator_wait
        if elevator_wait > 0 and result["total_distance"] < float("inf"):
            # Estimate total time: walking (1.4 m/s) + elevator waits
            elevator_count = sum(
                1 for nid in result.get("path", [])
                if "ELEV" in nid
            )
            # Count elevator transitions (pairs of adjacent elevator nodes on different floors)
            path = result.get("path", [])
            elevator_transitions = 0
            for i in range(len(path) - 1):
                a_node = building.graph.vertices.get(path[i])
                b_node = building.graph.vertices.get(path[i + 1])
                if a_node and b_node:
                    if (a_node.node_type.value == "elevator"
                            and b_node.node_type.value == "elevator"
                            and a_node.floor != b_node.floor):
                        elevator_transitions += 1
            result["elevator_rides"] = elevator_transitions
            result["estimated_total_time_s"] = round(
                result["total_distance"] / 1.4 + elevator_transitions * elevator_wait, 1
            )

        return jsonify({"success": True, "data": result})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import webbrowser
    import threading

    print(f"\n{'='*60}")
    print(f"  CampusPath + SmartNav API Server")
    print(f"  Building: {building.name}")
    print(f"  Nodes: {building.graph.total_vertices}")
    print(f"  Edges: {building.graph.total_edges}")
    print(f"  Floors: {building.floors}")
    print(f"  URL: http://localhost:5001")
    print(f"  Frontend: http://localhost:5001/app.html")
    print(f"  SmartNav APIs: /api/smart/* (30+ endpoints + SSE)")
    print(f"{'='*60}\n")

    def _open_browser():
        """Open browser after a short delay to let Flask start."""
        import time
        time.sleep(1.2)
        webbrowser.open("http://localhost:5001")

    threading.Thread(target=_open_browser, daemon=True).start()
    app.run(debug=True, host="0.0.0.0", port=5001)
