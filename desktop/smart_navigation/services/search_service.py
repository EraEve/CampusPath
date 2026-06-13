"""Nearby Search Service — POI proximity search and filtering.

Finds points of interest near a given location (node or coordinates),
sorted by Euclidean distance. Supports category filtering and radius
limiting.
"""

import math
from typing import List, Optional, Tuple

from ..core.graph import NavGraph
from ..core.node import NavNode
from ..models.transport import POICategory


class SearchService:
    """Nearby POI search with proximity ordering.

    Usage:
        svc = SearchService()
        results = svc.search_nearby(graph, "N001", categories=["food", "parking"])
    """

    def __init__(self):
        self.last_results: List[dict] = []

    def search_nearby(
        self,
        graph: NavGraph,
        center_node_id: Optional[str] = None,
        center_x: float = 0.0,
        center_y: float = 0.0,
        categories: Optional[List[str]] = None,
        radius: float = float("inf"),
        max_results: int = 20,
    ) -> List[dict]:
        """Search for POIs near a center point.

        Args:
            graph: The navigation graph.
            center_node_id: Search near this node (if provided, uses its coords).
            center_x, center_y: Search near these coordinates (used if no node_id).
            categories: Filter by POI categories ["scenic", "food", "parking", "hospital"].
            radius: Maximum search radius in coordinate units (default: unlimited).
            max_results: Maximum number of results to return.

        Returns:
            List of dicts: [{node_id, name, category, distance, x, y, description}, ...]
        """
        # Determine center
        if center_node_id:
            center_node = graph.get_node(center_node_id)
            if center_node is None:
                return []
            cx, cy = center_node.x, center_node.y
        else:
            cx, cy = center_x, center_y

        # Parse category filters
        category_set = None
        if categories:
            category_set = set()
            for c in categories:
                try:
                    category_set.add(POICategory(c))
                except ValueError:
                    pass

        # Search all POI nodes
        results = []
        for node in graph.get_poi_nodes():
            # Filter by category
            if category_set and node.poi_category not in category_set:
                continue

            # Compute distance
            dx = node.x - cx
            dy = node.y - cy
            dist = math.sqrt(dx * dx + dy * dy)

            # Filter by radius
            if dist > radius:
                continue

            # Direction (cardinal)
            direction = self._compute_direction(cx, cy, node.x, node.y)

            results.append({
                "node_id": node.node_id,
                "name": node.name,
                "category": node.poi_category.value if node.poi_category else "unknown",
                "category_label": str(node.poi_category) if node.poi_category else "",
                "distance": round(dist, 1),
                "x": node.x,
                "y": node.y,
                "direction": direction,
                "description": node.metadata.get("description", ""),
                "floor": node.floor,
            })

        # Sort by distance
        results.sort(key=lambda r: r["distance"])

        # Limit
        results = results[:max_results]
        self.last_results = results
        return results

    def search_by_category(
        self,
        graph: NavGraph,
        category: str,
        center_node_id: Optional[str] = None,
        center_x: float = 0.0,
        center_y: float = 0.0,
        radius: float = float("inf"),
    ) -> List[dict]:
        """Convenience: search for a single category."""
        return self.search_nearby(
            graph, center_node_id, center_x, center_y,
            categories=[category], radius=radius,
        )

    def get_poi_categories(self, graph: NavGraph) -> List[dict]:
        """Return summary of available POI categories with counts."""
        counts = {}
        for node in graph.get_poi_nodes():
            if node.poi_category:
                cat = node.poi_category.value
                counts[cat] = counts.get(cat, 0) + 1

        return [
            {"category": cat, "label": str(POICategory(cat)), "count": count}
            for cat, count in sorted(counts.items())
        ]

    def _compute_direction(self, cx: float, cy: float,
                           px: float, py: float) -> str:
        """Compute cardinal direction from center to point."""
        dx = px - cx
        dy = py - cy

        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return "原地"

        angle = math.degrees(math.atan2(-dy, dx))  # -dy because y increases downward
        angle = (angle + 360) % 360

        directions = [
            (0, "东"), (45, "东北"), (90, "北"), (135, "西北"),
            (180, "西"), (225, "西南"), (270, "南"), (315, "东南"),
            (360, "东"),
        ]
        for deg, name in directions:
            if angle <= deg + 22.5:
                return name
        return "东"

    def get_last_results(self) -> List[dict]:
        """Return the most recent search results."""
        return self.last_results
