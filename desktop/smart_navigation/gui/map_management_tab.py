"""Map Management Tab — map CRUD, scene switching, and simple editor."""

import tkinter as tk
from tkinter import ttk, messagebox

from ..core.map_manager import MapManager
from ..models.transport import SceneType


class MapManagementTab(ttk.Frame):
    """Tab 2: Map Management with scene listing, info, and map editor."""

    def __init__(self, parent, app, map_manager: MapManager):
        super().__init__(parent)
        self._app = app
        self._map_manager = map_manager
        self._build_ui()

    def _build_ui(self):
        # Scene filter
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(filter_frame, text="场景类型:").pack(side=tk.LEFT)
        self._filter_var = tk.StringVar(value="全部")
        filter_combo = ttk.Combobox(filter_frame, textvariable=self._filter_var,
                                   values=["全部", "室外校园", "室内商场", "室外城市", "地下通道"],
                                   state="readonly", width=15)
        filter_combo.pack(side=tk.LEFT, padx=4)
        filter_combo.bind("<<ComboboxSelected>>", self._refresh_maps)

        # Map list
        self._map_tree = ttk.Treeview(self, columns=("type", "nodes", "edges"),
                                      show="headings", height=8)
        self._map_tree.heading("#0", text="地图名称")
        self._map_tree.heading("type", text="类型")
        self._map_tree.heading("nodes", text="节点")
        self._map_tree.heading("edges", text="边")
        self._map_tree.column("#0", width=140)
        self._map_tree.column("type", width=80)
        self._map_tree.column("nodes", width=50)
        self._map_tree.column("edges", width=50)
        self._map_tree.pack(fill=tk.X, pady=5)
        self._map_tree.bind("<<TreeviewSelect>>", self._on_map_select)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, pady=3)
        ttk.Button(btn_frame, text="加载选中", command=self._load_selected).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text="刷新列表", command=self._refresh_maps).pack(side=tk.LEFT, padx=2)

        # Map info
        self._info_frame = ttk.LabelFrame(self, text="地图信息")
        self._info_frame.pack(fill=tk.X, pady=5)

        self._info_text = tk.Text(self._info_frame, height=8, width=40,
                                  bg="#1a1a2e", fg="#ecf0f1",
                                  font=("SimHei", 9))
        self._info_text.pack(fill=tk.X)

        # Transport modes
        ttk.Label(self, text="支持交通方式", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))
        self._modes_frame = ttk.Frame(self)
        self._modes_frame.pack(fill=tk.X)

        # Scene comparison
        ttk.Label(self, text="场景统计", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))
        self._stats_text = tk.Text(self, height=6, width=40,
                                   bg="#1a1a2e", fg="#ecf0f1",
                                   font=("SimHei", 9))
        self._stats_text.pack(fill=tk.X)

        self._refresh_maps()

    def on_map_changed(self, scene_id: str):
        """Update when active map changes."""
        self._refresh_maps()
        self._show_map_info(scene_id)

    def _refresh_maps(self, event=None):
        """Reload the map list."""
        self._map_tree.delete(*self._map_tree.get_children())
        filter_val = self._filter_var.get()

        for scene in self._map_manager.list_scenes():
            scene_label = str(scene.scene_type)
            if filter_val != "全部" and filter_val != scene_label:
                continue
            self._map_tree.insert("", tk.END, iid=scene.scene_id,
                                 text=scene.name,
                                 values=(scene_label, scene.node_count, scene.edge_count))

        self._update_stats()

    def _on_map_select(self, event):
        """Map selected in tree."""
        sel = self._map_tree.selection()
        if sel:
            self._show_map_info(sel[0])

    def _show_map_info(self, scene_id: str):
        """Display map details."""
        scene = self._map_manager.get_scene(scene_id)
        graph = self._map_manager.get_graph(scene_id)
        if scene is None:
            return

        self._info_text.delete("1.0", tk.END)
        info = (
            f"名称: {scene.name}\n"
            f"类型: {scene.scene_type}\n"
            f"描述: {scene.description}\n"
            f"节点数: {scene.node_count}\n"
            f"边数: {scene.edge_count}\n"
            f"交通方式: {', '.join(str(m) for m in scene.transport_modes)}\n"
        )
        if graph:
            floors = graph.get_floors()
            info += f"楼层: {floors}\n"
            pois = len(graph.get_poi_nodes())
            info += f"POI数量: {pois}\n"
        self._info_text.insert("1.0", info)

        # Show transport modes
        for widget in self._modes_frame.winfo_children():
            widget.destroy()
        if scene:
            for mode in scene.transport_modes:
                ttk.Label(self._modes_frame, text=f"  {mode}  ",
                         relief=tk.SUNKEN).pack(side=tk.LEFT, padx=2)

    def _load_selected(self):
        """Load the selected map."""
        sel = self._map_tree.selection()
        if sel:
            self._app._switch_map(sel[0])

    def _update_stats(self):
        """Update scene statistics."""
        self._stats_text.delete("1.0", tk.END)
        scenes = self._map_manager.list_scenes()
        total_nodes = sum(s.node_count for s in scenes)
        total_edges = sum(s.edge_count for s in scenes)

        stats = f"地图总数: {len(scenes)}\n"
        stats += f"总节点数: {total_nodes}\n"
        stats += f"总边数: {total_edges}\n"

        for st in SceneType:
            count = len(self._map_manager.get_scenes_by_type(st))
            if count > 0:
                stats += f"  {st}: {count} 个地图\n"

        self._stats_text.insert("1.0", stats)
