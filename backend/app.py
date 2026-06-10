"""CampusPath Flask API Server.

Provides 7 REST endpoints for the campus indoor navigation system:
- Building metadata
- Floor layouts (for Canvas rendering)
- Single-path finding (any algorithm)
- Multi-algorithm comparison
- Batch experiment execution
- Algorithm step data (for animation)

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

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder="../frontend", static_url_path="")
CORS(app)

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
    return send_from_directory(app.static_folder, "index.html")


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
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"\n{'='*60}")
    print(f"  CampusPath API Server")
    print(f"  Building: {building.name}")
    print(f"  Nodes: {building.graph.total_vertices}")
    print(f"  Edges: {building.graph.total_edges}")
    print(f"  Floors: {building.floors}")
    print(f"  URL: http://localhost:5001")
    print(f"  Frontend: http://localhost:5001/index.html")
    print(f"{'='*60}\n")
    app.run(debug=True, host="0.0.0.0", port=5001)
