"""Real-time Navigation Tab — traffic display, nav status, alerts, reroute (wxPython)."""

import wx

from ..services.traffic_service import TrafficService
from ..services.navigation_service import NavigationService
from .theme import (
    dark_panel, dark_label, dark_button, dark_text, dark_listctrl,
    dark_slider, dark_listbox, hex_to_wx_colour,
)
from .styles import BG_COLOR, DANGER_COLOR


class RealtimeNavTab(wx.Panel):
    """Tab 3: Real-time Navigation with traffic and alerts."""

    def __init__(self, parent, app,
                 traffic_service: TrafficService,
                 navigation_service: NavigationService):
        super().__init__(parent)
        self._app = app
        self._traffic = traffic_service
        self._nav = navigation_service

        self._sim_running = False
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Traffic Simulation ---
        sizer.Add(dark_label(self, label="交通模拟"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        sim_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._sim_btn = wx.Button(self, label="▶ 开始交通模拟")
        self._sim_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_sim())
        sim_sizer.Add(self._sim_btn, proportion=0, flag=wx.RIGHT, border=4)
        self._sim_label = dark_label(self, label="已停止")
        sim_sizer.Add(self._sim_label, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(sim_sizer, proportion=0, flag=wx.BOTTOM, border=3)

        sizer.Add(dark_label(self, label="模拟间隔 (秒):"), proportion=0)
        self._interval_slider = dark_slider(self, value=3, minValue=1, maxValue=10)
        sizer.Add(self._interval_slider, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        # --- Traffic Status ---
        sizer.Add(dark_label(self, label="当前路况"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        self._traffic_list = dark_listctrl(self, style=wx.LC_REPORT)
        self._traffic_list.InsertColumn(0, "路段", width=220)
        self._traffic_list.InsertColumn(1, "状况", width=80)
        sizer.Add(self._traffic_list, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        refresh_btn = wx.Button(self, label="🔄 刷新路况")
        refresh_btn.Bind(wx.EVT_BUTTON, lambda e: self.refresh_traffic_display())
        sizer.Add(refresh_btn, proportion=0, flag=wx.BOTTOM, border=3)

        # --- Blockages ---
        sizer.Add(dark_label(self, label="道路阻塞"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        self._blockage_list = dark_listbox(self)
        self._blockage_list.SetMinSize(wx.Size(-1, 60))
        sizer.Add(self._blockage_list, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        # --- Navigation Status ---
        sizer.Add(dark_label(self, label="导航状态"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        self._nav_status = dark_label(self, label="未开始导航")
        sizer.Add(self._nav_status, proportion=0, flag=wx.BOTTOM, border=3)

        nav_btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        start_btn = wx.Button(self, label="▶ 开始导航")
        start_btn.Bind(wx.EVT_BUTTON, lambda e: self._start_nav())
        nav_btn_sizer.Add(start_btn, proportion=0, flag=wx.RIGHT, border=3)
        stop_btn = wx.Button(self, label="■ 停止导航")
        stop_btn.Bind(wx.EVT_BUTTON, lambda e: self._stop_nav())
        nav_btn_sizer.Add(stop_btn)
        sizer.Add(nav_btn_sizer, proportion=0, flag=wx.BOTTOM, border=3)

        # Position simulation
        sizer.Add(dark_label(self, label="模拟当前位置 (节点ID):"), proportion=0,
                 flag=wx.TOP, border=4)
        pos_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._pos_entry = dark_text(self, style=0)
        self._pos_entry.SetMinSize(wx.Size(120, -1))
        pos_sizer.Add(self._pos_entry, proportion=0, flag=wx.RIGHT, border=3)
        update_btn = wx.Button(self, label="更新位置")
        update_btn.Bind(wx.EVT_BUTTON, lambda e: self._update_pos())
        pos_sizer.Add(update_btn, proportion=0, flag=wx.RIGHT, border=3)
        deviate_btn = wx.Button(self, label="模拟偏离")
        deviate_btn.Bind(wx.EVT_BUTTON, lambda e: self._simulate_deviation())
        pos_sizer.Add(deviate_btn)
        sizer.Add(pos_sizer, proportion=0, flag=wx.BOTTOM, border=3)

        # --- Alerts ---
        sizer.Add(dark_label(self, label="导航警报"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        self._alert_list = dark_listbox(self)
        self._alert_list.SetMinSize(wx.Size(-1, 80))
        sizer.Add(self._alert_list, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        reroute_btn = wx.Button(self, label="🔄 重新规划路线")
        reroute_btn.Bind(wx.EVT_BUTTON, lambda e: self._reroute())
        sizer.Add(reroute_btn, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        self._progress_label = dark_label(self, label="进度: --")
        sizer.Add(self._progress_label, proportion=0, flag=wx.BOTTOM, border=3)

        self.SetSizer(sizer)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_map_changed(self, scene_id: str):
        """Reset traffic when map changes."""
        self._traffic.clear_all()
        self._nav.stop_navigation()
        self.refresh_traffic_display()
        self._nav_status.SetLabel("未开始导航")

    def _toggle_sim(self):
        """Start/stop traffic simulation."""
        sim = self._app.ensure_traffic_simulator()
        if self._sim_running:
            sim.stop()
            self._sim_running = False
            self._sim_btn.SetLabel("▶ 开始交通模拟")
            self._sim_label.SetLabel("已停止")
        else:
            sim.start(interval_ms=self._interval_slider.GetValue() * 1000)
            self._sim_running = True
            self._sim_btn.SetLabel("⏸ 停止交通模拟")
            self._sim_label.SetLabel("运行中...")

    def refresh_traffic_display(self):
        """Refresh the traffic and blockage displays."""
        self._traffic_list.DeleteAllItems()
        for entry in self._traffic.get_all_congested():
            idx = self._traffic_list.InsertItem(10000,
                entry.get("name", f"{entry['from']}→{entry['to']}"))
            self._traffic_list.SetItem(idx, 1, entry["label"])

        self._blockage_list.Clear()
        for b in self._traffic.get_blockages():
            self._blockage_list.Append(
                f"阻塞: {b.edge_key[0]}→{b.edge_key[1]} - {b.description}")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _start_nav(self):
        """Start navigation along the current path."""
        graph = self._app.get_active_graph()
        path = self._app._current_path
        if not graph or not path:
            self._nav_status.SetLabel("请先规划路径")
            return

        goal = path[-1] if path else ""
        mode = self._app.get_transport_mode()

        self._nav.start_navigation(
            graph, path, goal, mode,
            traffic_service=self._traffic,
            on_alert=self._on_nav_alert,
        )
        self._nav_status.SetLabel("导航中...")
        self._update_progress()

    def _stop_nav(self):
        """Stop navigation."""
        self._nav.stop_navigation()
        self._nav_status.SetLabel("导航已停止")

    def _update_pos(self):
        """Manually update navigation position."""
        node_id = self._pos_entry.GetValue().strip()
        if not node_id:
            return
        on_path = self._nav.update_position(node_id)
        if not on_path:
            self._nav_status.SetLabel("⚠ 偏离路线!")
        self._update_progress()

    def _simulate_deviation(self):
        """Simulate a path deviation for testing."""
        graph = self._app.get_active_graph()
        if not graph:
            return
        all_nodes = graph.get_all_nodes()
        for nid in all_nodes:
            if self._nav._planned_path and nid not in self._nav._planned_path:
                self._pos_entry.SetValue(nid)
                self._nav.update_position(nid)
                self._nav_status.SetLabel("⚠ 偏离路线！请重新规划")
                return

    def _reroute(self):
        """Trigger rerouting."""
        result = self._nav.reroute()
        if result and result["path"]:
            self._app.show_path_on_map(result["path"])
            self._nav_status.SetLabel("已重新规划路线")
            self._update_progress()
        else:
            self._nav_status.SetLabel("重新规划失败")

    def _update_progress(self):
        """Update the progress display."""
        progress = self._nav.get_progress()
        self._progress_label.SetLabel(
            f"进度: {progress['pct']:.1f}% | "
            f"剩余节点: {progress['remaining_nodes']} | "
            f"下一站: {progress.get('next_node', '--')}"
        )

    def _on_nav_alert(self, alert: dict):
        """Callback for navigation alerts."""
        level_emoji = {"info": "ℹ", "warning": "⚠", "danger": "🚨",
                      "success": "✅", "error": "❌"}
        emoji = level_emoji.get(alert["level"], "•")
        self._alert_list.Insert(f"{emoji} {alert['message']}", 0)
        while self._alert_list.GetCount() > 20:
            self._alert_list.Delete(self._alert_list.GetCount() - 1)
