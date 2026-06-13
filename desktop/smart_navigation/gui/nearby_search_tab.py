"""Nearby Search Tab — POI proximity search and route-to-POI."""

import tkinter as tk
from tkinter import ttk

from ..services.search_service import SearchService


class NearbySearchTab(ttk.Frame):
    """Tab 4: Nearby POI Search with category filtering and routing."""

    def __init__(self, parent, app, search_service: SearchService):
        super().__init__(parent)
        self._app = app
        self._search = search_service
        self._build_ui()

    def _build_ui(self):
        # --- Search center ---
        ttk.Label(self, text="搜索中心", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(5, 2))
        center_frame = ttk.Frame(self)
        center_frame.pack(fill=tk.X)
        ttk.Label(center_frame, text="节点:").pack(side=tk.LEFT)
        self._center_var = tk.StringVar()
        self._center_combo = ttk.Combobox(center_frame, textvariable=self._center_var, width=28)
        self._center_combo.pack(side=tk.LEFT, padx=3)

        # --- Categories ---
        ttk.Label(self, text="POI类别", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))
        cat_frame = ttk.Frame(self)
        cat_frame.pack(fill=tk.X)
        self._cat_vars = {}
        for cat, emoji in [("scenic", "🏛 景点"), ("food", "🍽 美食"),
                           ("parking", "🅿 停车场"), ("hospital", "🏥 医院")]:
            var = tk.BooleanVar(value=True)
            self._cat_vars[cat] = var
            ttk.Checkbutton(cat_frame, text=emoji, variable=var).pack(side=tk.LEFT, padx=3)

        # --- Radius ---
        ttk.Label(self, text="搜索半径").pack(anchor=tk.W, pady=(5, 0))
        radius_frame = ttk.Frame(self)
        radius_frame.pack(fill=tk.X)
        self._radius_var = tk.DoubleVar(value=float("inf"))
        self._radius_combo = ttk.Combobox(
            radius_frame, textvariable=self._radius_var,
            values=["无限", "100", "200", "300", "500", "1000"],
            state="readonly", width=10,
        )
        self._radius_combo.pack(side=tk.LEFT)
        self._radius_combo.set("无限")

        ttk.Label(radius_frame, text="  最大结果:").pack(side=tk.LEFT)
        self._max_var = tk.IntVar(value=20)
        ttk.Spinbox(radius_frame, from_=1, to=100, textvariable=self._max_var,
                   width=5).pack(side=tk.LEFT, padx=3)

        # --- Search button ---
        ttk.Button(self, text="🔍 搜索附近", command=self._do_search).pack(fill=tk.X, pady=8)

        # --- Results ---
        self._result_tree = ttk.Treeview(
            self, columns=("category", "distance", "direction"),
            show="headings", height=10,
        )
        self._result_tree.heading("#0", text="名称")
        self._result_tree.heading("category", text="类别")
        self._result_tree.heading("distance", text="距离")
        self._result_tree.heading("direction", text="方向")
        self._result_tree.column("#0", width=130)
        self._result_tree.column("category", width=70)
        self._result_tree.column("distance", width=60)
        self._result_tree.column("direction", width=50)
        self._result_tree.pack(fill=tk.X, pady=3)
        self._result_tree.bind("<<TreeviewSelect>>", self._on_result_select)

        # --- Route to selected ---
        ttk.Button(self, text="🚏 规划到此处路径", command=self._route_to_selected).pack(fill=tk.X, pady=3)

        # --- POI Info ---
        self._info_text = tk.Text(self, height=5, width=40,
                                  bg="#1a1a2e", fg="#ecf0f1",
                                  font=("SimHei", 9))
        self._info_text.pack(fill=tk.X, pady=5)

        # --- Category summary ---
        ttk.Label(self, text="POI概览", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(5, 0))
        self._summary_text = tk.Text(self, height=4, width=40,
                                     bg="#1a1a2e", fg="#ecf0f1",
                                     font=("SimHei", 9))
        self._summary_text.pack(fill=tk.X)

    def on_map_changed(self, scene_id: str):
        """Update node list and POI summary when map changes."""
        graph = self._app.get_active_graph()
        if not graph:
            return

        nodes = graph.get_all_nodes()
        names = [f"{nid} - {graph.get_node(nid).name}" for nid in nodes]
        self._center_combo["values"] = names

        # Update POI summary
        self._summary_text.delete("1.0", tk.END)
        for cat_info in self._search.get_poi_categories(graph):
            self._summary_text.insert(tk.END,
                f"  {cat_info['label']}: {cat_info['count']} 个\n")

    def _do_search(self):
        """Execute nearby search."""
        graph = self._app.get_active_graph()
        if not graph:
            return

        # Parse center
        center_str = self._center_var.get()
        if " - " in center_str:
            center_id = center_str.split(" - ")[0].strip()
        else:
            center_id = center_str.strip() if center_str else None

        # Parse categories
        categories = [cat for cat, var in self._cat_vars.items() if var.get()]
        if not categories:
            categories = None

        # Parse radius
        radius_str = self._radius_combo.get()
        radius = float("inf") if radius_str == "无限" else float(radius_str)

        results = self._search.search_nearby(
            graph,
            center_node_id=center_id,
            categories=categories,
            radius=radius,
            max_results=self._max_var.get(),
        )

        # Display
        self._result_tree.delete(*self._result_tree.get_children())
        for r in results:
            self._result_tree.insert("", tk.END, iid=r["node_id"],
                                    text=r["name"],
                                    values=(r["category_label"], f"{r['distance']:.0f}", r["direction"]))

    def _on_result_select(self, event):
        """POI result selected."""
        sel = self._result_tree.selection()
        if not sel:
            return
        results = self._search.get_last_results()
        for r in results:
            if r["node_id"] == sel[0]:
                self._info_text.delete("1.0", tk.END)
                info = (
                    f"名称: {r['name']}\n"
                    f"类别: {r['category_label']}\n"
                    f"距离: {r['distance']:.0f} 单位\n"
                    f"方向: {r['direction']}\n"
                    f"楼层: {r['floor']}\n"
                    f"描述: {r.get('description', '无')}\n"
                )
                self._info_text.insert("1.0", info)

                # Highlight on canvas
                self._app.show_path_on_map([r["node_id"]])
                break

    def _route_to_selected(self):
        """Plan a route from the center to the selected POI."""
        sel = self._result_tree.selection()
        if not sel:
            return

        center_str = self._center_var.get()
        if " - " in center_str:
            center_id = center_str.split(" - ")[0].strip()
        else:
            center_id = center_str.strip()
        poi_id = sel[0]

        if not center_id:
            return

        graph = self._app.get_active_graph()
        if not graph:
            return

        from ..models.transport import TransportMode
        mode = self._app.get_transport_mode()
        result = self._app.path_service.find_path(
            graph, center_id, poi_id, transport_mode=mode,
        )
        if result.is_reachable:
            self._app.show_path_on_map(result.path, center_id, poi_id)
