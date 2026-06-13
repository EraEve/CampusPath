"""Path Planning Tab — route planning controls and result display (wxPython)."""

import wx
from typing import Optional

from ..core.map_manager import MapManager
from ..services.path_service import PathService
from ..models.transport import TransportMode
from .theme import (
    dark_panel, dark_label, dark_button, dark_text, dark_combo,
    dark_slider, dark_checkbox, dark_radio, dark_listbox,
    hex_to_wx_colour, configure_dark_panel,
)
from .styles import BG_COLOR, PANEL_BG, TEXT_COLOR


class PathPlanningTab(wx.Panel):
    """Tab 1: Path Planning with start/end/waypoint selection."""

    def __init__(self, parent, app, map_manager: MapManager, path_service: PathService):
        super().__init__(parent)
        self._app = app
        self._map_manager = map_manager
        self._path_service = path_service

        self._mode = "walking"
        self._algo = "dijkstra"
        self._heuristic = "euclidean"
        self._highway = False
        self._congestion = False
        self._multi_criteria = False
        self._w_dist = 0.4
        self._w_time = 0.4
        self._w_cost = 0.2

        self._node_list: list = []
        self._build_ui()

    def _build_ui(self):
        # Scrolled window
        scrolled = wx.ScrolledWindow(self)
        scrolled.SetScrollRate(0, 10)
        configure_dark_panel(scrolled)

        outer_sizer = wx.BoxSizer(wx.VERTICAL)
        f = scrolled

        # --- Transport mode ---
        outer_sizer.Add(dark_label(f, label="出行方式"), proportion=0,
                       flag=wx.TOP | wx.BOTTOM, border=4)
        mode_sizer = wx.BoxSizer(wx.HORIZONTAL)

        modes = [("🚗 驾车", "driving"), ("🚶 步行", "walking"), ("🚌 公交", "bus"),
                 ("🚄 火车", "train"), ("🚇 地铁", "subway")]
        self._mode_radios = {}
        for i, (text, val) in enumerate(modes):
            rb = dark_radio(f, label=text,
                           style=wx.RB_GROUP if i == 0 else 0)
            rb.Bind(wx.EVT_RADIOBUTTON, lambda e, v=val: self._on_mode_change(v))
            mode_sizer.Add(rb, proportion=0, flag=wx.RIGHT, border=2)
            self._mode_radios[val] = rb
        outer_sizer.Add(mode_sizer, proportion=0)

        # --- Start / End ---
        outer_sizer.Add(dark_label(f, label="起点"), proportion=0,
                       flag=wx.TOP, border=6)
        self._start_combo = dark_combo(f, choices=[], style=wx.CB_READONLY)
        outer_sizer.Add(self._start_combo, proportion=0, flag=wx.EXPAND)

        outer_sizer.Add(dark_label(f, label="终点"), proportion=0,
                       flag=wx.TOP, border=6)
        self._end_combo = dark_combo(f, choices=[], style=wx.CB_READONLY)
        outer_sizer.Add(self._end_combo, proportion=0, flag=wx.EXPAND)

        outer_sizer.Add(dark_label(f, label="途经点 (可选，分号分隔)"), proportion=0,
                       flag=wx.TOP, border=4)
        self._via_entry = dark_text(f, style=0)
        outer_sizer.Add(self._via_entry, proportion=0, flag=wx.EXPAND)

        # --- Algorithm ---
        outer_sizer.Add(dark_label(f, label="算法选择"), proportion=0,
                       flag=wx.TOP, border=6)
        algos = ["dijkstra", "a_star", "bfs", "bidirectional_dijkstra",
                 "bidirectional_bfs", "congestion_avoidance", "multi_criteria"]
        algo_labels = {
            "dijkstra": "Dijkstra", "a_star": "A*", "bfs": "BFS",
            "bidirectional_dijkstra": "双向Dijkstra", "bidirectional_bfs": "双向BFS",
            "congestion_avoidance": "避拥堵", "multi_criteria": "多指标",
        }
        algo_display = [f"{a} - {algo_labels.get(a, a)}" for a in algos]
        self._algo_combo = dark_combo(f, choices=algo_display, style=wx.CB_READONLY)
        self._algo_combo.SetSelection(0)
        self._algo_combo.Bind(wx.EVT_COMBOBOX, self._on_algo_change)
        outer_sizer.Add(self._algo_combo, proportion=0, flag=wx.EXPAND)

        # Heuristic (for A*)
        heur_sizer = wx.BoxSizer(wx.HORIZONTAL)
        heur_sizer.Add(dark_label(f, label="启发函数:"), proportion=0,
                      flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=4)
        self._heur_combo = dark_combo(f,
            choices=["euclidean", "manhattan", "floor_aware"],
            style=wx.CB_READONLY)
        self._heur_combo.SetSelection(0)
        heur_sizer.Add(self._heur_combo, proportion=1)
        outer_sizer.Add(heur_sizer, proportion=0, flag=wx.EXPAND | wx.TOP, border=3)

        # --- Options ---
        outer_sizer.Add(dark_label(f, label="路径选项"), proportion=0,
                       flag=wx.TOP, border=6)
        self._highway_cb = dark_checkbox(f, label="高速优先")
        self._highway_cb.Bind(wx.EVT_CHECKBOX, lambda e: setattr(self, '_highway', self._highway_cb.GetValue()))
        outer_sizer.Add(self._highway_cb, proportion=0)

        self._congestion_cb = dark_checkbox(f, label="避让拥堵")
        self._congestion_cb.Bind(wx.EVT_CHECKBOX, lambda e: setattr(self, '_congestion', self._congestion_cb.GetValue()))
        outer_sizer.Add(self._congestion_cb, proportion=0)

        self._mc_cb = dark_checkbox(f, label="多指标优化 (距离/时间/费用)")
        self._mc_cb.Bind(wx.EVT_CHECKBOX, lambda e: setattr(self, '_multi_criteria', self._mc_cb.GetValue()))
        outer_sizer.Add(self._mc_cb, proportion=0)

        # --- Multi-criteria weights ---
        self._mc_panel = wx.Panel(f)
        configure_dark_panel(self._mc_panel)
        mc_sizer = wx.BoxSizer(wx.VERTICAL)

        mc_sizer.Add(dark_label(self._mc_panel, label="距离权重"), proportion=0)
        self._w_dist_slider = dark_slider(self._mc_panel, value=40, minValue=0, maxValue=100)
        mc_sizer.Add(self._w_dist_slider, proportion=0, flag=wx.EXPAND)

        mc_sizer.Add(dark_label(self._mc_panel, label="时间权重"), proportion=0)
        self._w_time_slider = dark_slider(self._mc_panel, value=40, minValue=0, maxValue=100)
        mc_sizer.Add(self._w_time_slider, proportion=0, flag=wx.EXPAND)

        mc_sizer.Add(dark_label(self._mc_panel, label="费用权重"), proportion=0)
        self._w_cost_slider = dark_slider(self._mc_panel, value=20, minValue=0, maxValue=100)
        mc_sizer.Add(self._w_cost_slider, proportion=0, flag=wx.EXPAND)

        self._mc_panel.SetSizer(mc_sizer)
        outer_sizer.Add(self._mc_panel, proportion=0, flag=wx.EXPAND | wx.TOP, border=4)

        # --- Find Path button ---
        find_btn = wx.Button(f, label="🔍 查找路径")
        find_btn.Bind(wx.EVT_BUTTON, lambda e: self._find_path())
        outer_sizer.Add(find_btn, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM, border=8)

        # --- Results ---
        outer_sizer.Add(dark_label(f, label="路径结果"), proportion=0, flag=wx.BOTTOM, border=3)
        self._result_text = dark_text(f, value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY)
        self._result_text.SetMinSize(wx.Size(-1, 120))
        outer_sizer.Add(self._result_text, proportion=0, flag=wx.EXPAND)

        # --- History ---
        outer_sizer.Add(dark_label(f, label="历史记录"), proportion=0,
                       flag=wx.TOP | wx.BOTTOM, border=4)
        self._history_list = dark_listbox(f)
        self._history_list.SetMinSize(wx.Size(-1, 80))
        self._history_list.Bind(wx.EVT_LISTBOX, self._on_history_select)
        outer_sizer.Add(self._history_list, proportion=0, flag=wx.EXPAND)

        f.SetSizer(outer_sizer)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_map_changed(self, scene_id: str):
        """Called when the active map changes."""
        nodes = self._map_manager.get_all_nodes_for_scene(scene_id)
        self._node_list = nodes
        names = [f"{n['node_id']} - {n['name']}" for n in nodes]
        self._start_combo.Clear()
        self._start_combo.Set(names)
        self._end_combo.Clear()
        self._end_combo.Set(names)
        self._start_combo.SetValue("")
        self._end_combo.SetValue("")

    def on_node_clicked(self, node_id: str):
        """Called when a node is clicked on the canvas."""
        if not self._start_combo.GetValue():
            self._start_combo.SetValue(node_id)
        elif not self._end_combo.GetValue():
            self._end_combo.SetValue(node_id)

    def _on_mode_change(self, mode_str):
        """Transport mode changed."""
        self._mode = mode_str
        try:
            mode = TransportMode(mode_str)
            self._app.set_transport_mode(mode)
        except ValueError:
            pass

    def _on_algo_change(self, event):
        """Algorithm selection changed."""
        idx = self._algo_combo.GetSelection()
        if idx < 0:
            return
        algos = ["dijkstra", "a_star", "bfs", "bidirectional_dijkstra",
                 "bidirectional_bfs", "congestion_avoidance", "multi_criteria"]
        if idx < len(algos):
            self._algo = algos[idx]
        # Update heuristic from combo
        heur_idx = self._heur_combo.GetSelection()
        heuristics = ["euclidean", "manhattan", "floor_aware"]
        if 0 <= heur_idx < len(heuristics):
            self._heuristic = heuristics[heur_idx]

    # ------------------------------------------------------------------
    # Path finding
    # ------------------------------------------------------------------

    def _find_path(self):
        """Execute pathfinding."""
        start_str = self._start_combo.GetValue()
        end_str = self._end_combo.GetValue()

        if " - " in start_str:
            start_id = start_str.split(" - ")[0].strip()
        else:
            start_id = start_str.strip()

        if " - " in end_str:
            goal_id = end_str.split(" - ")[0].strip()
        else:
            goal_id = end_str.strip()

        if not start_id or not goal_id:
            self._result_text.SetValue("请选择起点和终点")
            return

        graph = self._app.get_active_graph()
        if graph is None:
            return

        mode_str = self._mode
        try:
            mode = TransportMode(mode_str)
        except ValueError:
            mode = TransportMode.WALKING

        algo = self._algo
        if not algo:
            algo = "dijkstra"

        # Parse waypoints
        via_str = self._via_entry.GetValue().strip()
        waypoints = None
        if via_str:
            waypoints = [w.strip() for w in via_str.split(";") if w.strip()]

        # Read weights from sliders (0-100 → 0.0-1.0)
        self._w_dist = self._w_dist_slider.GetValue() / 100.0
        self._w_time = self._w_time_slider.GetValue() / 100.0
        self._w_cost = self._w_cost_slider.GetValue() / 100.0

        try:
            result = self._path_service.find_path(
                graph, start_id, goal_id,
                transport_mode=mode,
                algorithm=algo,
                heuristic=self._heuristic,
                waypoints=waypoints,
                highway_priority=self._highway_cb.GetValue(),
                congestion_avoidance=self._congestion_cb.GetValue(),
                multi_criteria=self._mc_cb.GetValue(),
                w_distance=self._w_dist,
                w_time=self._w_time,
                w_cost=self._w_cost,
            )
        except Exception as e:
            self._result_text.SetValue(f"错误: {e}")
            return

        if result.is_reachable:
            time_min = result.total_time / 60.0
            text = (
                f"算法: {result.algorithm}\n"
                f"模式: {result.transport_mode}\n"
                f"路径长度: {result.total_distance:.1f} m\n"
                f"预计时间: {time_min:.1f} 分钟\n"
                f"预计费用: {result.total_cost:.2f} 元\n"
                f"节点数: {result.path_length}\n"
                f"搜索节点: {result.nodes_visited}\n"
                f"耗时: {result.execution_time_ms:.2f} ms\n"
            )
            if result.waypoints:
                text += f"途经点: {', '.join(result.waypoints)}\n"
        else:
            text = "未找到可达路径"

        self._result_text.SetValue(text)

        if result.is_reachable:
            self._app.show_path_on_map(result.path, start_id, goal_id)

        self._refresh_history()

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _refresh_history(self):
        """Update the history listbox."""
        self._history_list.Clear()
        for entry in self._path_service.get_history()[:10]:
            start_name = self._get_node_name(entry.path[0]) if entry.path else "?"
            goal_name = self._get_node_name(entry.path[-1]) if entry.path else "?"
            label = f"{start_name} → {goal_name} ({entry.total_distance:.0f}m)"
            self._history_list.Append(label)

    def _on_history_select(self, event):
        """Replay a historical path."""
        idx = self._history_list.GetSelection()
        if idx == wx.NOT_FOUND:
            return
        history = self._path_service.get_history()
        if idx < len(history):
            result = history[idx]
            if result.is_reachable:
                self._app.show_path_on_map(result.path)
                if result.path:
                    self._start_combo.SetValue(result.path[0])
                if result.path:
                    self._end_combo.SetValue(result.path[-1])

    def _get_node_name(self, node_id: str) -> str:
        """Get human-readable node name."""
        graph = self._app.get_active_graph()
        if graph:
            node = graph.get_node(node_id)
            if node:
                return node.name
        return node_id
