"""Path Comparison Panel — multi-algorithm benchmarking (wxPython)."""

import wx

from ..services.path_service import PathService
from ..models.transport import TransportMode
from .theme import (
    dark_panel, dark_label, dark_button, dark_text, dark_combo,
    dark_listctrl, dark_radio, hex_to_wx_colour,
)
from .styles import PANEL_BG, TEXT_COLOR


class ComparisonPanel(wx.Panel):
    """Tab 6: Multi-algorithm path comparison with results table."""

    def __init__(self, parent, app, path_service: PathService):
        super().__init__(parent)
        self._app = app
        self._path_service = path_service
        self._mode = "walking"
        self._results = []
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Inputs ---
        sizer.Add(dark_label(self, label="起点"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        self._start_combo = dark_combo(self, choices=[], style=wx.CB_READONLY)
        sizer.Add(self._start_combo, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        sizer.Add(dark_label(self, label="终点"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        self._end_combo = dark_combo(self, choices=[], style=wx.CB_READONLY)
        sizer.Add(self._end_combo, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        # --- Mode ---
        sizer.Add(dark_label(self, label="交通方式"), proportion=0,
                 flag=wx.TOP, border=3)
        mode_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._mode_radios = {}
        for i, (text, val) in enumerate([("🚶步行", "walking"), ("🚗驾车", "driving"), ("🚌公交", "bus")]):
            rb = dark_radio(self, label=text,
                           style=wx.RB_GROUP if i == 0 else 0)
            rb.Bind(wx.EVT_RADIOBUTTON, lambda e, v=val: setattr(self, '_mode', v))
            mode_sizer.Add(rb, proportion=0, flag=wx.RIGHT, border=2)
        sizer.Add(mode_sizer, proportion=0, flag=wx.BOTTOM, border=3)

        # --- Compare button ---
        compare_btn = wx.Button(self, label="📊 比较所有算法")
        compare_btn.Bind(wx.EVT_BUTTON, lambda e: self._run_comparison())
        sizer.Add(compare_btn, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM, border=6)

        # --- Results table ---
        self._result_list = dark_listctrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self._result_list.InsertColumn(0, "算法", width=120)
        self._result_list.InsertColumn(1, "距离(m)", width=70)
        self._result_list.InsertColumn(2, "时间(s)", width=60)
        self._result_list.InsertColumn(3, "费用", width=50)
        self._result_list.InsertColumn(4, "路径节点", width=60)
        self._result_list.InsertColumn(5, "耗时(ms)", width=70)
        self._result_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_result_select)
        sizer.Add(self._result_list, proportion=1, flag=wx.EXPAND | wx.BOTTOM, border=3)

        show_btn = wx.Button(self, label="🗺 在地图上显示选中路径")
        show_btn.Bind(wx.EVT_BUTTON, lambda e: self._show_on_map())
        sizer.Add(show_btn, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        # --- Summary ---
        self._summary_text = dark_text(self, value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY)
        self._summary_text.SetMinSize(wx.Size(-1, 60))
        sizer.Add(self._summary_text, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        self.SetSizer(sizer)

    def on_map_changed(self, scene_id: str):
        """Update node lists."""
        graph = self._app.get_active_graph()
        if not graph:
            return
        nodes = graph.get_all_nodes()
        names = [f"{nid} - {graph.get_node(nid).name}" for nid in nodes]
        self._start_combo.Clear()
        self._start_combo.Set(names)
        self._end_combo.Clear()
        self._end_combo.Set(names)

    def _parse_node_id(self, s: str) -> str:
        """Extract node ID from 'N001 - Name' format."""
        if " - " in s:
            return s.split(" - ")[0].strip()
        return s.strip()

    def _run_comparison(self):
        """Run all algorithms and display comparison."""
        start_id = self._parse_node_id(self._start_combo.GetValue())
        goal_id = self._parse_node_id(self._end_combo.GetValue())

        if not start_id or not goal_id:
            return

        graph = self._app.get_active_graph()
        if not graph:
            return

        try:
            mode = TransportMode(self._mode)
        except ValueError:
            mode = TransportMode.WALKING

        self._results = self._path_service.compare_algorithms(
            graph, start_id, goal_id, mode,
        )

        self._result_list.DeleteAllItems()
        self._summary_text.SetValue("")

        best_dist = float("inf")
        best_algo = ""

        for r in self._results:
            if not r.is_reachable:
                continue
            idx = self._result_list.InsertItem(10000, r.algorithm)
            self._result_list.SetItem(idx, 1, f"{r.total_distance:.0f}")
            self._result_list.SetItem(idx, 2, f"{r.total_time:.0f}")
            self._result_list.SetItem(idx, 3, f"{r.total_cost:.2f}")
            self._result_list.SetItem(idx, 4, str(r.path_length))
            self._result_list.SetItem(idx, 5, f"{r.execution_time_ms:.2f}")
            if r.total_distance < best_dist:
                best_dist = r.total_distance
                best_algo = r.algorithm

        if best_algo:
            self._summary_text.SetValue(
                f"🏆 最佳算法: {best_algo}\n"
                f"📏 最短距离: {best_dist:.0f} m\n"
                f"📊 共比较 {len([r for r in self._results if r.is_reachable])} 个算法\n"
            )

    def _on_result_select(self, event):
        """Result row selected."""
        pass

    def _show_on_map(self):
        """Display the selected result path on the map."""
        idx = self._result_list.GetFirstSelected()
        if idx < 0:
            return

        reachable = [r for r in self._results if r.is_reachable]
        if idx < len(reachable):
            self._app.show_path_on_map(reachable[idx].path)
