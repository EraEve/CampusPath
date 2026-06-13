"""Map Canvas — tkinter Canvas wrapper with zoom, pan, and rendering.

Renders the navigation graph on a tkinter Canvas:
- Nodes as colored shapes (circle, diamond, rectangle per type)
- Edges as colored lines (by road type)
- Found paths as highlighted lines
- Vehicles as moving dots
- POI labels with emoji
- Zoom (mouse wheel) and pan (click-drag)
"""

import math
import tkinter as tk
from tkinter import font as tkfont
from typing import Dict, List, Optional, Set, Tuple

from ..core.graph import NavGraph
from ..core.node import NavNode
from ..core.edge import Edge
from ..models.vehicle import Vehicle
from ..models.traffic import CongestionLevel
from .styles import (
    ROAD_COLORS, ROAD_WIDTHS, ROAD_DASH,
    NODE_COLORS, NODE_RADIUS,
    POI_EMOJI, POI_COLORS,
    PATH_COLOR, PATH_WIDTH,
    START_COLOR, GOAL_COLOR,
    CANVAS_BG, CONGESTION_COLORS,
)


class MapCanvas(tk.Canvas):
    """Interactive map renderer with zoom and pan.

    Usage:
        canvas = MapCanvas(parent, width=800, height=600)
        canvas.set_graph(graph)
        canvas.render()
        canvas.show_path(path_list)
    """

    def __init__(self, parent, width=800, height=600, **kwargs):
        super().__init__(parent, width=width, height=height,
                        bg=CANVAS_BG, highlightthickness=0, **kwargs)
        self._graph: Optional[NavGraph] = None

        # Viewport transform
        self._scale = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._drag_start_x = 0
        self._drag_start_y = 0

        # State
        self._show_node_labels = True
        self._show_edge_labels = False
        self._show_poi_icons = True
        self._highlight_path: List[str] = []
        self._start_node: Optional[str] = None
        self._goal_node: Optional[str] = None
        self._waypoint_nodes: List[str] = []
        self._vehicles: List[Vehicle] = []
        self._congestion_map: Dict[Tuple[str, str], str] = {}  # edge_key → level
        self._selected_node: Optional[str] = None
        self._on_node_click = None  # callback(node_id)

        # Cached canvas IDs for efficient updates
        self._node_items: Dict[str, int] = {}
        self._edge_items: Dict[Tuple[str, str], int] = {}
        self._label_items: Dict[str, int] = {}
        self._path_items: List[int] = []
        self._vehicle_items: Dict[str, int] = {}
        self._poi_text_items: Dict[str, int] = {}

        # Bind events
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Button-4>", self._on_mousewheel)      # Linux scroll up
        self.bind("<Button-5>", self._on_mousewheel)      # Linux scroll down
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._on_resize)

    # ------------------------------------------------------------------
    # Graph management
    # ------------------------------------------------------------------

    def set_graph(self, graph: NavGraph):
        """Set the graph to render."""
        self._graph = graph
        self._node_items.clear()
        self._edge_items.clear()
        self._label_items.clear()
        self._poi_text_items.clear()

    def clear_highlights(self):
        """Clear path and node highlights."""
        self._highlight_path = []
        self._start_node = None
        self._goal_node = None
        self._waypoint_nodes = []
        self._selected_node = None
        for item_id in self._path_items:
            self.delete(item_id)
        self._path_items = []

    # ------------------------------------------------------------------
    # Coordinate transform
    # ------------------------------------------------------------------

    def to_canvas(self, x: float, y: float) -> Tuple[float, float]:
        """Convert virtual coordinates to canvas pixel coordinates."""
        cx = x * self._scale + self._offset_x
        cy = y * self._scale + self._offset_y
        return cx, cy

    def to_virtual(self, canvas_x: float, canvas_y: float) -> Tuple[float, float]:
        """Convert canvas pixel coordinates to virtual coordinates."""
        vx = (canvas_x - self._offset_x) / self._scale
        vy = (canvas_y - self._offset_y) / self._scale
        return vx, vy

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self):
        """Full render of the graph."""
        self.delete("all")
        self._node_items.clear()
        self._edge_items.clear()
        self._label_items.clear()
        self._poi_text_items.clear()
        self._path_items = []
        self._vehicle_items.clear()

        if not self._graph:
            self.create_text(
                self.winfo_width() // 2, self.winfo_height() // 2,
                text="未加载地图", fill="#7f8c8d",
                font=("SimHei", 16),
            )
            return

        self._draw_edges()
        self._draw_nodes()
        self._draw_poi_icons()

        # Redraw highlights if any
        if self._highlight_path:
            self._draw_path(self._highlight_path)
        if self._vehicles:
            self._draw_vehicles()

    def _draw_edges(self):
        """Draw all edges with road-type coloring."""
        if not self._graph:
            return

        drawn = set()
        for from_id in self._graph:
            for edge in self._graph.get_edges(from_id):
                # Skip reverse of undirected edges to avoid double-draw
                rev_key = (edge.to_id, edge.from_id)
                if rev_key in drawn and not edge.one_way:
                    continue
                drawn.add((from_id, edge.to_id))

                from_node = self._graph.get_node(from_id)
                to_node = self._graph.get_node(edge.to_id)
                if not from_node or not to_node:
                    continue

                x1, y1 = self.to_canvas(from_node.x, from_node.y)
                x2, y2 = self.to_canvas(to_node.x, to_node.y)

                road = edge.road_type.value
                color = ROAD_COLORS.get(road, "#95a5a6")

                # Override with congestion color
                cong_key = (from_id, edge.to_id)
                if cong_key in self._congestion_map:
                    level = self._congestion_map[cong_key]
                    if level in CONGESTION_COLORS:
                        color = CONGESTION_COLORS[level]

                width = ROAD_WIDTHS.get(road, 1)
                dash = ROAD_DASH.get(road, ())

                item_id = self.create_line(
                    x1, y1, x2, y2,
                    fill=color, width=width, dash=dash,
                    tags=("edge",),
                )
                self._edge_items[(from_id, edge.to_id)] = item_id

                # One-way arrow
                if edge.one_way:
                    self._draw_arrow(x1, y1, x2, y2, color)

    def _draw_arrow(self, x1, y1, x2, y2, color):
        """Draw a small arrowhead for one-way edges."""
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2
        dx = x2 - x1
        dy = y2 - y1
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        px, py = -uy, ux
        arrow_size = 5 * self._scale
        self.create_polygon(
            mid_x, mid_y,
            mid_x - ux * arrow_size + px * arrow_size * 0.5,
            mid_y - uy * arrow_size + py * arrow_size * 0.5,
            mid_x - ux * arrow_size - px * arrow_size * 0.5,
            mid_y - uy * arrow_size - py * arrow_size * 0.5,
            fill=color, outline=color,
        )

    def _draw_nodes(self):
        """Draw all nodes as colored shapes."""
        if not self._graph:
            return

        for node_id, node in self._graph.vertices.items():
            x, y = self.to_canvas(node.x, node.y)
            ntype = node.node_type.value
            color = NODE_COLORS.get(ntype, "#bdc3c7")
            radius = max(3, NODE_RADIUS.get(ntype, 4) * self._scale)

            # Start/goal override
            if node_id == self._start_node:
                color = START_COLOR
                radius = max(5, 7 * self._scale)
            elif node_id == self._goal_node:
                color = GOAL_COLOR
                radius = max(5, 7 * self._scale)
            elif node_id in self._waypoint_nodes:
                color = "#f39c12"
            elif node_id == self._selected_node:
                color = "#e74c3c"

            # Shape by type
            if ntype in ("stair",):
                item_id = self._draw_diamond(x, y, radius, color, node.name)
            elif ntype in ("elevator", "parking"):
                item_id = self._draw_rect(x, y, radius, color, node.name)
            elif ntype in ("corridor", "intersection"):
                item_id = self._draw_circle(x, y, max(2, radius * 0.5), color, node.name)
            else:
                item_id = self._draw_circle(x, y, radius, color, node.name)

            self._node_items[node_id] = item_id

            # Label
            if self._show_node_labels:
                font_size = max(7, int(9 * self._scale))
                label_id = self.create_text(
                    x, y - radius - 3,
                    text=node.name if len(node.name) <= 8 else node.name[:7] + "…",
                    fill="#ecf0f1", font=("SimHei", font_size),
                    tags=("label",),
                )
                self._label_items[node_id] = label_id

    def _draw_circle(self, x, y, r, color, name=""):
        """Draw a circular node."""
        return self.create_oval(
            x - r, y - r, x + r, y + r,
            fill=color, outline="#ecf0f1", width=1,
            tags=("node",),
        )

    def _draw_diamond(self, x, y, r, color, name=""):
        """Draw a diamond-shaped node (for stairs)."""
        return self.create_polygon(
            x, y - r, x + r, y, x, y + r, x - r, y,
            fill=color, outline="#ecf0f1", width=1,
            tags=("node",),
        )

    def _draw_rect(self, x, y, r, color, name=""):
        """Draw a rectangle node (for elevators)."""
        return self.create_rectangle(
            x - r, y - r * 0.7, x + r, y + r * 0.7,
            fill=color, outline="#ecf0f1", width=1,
            tags=("node",),
        )

    def _draw_poi_icons(self):
        """Draw emoji icons for POI nodes."""
        if not self._graph or not self._show_poi_icons:
            return

        for node in self._graph.get_poi_nodes():
            x, y = self.to_canvas(node.x, node.y)
            if node.poi_category:
                emoji = POI_EMOJI.get(node.poi_category.value, "📍")
                font_size = max(10, int(14 * self._scale))
                item_id = self.create_text(
                    x + 10 * self._scale, y - 10 * self._scale,
                    text=emoji, font=("Segoe UI Emoji", font_size),
                    tags=("poi_icon",),
                )
                self._poi_text_items[node.node_id] = item_id

    # ------------------------------------------------------------------
    # Path rendering
    # ------------------------------------------------------------------

    def show_path(self, path: List[str], start: str = None, goal: str = None):
        """Highlight a path on the map."""
        # Clear old path
        for item_id in self._path_items:
            self.delete(item_id)
        self._path_items = []

        self._highlight_path = path
        if start:
            self._start_node = start
        if goal:
            self._goal_node = goal

        if not path or len(path) < 2:
            return

        self._draw_path(path)
        # Re-render nodes to update start/goal colors
        self._redraw_nodes()

    def _draw_path(self, path: List[str]):
        """Draw the path as highlighted lines."""
        for i in range(len(path) - 1):
            n1 = self._graph.get_node(path[i])
            n2 = self._graph.get_node(path[i + 1])
            if not n1 or not n2:
                continue
            x1, y1 = self.to_canvas(n1.x, n1.y)
            x2, y2 = self.to_canvas(n2.x, n2.y)

            item_id = self.create_line(
                x1, y1, x2, y2,
                fill=PATH_COLOR, width=PATH_WIDTH + 1,
                tags=("path",),
            )
            self._path_items.append(item_id)

    def _redraw_nodes(self):
        """Delete and redraw all nodes (to update colors)."""
        for item_id in self._node_items.values():
            self.delete(item_id)
        for item_id in self._label_items.values():
            self.delete(item_id)
        self._node_items.clear()
        self._label_items.clear()
        self._draw_nodes()

    # ------------------------------------------------------------------
    # Vehicle rendering
    # ------------------------------------------------------------------

    def show_vehicles(self, vehicles: List[Vehicle]):
        """Show vehicle markers on the map."""
        self._vehicles = vehicles
        self._draw_vehicles()

    def _draw_vehicles(self):
        """Draw vehicle markers."""
        for item_id in self._vehicle_items.values():
            self.delete(item_id)
        self._vehicle_items.clear()

        for v in self._vehicles:
            x, y = self.to_canvas(v.x, v.y)
            r = 5 * self._scale
            item_id = self.create_oval(
                x - r, y - r, x + r, y + r,
                fill="#e74c3c", outline="#fff", width=1,
                tags=("vehicle",),
            )
            self._vehicle_items[v.vehicle_id] = item_id

            # Label
            self.create_text(
                x, y - r - 5,
                text=v.name, fill="#e74c3c",
                font=("SimHei", max(7, int(8 * self._scale))),
                tags=("vehicle_label",),
            )

    # ------------------------------------------------------------------
    # Congestion overlay
    # ------------------------------------------------------------------

    def set_congestion(self, edge_key: Tuple[str, str], level: str):
        """Set congestion level for an edge and redraw it."""
        self._congestion_map[edge_key] = level
        # Redraw the affected edge
        if edge_key in self._edge_items:
            self.delete(self._edge_items[edge_key])
        from_node = self._graph.get_node(edge_key[0])
        to_node = self._graph.get_node(edge_key[1])
        if from_node and to_node:
            x1, y1 = self.to_canvas(from_node.x, from_node.y)
            x2, y2 = self.to_canvas(to_node.x, to_node.y)
            color = CONGESTION_COLORS.get(level, ROAD_COLORS.get("main_road", "#3498db"))
            edge = self._graph.get_edge(edge_key[0], edge_key[1])
            width = ROAD_WIDTHS.get(edge.road_type.value if edge else "main_road", 2)
            item_id = self.create_line(x1, y1, x2, y2, fill=color, width=max(2, width + 1))
            self._edge_items[edge_key] = item_id

    # ------------------------------------------------------------------
    # Zoom and pan
    # ------------------------------------------------------------------

    def _on_mousewheel(self, event):
        """Zoom in/out with mouse wheel."""
        # Get canvas coords under mouse
        if event.num == 4 or event.delta > 0:
            factor = 1.1
        elif event.num == 5 or event.delta < 0:
            factor = 0.9
        else:
            factor = 1.0

        mx = self.canvasx(event.x) if hasattr(event, 'x') else event.x
        my = self.canvasy(event.y) if hasattr(event, 'y') else event.y

        # Zoom toward mouse position
        old_scale = self._scale
        self._scale = max(0.1, min(self._scale * factor, 5.0))

        # Adjust offset to keep mouse point stable
        self._offset_x = mx - (mx - self._offset_x) * (self._scale / old_scale)
        self._offset_y = my - (my - self._offset_y) * (self._scale / old_scale)

        self.render()

    def _on_press(self, event):
        """Start pan or node selection."""
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        self._pan_start_x = self._offset_x
        self._pan_start_y = self._offset_y

    def _on_drag(self, event):
        """Pan the view."""
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y

        if abs(dx) > 3 or abs(dy) > 3:
            self._offset_x = self._pan_start_x + dx
            self._offset_y = self._pan_start_y + dy
            self.render()

    def _on_release(self, event):
        """Handle click (if no significant drag)."""
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y

        if abs(dx) < 3 and abs(dy) < 3:
            # It was a click — find nearest node
            self._handle_click(event.x, event.y)

    def _handle_click(self, canvas_x, canvas_y):
        """Find and select the nearest node to a click."""
        if not self._graph:
            return

        vx, vy = self.to_virtual(canvas_x, canvas_y)
        best_node = None
        best_dist = float("inf")

        for node_id, node in self._graph.vertices.items():
            dx = node.x - vx
            dy = node.y - vy
            d = dx * dx + dy * dy
            if d < best_dist:
                best_dist = d
                best_node = node_id

        threshold = (20 / self._scale) ** 2
        if best_dist < threshold:
            self._selected_node = best_node
            if self._on_node_click:
                self._on_node_click(best_node)
            self._redraw_nodes()

    def _on_resize(self, event):
        """Re-render on window resize."""
        self.render()

    def set_node_click_callback(self, callback):
        """Set callback for node click events: callback(node_id)."""
        self._on_node_click = callback

    # ------------------------------------------------------------------
    # View control
    # ------------------------------------------------------------------

    def zoom_in(self):
        """Zoom in by 10%."""
        self._scale = min(self._scale * 1.2, 5.0)
        self.render()

    def zoom_out(self):
        """Zoom out by 10%."""
        self._scale = max(self._scale * 0.8, 0.1)
        self.render()

    def fit_to_view(self):
        """Auto-fit the graph to the canvas."""
        if not self._graph or self._graph.total_vertices == 0:
            return

        # Find bounds
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for node in self._graph.vertices.values():
            min_x = min(min_x, node.x)
            min_y = min(min_y, node.y)
            max_x = max(max_x, node.x)
            max_y = max(max_y, node.y)

        if min_x == float("inf"):
            return

        # Add padding
        pad = 20
        vw = max_x - min_x + pad * 2
        vh = max_y - min_y + pad * 2

        cw = self.winfo_width() or 800
        ch = self.winfo_height() or 600

        self._scale = min(cw / vw, ch / vh) if vw > 0 and vh > 0 else 1.0
        self._offset_x = (cw - vw * self._scale) / 2 - min_x * self._scale + pad * self._scale
        self._offset_y = (ch - vh * self._scale) / 2 - min_y * self._scale + pad * self._scale

        self.render()

    def get_scale(self) -> float:
        """Return current zoom scale."""
        return self._scale

    def get_offset(self) -> Tuple[float, float]:
        """Return current pan offset."""
        return (self._offset_x, self._offset_y)
