"""Path Comparison Panel — multi-algorithm benchmarking."""

import tkinter as tk
from tkinter import ttk

from ..services.path_service import PathService
from ..models.transport import TransportMode


class ComparisonPanel(ttk.Frame):
    """Tab 6: Multi-algorithm path comparison with results table."""

    def __init__(self, parent, app, path_service: PathService):
        super().__init__(parent)
        self._app = app
        self._path_service = path_service
        self._build_ui()

    def _build_ui(self):
        # --- Inputs ---
        ttk.Label(self, text="起点", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(5, 0))
        self._start_var = tk.StringVar()
        self._start_combo = ttk.Combobox(self, textvariable=self._start_var, width=38)
        self._start_combo.pack(fill=tk.X, pady=2)

        ttk.Label(self, text="终点", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(5, 0))
        self._end_var = tk.StringVar()
        self._end_combo = ttk.Combobox(self, textvariable=self._end_var, width=38)
        self._end_combo.pack(fill=tk.X, pady=2)

        # --- Mode ---
        ttk.Label(self, text="交通方式").pack(anchor=tk.W)
        self._mode_var = tk.StringVar(value="walking")
        mode_frame = ttk.Frame(self)
        mode_frame.pack(fill=tk.X, pady=2)
        for text, val in [("🚶步行", "walking"), ("🚗驾车", "driving"), ("🚌公交", "bus")]:
            ttk.Radiobutton(mode_frame, text=text, variable=self._mode_var,
                           value=val).pack(side=tk.LEFT, padx=2)

        # --- Compare button ---
        ttk.Button(self, text="📊 比较所有算法", command=self._run_comparison).pack(fill=tk.X, pady=8)

        # --- Results table ---
        columns = ("algorithm", "distance", "time", "cost", "nodes", "ms")
        self._result_tree = ttk.Treeview(self, columns=columns, show="headings", height=10)
        self._result_tree.heading("algorithm", text="算法")
        self._result_tree.heading("distance", text="距离(m)")
        self._result_tree.heading("time", text="时间(s)")
        self._result_tree.heading("cost", text="费用")
        self._result_tree.heading("nodes", text="路径节点")
        self._result_tree.heading("ms", text="耗时(ms)")

        self._result_tree.column("algorithm", width=120)
        self._result_tree.column("distance", width=70)
        self._result_tree.column("time", width=60)
        self._result_tree.column("cost", width=50)
        self._result_tree.column("nodes", width=60)
        self._result_tree.column("ms", width=70)
        self._result_tree.pack(fill=tk.X, pady=3)

        self._result_tree.bind("<<TreeviewSelect>>", self._on_result_select)

        # --- Highlight selected ---
        ttk.Button(self, text="🗺 在地图上显示选中路径",
                  command=self._show_on_map).pack(fill=tk.X, pady=3)

        # --- Summary ---
        self._summary_text = tk.Text(self, height=5, width=40,
                                     bg="#1a1a2e", fg="#ecf0f1",
                                     font=("Consolas", 8))
        self._summary_text.pack(fill=tk.X)

        self._results = []

    def on_map_changed(self, scene_id: str):
        """Update node lists."""
        graph = self._app.get_active_graph()
        if not graph:
            return
        nodes = graph.get_all_nodes()
        names = [f"{nid} - {graph.get_node(nid).name}" for nid in nodes]
        self._start_combo["values"] = names
        self._end_combo["values"] = names

    def _parse_node_id(self, s: str) -> str:
        """Extract node ID from 'N001 - Name' format."""
        if " - " in s:
            return s.split(" - ")[0].strip()
        return s.strip()

    def _run_comparison(self):
        """Run all algorithms and display comparison."""
        start_id = self._parse_node_id(self._start_var.get())
        goal_id = self._parse_node_id(self._end_var.get())

        if not start_id or not goal_id:
            return

        graph = self._app.get_active_graph()
        if not graph:
            return

        mode_str = self._mode_var.get()
        try:
            mode = TransportMode(mode_str)
        except ValueError:
            mode = TransportMode.WALKING

        self._results = self._path_service.compare_algorithms(
            graph, start_id, goal_id, mode,
        )

        # Display
        self._result_tree.delete(*self._result_tree.get_children())
        self._summary_text.delete("1.0", tk.END)

        best_dist = float("inf")
        best_algo = ""

        for r in self._results:
            if not r.is_reachable:
                continue
            self._result_tree.insert("", tk.END, iid=r.algorithm,
                                    values=(
                                        r.algorithm,
                                        f"{r.total_distance:.0f}",
                                        f"{r.total_time:.0f}",
                                        f"{r.total_cost:.2f}",
                                        str(r.path_length),
                                        f"{r.execution_time_ms:.2f}",
                                    ))
            if r.total_distance < best_dist:
                best_dist = r.total_distance
                best_algo = r.algorithm

        if best_algo:
            self._summary_text.insert("1.0",
                f"🏆 最佳算法: {best_algo}\n"
                f"📏 最短距离: {best_dist:.0f} m\n"
                f"📊 共比较 {len([r for r in self._results if r.is_reachable])} 个算法\n"
            )

    def _on_result_select(self, event):
        """Result row selected."""
        pass

    def _show_on_map(self):
        """Display the selected result path on the map."""
        sel = self._result_tree.selection()
        if not sel:
            return

        for r in self._results:
            if r.algorithm == sel[0] and r.is_reachable:
                self._app.show_path_on_map(r.path)
                break
