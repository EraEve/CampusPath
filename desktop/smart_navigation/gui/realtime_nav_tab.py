"""Real-time Navigation Tab — traffic display, nav status, alerts, reroute."""

import tkinter as tk
from tkinter import ttk

from ..services.traffic_service import TrafficService
from ..services.navigation_service import NavigationService


class RealtimeNavTab(ttk.Frame):
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
        # --- Traffic Simulation ---
        ttk.Label(self, text="交通模拟", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(5, 2))

        sim_frame = ttk.Frame(self)
        sim_frame.pack(fill=tk.X, pady=2)
        self._sim_btn = ttk.Button(sim_frame, text="▶ 开始交通模拟", command=self._toggle_sim)
        self._sim_btn.pack(side=tk.LEFT, padx=2)
        self._sim_label = ttk.Label(sim_frame, text="已停止", foreground="gray")
        self._sim_label.pack(side=tk.LEFT, padx=5)

        ttk.Label(self, text="模拟间隔 (秒):").pack(anchor=tk.W)
        self._interval_var = tk.IntVar(value=3)
        ttk.Scale(self, from_=1, to=10, variable=self._interval_var,
                 orient=tk.HORIZONTAL, command=self._on_interval_change).pack(fill=tk.X)

        # --- Traffic Status ---
        ttk.Label(self, text="当前路况", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))

        self._traffic_tree = ttk.Treeview(self, columns=("level",),
                                          show="headings", height=5)
        self._traffic_tree.heading("#0", text="路段")
        self._traffic_tree.heading("level", text="状况")
        self._traffic_tree.column("#0", width=220)
        self._traffic_tree.column("level", width=80)
        self._traffic_tree.pack(fill=tk.X, pady=2)

        ttk.Button(self, text="🔄 刷新路况", command=self.refresh_traffic_display).pack(anchor=tk.W, pady=2)

        # --- Active Blockages ---
        ttk.Label(self, text="道路阻塞", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))
        self._blockage_list = tk.Listbox(self, height=4, bg="#1a1a2e", fg="#e74c3c",
                                         font=("SimHei", 9))
        self._blockage_list.pack(fill=tk.X, pady=2)

        # --- Navigation Status ---
        ttk.Label(self, text="导航状态", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))
        self._nav_status = ttk.Label(self, text="未开始导航", foreground="gray")
        self._nav_status.pack(anchor=tk.W)

        # Navigation controls
        nav_btn_frame = ttk.Frame(self)
        nav_btn_frame.pack(fill=tk.X, pady=3)
        ttk.Button(nav_btn_frame, text="▶ 开始导航", command=self._start_nav).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_btn_frame, text="■ 停止导航", command=self._stop_nav).pack(side=tk.LEFT, padx=2)

        # Simulate position
        ttk.Label(self, text="模拟当前位置 (节点ID):").pack(anchor=tk.W, pady=(5, 0))
        pos_frame = ttk.Frame(self)
        pos_frame.pack(fill=tk.X)
        self._pos_var = tk.StringVar()
        ttk.Entry(pos_frame, textvariable=self._pos_var, width=20).pack(side=tk.LEFT)
        ttk.Button(pos_frame, text="更新位置", command=self._update_pos).pack(side=tk.LEFT, padx=4)
        ttk.Button(pos_frame, text="模拟偏离", command=self._simulate_deviation).pack(side=tk.LEFT)

        # --- Alerts ---
        ttk.Label(self, text="导航警报", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))
        self._alert_list = tk.Listbox(self, height=5, bg="#1a1a2e", fg="#ecf0f1",
                                      font=("SimHei", 8))
        self._alert_list.pack(fill=tk.X, pady=2)

        # Reroute button
        ttk.Button(self, text="🔄 重新规划路线", command=self._reroute).pack(fill=tk.X, pady=3)

        # Progress
        self._progress_label = ttk.Label(self, text="进度: --")
        self._progress_label.pack(anchor=tk.W, pady=3)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_map_changed(self, scene_id: str):
        """Reset traffic when map changes."""
        self._traffic.clear_all()
        self._nav.stop_navigation()
        self.refresh_traffic_display()
        self._nav_status.config(text="未开始导航", foreground="gray")

    def _toggle_sim(self):
        """Start/stop traffic simulation."""
        sim = self._app.ensure_traffic_simulator()
        if self._sim_running:
            sim.stop()
            self._sim_running = False
            self._sim_btn.config(text="▶ 开始交通模拟")
            self._sim_label.config(text="已停止", foreground="gray")
        else:
            sim.start(interval_ms=self._interval_var.get() * 1000)
            self._sim_running = True
            self._sim_btn.config(text="⏸ 停止交通模拟")
            self._sim_label.config(text="运行中...", foreground="green")

    def _on_interval_change(self, val):
        """Update simulation interval."""
        if self._sim_running:
            sim = self._app.ensure_traffic_simulator()
            sim.stop()
            sim.start(interval_ms=self._interval_var.get() * 1000)

    def refresh_traffic_display(self):
        """Refresh the traffic and blockage displays."""
        # Traffic tree
        self._traffic_tree.delete(*self._traffic_tree.get_children())
        for entry in self._traffic.get_all_congested():
            self._traffic_tree.insert("", tk.END,
                                     text=entry.get("name", f"{entry['from']}→{entry['to']}"),
                                     values=(entry["label"],))

        # Blockage list
        self._blockage_list.delete(0, tk.END)
        for b in self._traffic.get_blockages():
            self._blockage_list.insert(tk.END,
                f"阻塞: {b.edge_key[0]}→{b.edge_key[1]} - {b.description}")

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _start_nav(self):
        """Start navigation along the current path."""
        graph = self._app.get_active_graph()
        path = self._app._current_path
        if not graph or not path:
            self._nav_status.config(text="请先规划路径", foreground="orange")
            return

        goal = path[-1] if path else ""
        mode = self._app.get_transport_mode()

        self._nav.start_navigation(
            graph, path, goal, mode,
            traffic_service=self._traffic,
            on_alert=self._on_nav_alert,
        )
        self._nav_status.config(text="导航中...", foreground="green")
        self._update_progress()

    def _stop_nav(self):
        """Stop navigation."""
        self._nav.stop_navigation()
        self._nav_status.config(text="导航已停止", foreground="gray")

    def _update_pos(self):
        """Manually update navigation position."""
        node_id = self._pos_var.get().strip()
        if not node_id:
            return
        on_path = self._nav.update_position(node_id)
        if not on_path:
            self._nav_status.config(text="⚠ 偏离路线!", foreground="red")
        self._update_progress()

    def _simulate_deviation(self):
        """Simulate a path deviation for testing."""
        graph = self._app.get_active_graph()
        if not graph:
            return
        # Pick a random node not on the path
        all_nodes = graph.get_all_nodes()
        for nid in all_nodes:
            if self._nav._planned_path and nid not in self._nav._planned_path:
                self._pos_var.set(nid)
                self._nav.update_position(nid)
                self._nav_status.config(text="⚠ 偏离路线！请重新规划", foreground="red")
                return

    def _reroute(self):
        """Trigger rerouting."""
        result = self._nav.reroute()
        if result and result["path"]:
            self._app.show_path_on_map(result["path"])
            self._nav_status.config(text="已重新规划路线", foreground="green")
            self._update_progress()
        else:
            self._nav_status.config(text="重新规划失败", foreground="red")

    def _update_progress(self):
        """Update the progress display."""
        progress = self._nav.get_progress()
        self._progress_label.config(
            text=f"进度: {progress['pct']:.1f}% | "
                 f"剩余节点: {progress['remaining_nodes']} | "
                 f"下一站: {progress.get('next_node', '--')}"
        )

    def _on_nav_alert(self, alert: dict):
        """Callback for navigation alerts."""
        level_emoji = {"info": "ℹ", "warning": "⚠", "danger": "🚨",
                      "success": "✅", "error": "❌"}
        emoji = level_emoji.get(alert["level"], "•")
        self._alert_list.insert(0, f"{emoji} {alert['message']}")
        # Keep only last 20
        while self._alert_list.size() > 20:
            self._alert_list.delete(tk.END)
