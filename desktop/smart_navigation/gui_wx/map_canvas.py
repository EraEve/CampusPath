"""Map Canvas — wxPython ScrolledWindow with GraphicsContext rendering.

Renders the navigation graph using wx.GraphicsContext (GPU-accelerated):
- Nodes as colored shapes (circle, diamond, rectangle per type)
- Edges as colored lines (by road type)
- Found paths as highlighted lines
- Vehicles as moving dots
- POI labels with emoji
- Zoom (mouse wheel) and pan (click-drag)
"""

import math
import wx
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
from .theme import hex_to_wx_colour


# ---------------------------------------------------------------------------
# wx.GraphicsContext pen/brush cache (keyed by colour + width)
# ---------------------------------------------------------------------------
_pen_cache: Dict[str, wx.GraphicsPen] = {}
_brush_cache: Dict[str, wx.GraphicsBrush] = {}


def _make_pen(colour_hex: str, width: float = 1.0) -> wx.Pen:
    """Create or retrieve a cached wx.Pen."""
    assert isinstance(colour_hex, str), f"colour_hex must be str, got {type(colour_hex)}: {colour_hex!r}"
    key = f"{colour_hex}_{width:.1f}"
    if key not in _pen_cache:
        col = hex_to_wx_colour(colour_hex)
        _pen_cache[key] = wx.Pen(col, int(width))
    return _pen_cache[key]


def _make_brush(colour_hex: str) -> wx.Brush:
    """Create or retrieve a cached wx.Brush."""
    assert isinstance(colour_hex, str), f"colour_hex must be str, got {type(colour_hex)}: {colour_hex!r}"
    if colour_hex not in _brush_cache:
        col = hex_to_wx_colour(colour_hex)
        _brush_cache[colour_hex] = wx.Brush(col)
    return _brush_cache[colour_hex]


# ---------------------------------------------------------------------------
# MapCanvas
# ---------------------------------------------------------------------------

class MapCanvas(wx.ScrolledWindow):
    """Interactive map renderer with zoom and pan (wxPython).

    Usage:
        canvas = MapCanvas(parent)
        canvas.set_graph(graph)
        canvas.Refresh()
        canvas.show_path(path_list)
    """

    def __init__(self, parent, **kwargs):
        super().__init__(parent, style=wx.FULL_REPAINT_ON_RESIZE)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)  # flicker-free double-buffer
        self.SetBackgroundColour(hex_to_wx_colour(CANVAS_BG))
        self.SetScrollRate(20, 20)
        self.SetVirtualSize(2000, 1500)
        self.EnableScrolling(True, True)

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
        self._congestion_map: Dict[Tuple[str, str], str] = {}
        self._selected_node: Optional[str] = None
        self._on_node_click = None  # callback(node_id)

        # Bind events
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_MOUSEWHEEL, self._on_mousewheel)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)
        self.Bind(wx.EVT_MOTION, self._on_motion)
        self.Bind(wx.EVT_SIZE, self._on_size)

    # ------------------------------------------------------------------
    # Graph management
    # ------------------------------------------------------------------

    def set_graph(self, graph: NavGraph):
        """Set the graph to render."""
        self._graph = graph
        self._congestion_map.clear()

    def clear_highlights(self):
        """Clear path and node highlights."""
        self._highlight_path = []
        self._start_node = None
        self._goal_node = None
        self._waypoint_nodes = []
        self._selected_node = None

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
    # Rendering (immediate-mode via GraphicsContext)
    # ------------------------------------------------------------------

    def _on_paint(self, event):
        """Paint event handler — draws everything via GraphicsContext."""
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(hex_to_wx_colour(CANVAS_BG)))
        dc.Clear()

        if not self._graph:
            # No map loaded
            w, h = self.GetClientSize()
            dc.SetTextForeground(hex_to_wx_colour("#7f8c8d"))
            font = wx.Font(16, wx.FONTFAMILY_DEFAULT,
                          wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
            dc.SetFont(font)
            text = "未加载地图"
            tw, th = dc.GetTextExtent(text)
            dc.DrawText(text, (w - tw) // 2, (h - th) // 2)
            return

        gc = wx.GraphicsContext.Create(dc)
        if not gc:
            # Fallback: GraphicsContext not available on this platform
            return

        # Apply viewport transform
        gc.Translate(self._offset_x, self._offset_y)
        gc.Scale(self._scale, self._scale)

        self._draw_edges(gc)
        if self._highlight_path:
            self._draw_path(gc)
        self._draw_nodes(gc)
        if self._show_poi_icons:
            self._draw_poi_icons(gc)
        # Vehicles drawn in device coords for consistent size
        if self._vehicles:
            self._draw_vehicles(gc)

    def _draw_edges(self, gc: wx.GraphicsContext):
        """Draw all edges with road-type coloring."""
        if not self._graph:
            return

        drawn = set()
        for from_id in self._graph:
            for edge in self._graph.get_edges(from_id):
                rev_key = (edge.to_id, edge.from_id)
                if rev_key in drawn and not edge.one_way:
                    continue
                drawn.add((from_id, edge.to_id))

                from_node = self._graph.get_node(from_id)
                to_node = self._graph.get_node(edge.to_id)
                if not from_node or not to_node:
                    continue

                x1, y1 = from_node.x, from_node.y
                x2, y2 = to_node.x, to_node.y

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

                pen = _make_pen(color, float(width))
                gc.SetPen(gc.CreatePen(pen))
                gc.StrokeLine(x1, y1, x2, y2)

                # One-way arrow
                if edge.one_way:
                    self._draw_arrow(gc, x1, y1, x2, y2, color)

    def _draw_arrow(self, gc: wx.GraphicsContext, x1, y1, x2, y2, color):
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
        arrow_size = 5  # virtual coords, scale handles size
        brush = _make_brush(color)
        gc.SetBrush(gc.CreateBrush(brush))
        gc.SetPen(gc.CreatePen(_make_pen(color, 0.5)))
        path = gc.CreatePath()
        path.MoveToPoint(mid_x, mid_y)
        path.AddLineToPoint(mid_x - ux * arrow_size + px * arrow_size * 0.5,
                           mid_y - uy * arrow_size + py * arrow_size * 0.5)
        path.AddLineToPoint(mid_x - ux * arrow_size - px * arrow_size * 0.5,
                           mid_y - uy * arrow_size - py * arrow_size * 0.5)
        path.CloseSubpath()
        gc.FillPath(path)

    def _draw_nodes(self, gc: wx.GraphicsContext):
        """Draw all nodes as colored shapes."""
        if not self._graph:
            return

        for node_id, node in self._graph.vertices.items():
            x, y = node.x, node.y
            ntype = node.node_type.value
            color = NODE_COLORS.get(ntype, "#bdc3c7")
            radius = max(3, NODE_RADIUS.get(ntype, 4))

            # Start/goal/waypoint/selected override
            if node_id == self._start_node:
                color = START_COLOR
                radius = max(5, 7)
            elif node_id == self._goal_node:
                color = GOAL_COLOR
                radius = max(5, 7)
            elif node_id in self._waypoint_nodes:
                color = "#f39c12"
            elif node_id == self._selected_node:
                color = "#e74c3c"

            brush = _make_brush(color)
            gc.SetBrush(gc.CreateBrush(brush))
            gc.SetPen(gc.CreatePen(_make_pen("#ecf0f1", 1.0)))

            # Shape by type
            if ntype in ("stair",):
                self._draw_diamond(gc, x, y, radius)
            elif ntype in ("elevator", "parking"):
                self._draw_rect(gc, x, y, radius)
            elif ntype in ("corridor", "intersection"):
                self._draw_circle(gc, x, y, max(2, radius * 0.5))
            else:
                self._draw_circle(gc, x, y, radius)

            # Label
            if self._show_node_labels:
                label = node.name if len(node.name) <= 8 else node.name[:7] + "…"
                gc.SetFont(
                    wx.Font(9, wx.FONTFAMILY_DEFAULT,
                           wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL),
                    hex_to_wx_colour("#ecf0f1")
                )
                # Position text above the node
                tw, th = gc.GetTextExtent(label)
                gc.DrawText(label, x - tw / 2, y - radius - th - 2)

    def _draw_circle(self, gc, x, y, r):
        """Draw a filled circle."""
        gc.DrawEllipse(x - r, y - r, r * 2, r * 2)

    def _draw_diamond(self, gc, x, y, r):
        """Draw a filled diamond (for stairs)."""
        path = gc.CreatePath()
        path.MoveToPoint(x, y - r)
        path.AddLineToPoint(x + r, y)
        path.AddLineToPoint(x, y + r)
        path.AddLineToPoint(x - r, y)
        path.CloseSubpath()
        gc.FillPath(path)

    def _draw_rect(self, gc, x, y, r):
        """Draw a filled rectangle (for elevators/parking)."""
        gc.DrawRectangle(x - r, y - r * 0.7, r * 2, r * 1.4)

    def _draw_poi_icons(self, gc: wx.GraphicsContext):
        """Draw emoji icons for POI nodes."""
        if not self._graph:
            return

        for node in self._graph.get_poi_nodes():
            if node.poi_category:
                emoji = POI_EMOJI.get(node.poi_category.value, "📍")
                gc.SetFont(
                    wx.Font(14, wx.FONTFAMILY_DEFAULT,
                           wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL),
                    hex_to_wx_colour(POI_COLORS.get(
                        node.poi_category.value, "#e91e63"))
                )
                gc.DrawText(emoji, node.x + 10, node.y - 10)

    # ------------------------------------------------------------------
    # Path rendering
    # ------------------------------------------------------------------

    def show_path(self, path: List[str], start: str = None, goal: str = None):
        """Highlight a path on the map."""
        self._highlight_path = path
        if start:
            self._start_node = start
        if goal:
            self._goal_node = goal
        self.Refresh()

    def _draw_path(self, gc: wx.GraphicsContext):
        """Draw the path as highlighted lines."""
        for i in range(len(self._highlight_path) - 1):
            n1 = self._graph.get_node(self._highlight_path[i])
            n2 = self._graph.get_node(self._highlight_path[i + 1])
            if not n1 or not n2:
                continue
            pen = _make_pen(PATH_COLOR, float(PATH_WIDTH + 1))
            gc.SetPen(gc.CreatePen(pen))
            gc.StrokeLine(n1.x, n1.y, n2.x, n2.y)

    # ------------------------------------------------------------------
    # Vehicle rendering
    # ------------------------------------------------------------------

    def show_vehicles(self, vehicles: List[Vehicle]):
        """Show vehicle markers on the map."""
        self._vehicles = vehicles
        self.Refresh()

    def _draw_vehicles(self, gc: wx.GraphicsContext):
        """Draw vehicle markers (in virtual coords)."""
        for v in self._vehicles:
            x, y = v.x, v.y
            r = 5
            brush = _make_brush("#e74c3c")
            gc.SetBrush(gc.CreateBrush(brush))
            gc.SetPen(gc.CreatePen(_make_pen("#ffffff", 1.0)))
            gc.DrawEllipse(x - r, y - r, r * 2, r * 2)

            # Label
            gc.SetFont(
                wx.Font(8, wx.FONTFAMILY_DEFAULT,
                       wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL),
                hex_to_wx_colour("#e74c3c")
            )
            tw, th = gc.GetTextExtent(v.name)
            gc.DrawText(v.name, x - tw / 2, y - r - th - 2)

    # ------------------------------------------------------------------
    # Congestion overlay
    # ------------------------------------------------------------------

    def set_congestion(self, edge_key: Tuple[str, str], level: str):
        """Set congestion level for an edge and refresh."""
        self._congestion_map[edge_key] = level
        self.Refresh()

    # ------------------------------------------------------------------
    # Zoom and pan
    # ------------------------------------------------------------------

    def _on_mousewheel(self, event):
        """Zoom in/out with mouse wheel (toward cursor)."""
        if event.GetWheelRotation() > 0:
            factor = 1.1
        elif event.GetWheelRotation() < 0:
            factor = 0.9
        else:
            factor = 1.0

        # Get mouse position in client coords
        pos = event.GetPosition()
        mx, my = pos.x, pos.y

        old_scale = self._scale
        self._scale = max(0.1, min(self._scale * factor, 5.0))

        # Adjust offset to keep mouse point stable
        self._offset_x = mx - (mx - self._offset_x) * (self._scale / old_scale)
        self._offset_y = my - (my - self._offset_y) * (self._scale / old_scale)

        self.Refresh()

    def _on_left_down(self, event):
        """Start pan or prepare for click."""
        pos = event.GetPosition()
        self._drag_start_x = pos.x
        self._drag_start_y = pos.y
        self._pan_start_x = self._offset_x
        self._pan_start_y = self._offset_y
        self.CaptureMouse()

    def _on_left_up(self, event):
        """End pan; if no significant drag, treat as click."""
        if self.HasCapture():
            self.ReleaseMouse()

        pos = event.GetPosition()
        dx = pos.x - self._drag_start_x
        dy = pos.y - self._drag_start_y

        if abs(dx) < 3 and abs(dy) < 3:
            self._handle_click(pos.x, pos.y)

    def _on_motion(self, event):
        """Pan the view while dragging."""
        if not event.Dragging() or not self.HasCapture():
            return

        pos = event.GetPosition()
        dx = pos.x - self._drag_start_x
        dy = pos.y - self._drag_start_y

        if abs(dx) > 2 or abs(dy) > 2:
            self._offset_x = self._pan_start_x + dx
            self._offset_y = self._pan_start_y + dy
            self.Refresh()

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
            self.Refresh()

    def _on_size(self, event):
        """Re-render on window resize."""
        self.Refresh()
        event.Skip()

    # ------------------------------------------------------------------
    # View control
    # ------------------------------------------------------------------

    def zoom_in(self):
        """Zoom in by 20%."""
        self._scale = min(self._scale * 1.2, 5.0)
        self.Refresh()

    def zoom_out(self):
        """Zoom out by 20%."""
        self._scale = max(self._scale * 0.8, 0.1)
        self.Refresh()

    def set_show_labels(self, show: bool):
        """Set whether node labels are shown."""
        self._show_node_labels = show

    def fit_to_view(self):
        """Auto-fit the graph to the canvas."""
        if not self._graph or self._graph.total_vertices == 0:
            return

        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")
        for node in self._graph.vertices.values():
            min_x = min(min_x, node.x)
            min_y = min(min_y, node.y)
            max_x = max(max_x, node.x)
            max_y = max(max_y, node.y)

        if min_x == float("inf"):
            return

        pad = 20
        vw = max_x - min_x + pad * 2
        vh = max_y - min_y + pad * 2

        cw, ch = self.GetClientSize()
        if cw <= 0:
            cw = 800
        if ch <= 0:
            ch = 600

        self._scale = min(cw / vw, ch / vh) if vw > 0 and vh > 0 else 1.0
        self._offset_x = (cw - vw * self._scale) / 2 - min_x * self._scale + pad * self._scale
        self._offset_y = (ch - vh * self._scale) / 2 - min_y * self._scale + pad * self._scale

        self.Refresh()

    def get_scale(self) -> float:
        """Return current zoom scale."""
        return self._scale

    def get_offset(self) -> Tuple[float, float]:
        """Return current pan offset."""
        return (self._offset_x, self._offset_y)

    # ------------------------------------------------------------------
    # Callback
    # ------------------------------------------------------------------

    def set_node_click_callback(self, callback):
        """Set callback for node click events: callback(node_id)."""
        self._on_node_click = callback
