"""Path Planning Tab — route planning controls and result display."""

import tkinter as tk
from tkinter import ttk
from typing import Optional

from ..core.map_manager import MapManager
from ..services.path_service import PathService
from ..models.transport import TransportMode


class PathPlanningTab(ttk.Frame):
    """Tab 1: Path Planning with start/end/waypoint selection."""

    def __init__(self, parent, app, map_manager: MapManager, path_service: PathService):
        super().__init__(parent)
        self._app = app
        self._map_manager = map_manager
        self._path_service = path_service

        self._start_var = tk.StringVar()
        self._end_var = tk.StringVar()
        self._via_var = tk.StringVar()
        self._mode_var = tk.StringVar(value="walking")
        self._algo_var = tk.StringVar(value="dijkstra")
        self._heuristic_var = tk.StringVar(value="euclidean")
        self._highway_var = tk.BooleanVar(value=False)
        self._congestion_var = tk.BooleanVar(value=False)
        self._multi_criteria_var = tk.BooleanVar(value=False)

        self._node_list: list = []
        self._build_ui()

    def _build_ui(self):
        # Scrollable frame
        canvas = tk.Canvas(self, width=360, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)

        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind mousewheel to canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        f = scroll_frame

        # --- Transport mode ---
        ttk.Label(f, text="出行方式", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))
        mode_frame = ttk.Frame(f)
        mode_frame.pack(fill=tk.X, pady=2)
        modes = [("🚗 驾车", "driving"), ("🚶 步行", "walking"), ("🚌 公交", "bus"),
                 ("🚄 火车", "train"), ("🚇 地铁", "subway")]
        for text, val in modes:
            ttk.Radiobutton(mode_frame, text=text, variable=self._mode_var,
                           value=val, command=self._on_mode_change).pack(side=tk.LEFT, padx=2)

        # --- Start / End ---
        ttk.Label(f, text="起点", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 0))
        self._start_combo = ttk.Combobox(f, textvariable=self._start_var, width=40)
        self._start_combo.pack(fill=tk.X, pady=2)

        ttk.Label(f, text="终点", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 0))
        self._end_combo = ttk.Combobox(f, textvariable=self._end_var, width=40)
        self._end_combo.pack(fill=tk.X, pady=2)

        ttk.Label(f, text="途经点 (可选，分号分隔)", font=("SimHei", 9)).pack(anchor=tk.W, pady=(6, 0))
        ttk.Entry(f, textvariable=self._via_var, width=42).pack(fill=tk.X, pady=2)

        # --- Algorithm ---
        ttk.Label(f, text="算法选择", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))
        algo_frame = ttk.Frame(f)
        algo_frame.pack(fill=tk.X)
        algos = ["dijkstra", "a_star", "bfs", "bidirectional_dijkstra",
                 "bidirectional_bfs", "congestion_avoidance", "multi_criteria"]
        algo_labels = {
            "dijkstra": "Dijkstra", "a_star": "A*", "bfs": "BFS",
            "bidirectional_dijkstra": "双向Dijkstra", "bidirectional_bfs": "双向BFS",
            "congestion_avoidance": "避拥堵", "multi_criteria": "多指标",
        }
        self._algo_combo = ttk.Combobox(
            algo_frame, textvariable=self._algo_var,
            values=algos, state="readonly", width=25,
        )
        self._algo_combo.pack(side=tk.LEFT)
        # Format display
        self._algo_combo["values"] = [f"{a} - {algo_labels.get(a, a)}" for a in algos]
        self._algo_combo.bind("<<ComboboxSelected>>", self._on_algo_change)

        # Heuristic (for A*)
        heur_frame = ttk.Frame(f)
        heur_frame.pack(fill=tk.X, pady=2)
        ttk.Label(heur_frame, text="启发函数:").pack(side=tk.LEFT)
        ttk.Combobox(heur_frame, textvariable=self._heuristic_var,
                    values=["euclidean", "manhattan", "floor_aware"],
                    state="readonly", width=14).pack(side=tk.LEFT, padx=4)

        # --- Options ---
        ttk.Label(f, text="路径选项", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))
        ttk.Checkbutton(f, text="高速优先", variable=self._highway_var).pack(anchor=tk.W)
        ttk.Checkbutton(f, text="避让拥堵", variable=self._congestion_var).pack(anchor=tk.W)
        ttk.Checkbutton(f, text="多指标优化 (距离/时间/费用)", variable=self._multi_criteria_var).pack(anchor=tk.W)

        # --- Multi-criteria weights ---
        self._mc_frame = ttk.LabelFrame(f, text="多指标权重")
        self._mc_frame.pack(fill=tk.X, pady=5)
        ttk.Label(self._mc_frame, text="距离权重").pack(anchor=tk.W)
        self._w_dist = ttk.Scale(self._mc_frame, from_=0, to=1.0, value=0.4)
        self._w_dist.pack(fill=tk.X)
        ttk.Label(self._mc_frame, text="时间权重").pack(anchor=tk.W)
        self._w_time = ttk.Scale(self._mc_frame, from_=0, to=1.0, value=0.4)
        self._w_time.pack(fill=tk.X)
        ttk.Label(self._mc_frame, text="费用权重").pack(anchor=tk.W)
        self._w_cost = ttk.Scale(self._mc_frame, from_=0, to=1.0, value=0.2)
        self._w_cost.pack(fill=tk.X)

        # --- Find Path button ---
        ttk.Button(f, text="🔍 查找路径", command=self._find_path).pack(fill=tk.X, pady=10)

        # --- Results ---
        self._result_frame = ttk.LabelFrame(f, text="路径结果")
        self._result_frame.pack(fill=tk.X, pady=5)

        self._result_text = tk.Text(self._result_frame, height=10, width=40,
                                    bg="#1a1a2e", fg="#ecf0f1",
                                    font=("Consolas", 9))
        self._result_text.pack(fill=tk.X)

        # --- History ---
        ttk.Label(f, text="历史记录", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(6, 0))
        self._history_list = tk.Listbox(f, height=5, bg="#1a1a2e", fg="#ecf0f1")
        self._history_list.pack(fill=tk.X, pady=2)
        self._history_list.bind("<<ListboxSelect>>", self._on_history_select)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_map_changed(self, scene_id: str):
        """Called when the active map changes."""
        nodes = self._map_manager.get_all_nodes_for_scene(scene_id)
        self._node_list = nodes
        names = [f"{n['node_id']} - {n['name']}" for n in nodes]
        self._start_combo["values"] = names
        self._end_combo["values"] = names
        self._start_var.set("")
        self._end_var.set("")

    def on_node_clicked(self, node_id: str):
        """Called when a node is clicked on the canvas."""
        # Set as start or end depending on what's empty
        if not self._start_var.get():
            self._start_var.set(node_id)
        elif not self._end_var.get():
            self._end_var.set(node_id)

    def _on_mode_change(self):
        """Transport mode changed."""
        mode_str = self._mode_var.get()
        try:
            mode = TransportMode(mode_str)
            self._app.set_transport_mode(mode)
        except ValueError:
            pass

    def _on_algo_change(self, event=None):
        """Algorithm selection changed."""
        selection = self._algo_combo.get()
        if "a_star" in selection:
            self._algo_var.set("a_star")
        elif "bidirectional_dijkstra" in selection:
            self._algo_var.set("bidirectional_dijkstra")
        elif "bidirectional_bfs" in selection:
            self._algo_var.set("bidirectional_bfs")
        elif "congestion" in selection:
            self._algo_var.set("congestion_avoidance")
        elif "multi" in selection:
            self._algo_var.set("multi_criteria")
        else:
            self._algo_var.set("dijkstra")

    # ------------------------------------------------------------------
    # Path finding
    # ------------------------------------------------------------------

    def _find_path(self):
        """Execute pathfinding."""
        start_str = self._start_var.get()
        end_str = self._end_var.get()

        # Extract node ID from "N001 - Name" format
        if " - " in start_str:
            start_id = start_str.split(" - ")[0].strip()
        else:
            start_id = start_str.strip()

        if " - " in end_str:
            goal_id = end_str.split(" - ")[0].strip()
        else:
            goal_id = end_str.strip()

        if not start_id or not goal_id:
            self._result_text.delete("1.0", tk.END)
            self._result_text.insert("1.0", "请选择起点和终点")
            return

        graph = self._app.get_active_graph()
        if graph is None:
            return

        mode_str = self._mode_var.get()
        try:
            mode = TransportMode(mode_str)
        except ValueError:
            mode = TransportMode.WALKING

        algo = self._algo_var.get()
        if not algo:
            algo = "dijkstra"

        # Parse waypoints
        via_str = self._via_var.get().strip()
        waypoints = None
        if via_str:
            waypoints = [w.strip() for w in via_str.split(";") if w.strip()]

        try:
            result = self._path_service.find_path(
                graph, start_id, goal_id,
                transport_mode=mode,
                algorithm=algo,
                heuristic=self._heuristic_var.get(),
                waypoints=waypoints,
                highway_priority=self._highway_var.get(),
                congestion_avoidance=self._congestion_var.get(),
                multi_criteria=self._multi_criteria_var.get(),
                w_distance=self._w_dist.get(),
                w_time=self._w_time.get(),
                w_cost=self._w_cost.get(),
            )
        except Exception as e:
            self._result_text.delete("1.0", tk.END)
            self._result_text.insert("1.0", f"错误: {e}")
            return

        # Display result
        self._result_text.delete("1.0", tk.END)
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

        self._result_text.insert("1.0", text)

        # Show on canvas
        if result.is_reachable:
            self._app.show_path_on_map(result.path, start_id, goal_id)

        # Update history
        self._refresh_history()

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def _refresh_history(self):
        """Update the history listbox."""
        self._history_list.delete(0, tk.END)
        for entry in self._path_service.get_history()[:10]:
            start_name = self._get_node_name(entry.path[0]) if entry.path else "?"
            goal_name = self._get_node_name(entry.path[-1]) if entry.path else "?"
            label = f"{start_name} → {goal_name} ({entry.total_distance:.0f}m)"
            self._history_list.insert(tk.END, label)

    def _on_history_select(self, event):
        """Replay a historical path."""
        sel = self._history_list.curselection()
        if not sel:
            return
        idx = sel[0]
        history = self._path_service.get_history()
        if idx < len(history):
            result = history[idx]
            if result.is_reachable:
                self._app.show_path_on_map(result.path)
                self._start_var.set(result.path[0] if result.path else "")
                self._end_var.set(result.path[-1] if result.path else "")

    def _get_node_name(self, node_id: str) -> str:
        """Get human-readable node name."""
        graph = self._app.get_active_graph()
        if graph:
            node = graph.get_node(node_id)
            if node:
                return node.name
        return node_id
