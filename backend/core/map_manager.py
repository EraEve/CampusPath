"""Map Manager — loads, caches, and provides CRUD for navigation maps.

Reads JSON map files, builds NavGraph instances, and provides
a registry of available scenes for the GUI.
"""

import json
import os
from typing import Dict, List, Optional

from .nav_graph import NavGraph
from .edge import Edge
from backend.models.transport import SceneType, TransportMode, RoadType
from backend.models.map_scene import SceneMap


class MapManager:
    """Manages the lifecycle of navigation maps.

    Responsibilities:
    - Load map JSON files into NavGraph instances
    - Cache loaded graphs for performance
    - Provide scene metadata for the GUI map selector
    - Support basic CRUD: create, delete, save maps
    """

    def __init__(self) -> None:
        self._graphs: Dict[str, NavGraph] = {}
        self._scenes: Dict[str, SceneMap] = {}

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_map(self, file_path: str) -> tuple:
        """Load a map JSON file and return (NavGraph, SceneMap).

        Caches the result by scene_id for subsequent access.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        scene_data = data.get("scene", {})
        scene_id = scene_data.get("id", os.path.basename(file_path).replace(".json", ""))
        scene_type = SceneType(scene_data.get("scene_type", "outdoor_campus"))
        transport_modes = [
            TransportMode(m) for m in scene_data.get("transport_modes", ["walking"])
        ]

        scene = SceneMap(
            scene_id=scene_id,
            name=scene_data.get("name", scene_id),
            scene_type=scene_type,
            transport_modes=transport_modes,
            description=scene_data.get("description", ""),
            bounds=scene_data.get("bounds", {"min_x": 0, "min_y": 0, "max_x": 1000, "max_y": 600}),
            file_path=file_path,
        )

        graph = NavGraph()

        # Load layers (or single-layer format)
        layers = data.get("layers", [data])  # support both single and multi-layer
        for layer in layers:
            for node_data in layer.get("nodes", []):
                from backend.core.nav_node import NavNode
                node_data["scene_id"] = scene_id
                # Keep floor from node data if present; layer floor is default
                if "floor" not in node_data:
                    node_data["floor"] = layer.get("floor", 0)
                node = NavNode.from_dict(node_data)
                graph.add_node(node)

            for edge_data in layer.get("edges", []):
                edge = Edge.from_dict(edge_data)
                graph.add_edge(edge)

        # Load vertical connectors (for multi-floor maps like mall)
        for edge_data in data.get("vertical_connectors", []):
            edge = Edge.from_dict(edge_data)
            graph.add_edge(edge)

        scene.node_count = graph.total_vertices
        scene.edge_count = graph.total_edges

        self._graphs[scene_id] = graph
        self._scenes[scene_id] = scene

        return graph, scene

    def load_all_demo_maps(self) -> Dict[str, SceneMap]:
        """Load all demo maps from the data/maps directory."""
        import os
        maps_dir = os.path.join(os.path.dirname(__file__), "..", "data", "maps")
        if not os.path.isdir(maps_dir):
            return {}

        loaded = {}
        for filename in sorted(os.listdir(maps_dir)):
            if filename.endswith(".json"):
                file_path = os.path.join(maps_dir, filename)
                try:
                    graph, scene = self.load_map(file_path)
                    loaded[scene.scene_id] = scene
                except Exception as e:
                    print(f"Warning: failed to load {filename}: {e}")
        return loaded

    # ------------------------------------------------------------------
    # Access
    # ------------------------------------------------------------------

    def get_graph(self, scene_id: str) -> Optional[NavGraph]:
        """Return the cached NavGraph for a scene."""
        return self._graphs.get(scene_id)

    def get_scene(self, scene_id: str) -> Optional[SceneMap]:
        """Return scene metadata."""
        return self._scenes.get(scene_id)

    def list_scenes(self) -> List[SceneMap]:
        """Return all loaded scene metadata."""
        return list(self._scenes.values())

    def get_scenes_by_type(self, scene_type: SceneType) -> List[SceneMap]:
        """Return scenes filtered by type."""
        return [s for s in self._scenes.values() if s.scene_type == scene_type]

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_map(self, scene: SceneMap) -> NavGraph:
        """Create a new empty map and register it."""
        graph = NavGraph()
        self._graphs[scene.scene_id] = graph
        self._scenes[scene.scene_id] = scene
        return graph

    def delete_map(self, scene_id: str) -> bool:
        """Remove a map from the registry. Returns False if not found."""
        if scene_id in self._graphs:
            del self._graphs[scene_id]
            del self._scenes[scene_id]
            return True
        return False

    def save_map(self, scene_id: str, file_path: str) -> bool:
        """Save a map to a JSON file. Returns True on success."""
        graph = self._graphs.get(scene_id)
        scene = self._scenes.get(scene_id)
        if graph is None or scene is None:
            return False

        data = {
            "scene": {
                "id": scene.scene_id,
                "name": scene.name,
                "scene_type": scene.scene_type.value,
                "transport_modes": [m.value for m in scene.transport_modes],
                "description": scene.description,
                "bounds": scene.bounds,
            },
            "layers": [{
                "layer_id": "main",
                "floor": 0,
                "name": "Main",
                "nodes": [n.to_dict() for n in graph.vertices.values()],
                "edges": [e.to_dict() for e_list in graph._edges.values() for e in e_list],
            }],
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True

    def get_all_nodes_for_scene(self, scene_id: str) -> list:
        """Return all node data dicts for a scene (for GUI dropdowns)."""
        graph = self._graphs.get(scene_id)
        if graph is None:
            return []
        return [
            {"node_id": n.node_id, "name": n.name, "floor": n.floor,
             "type": n.node_type.value, "poi_category": (
                 n.poi_category.value if n.poi_category else None
             )}
            for n in graph.vertices.values()
        ]

    def __repr__(self) -> str:
        return f"MapManager(scenes={list(self._scenes.keys())})"
