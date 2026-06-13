"""Main Application Window — tkinter GUI shell.

Creates the main window with menu bar, tabbed control panel,
map canvas, and status bar. Wires together all services and tabs.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from ..core.map_manager import MapManager
from ..core.graph import NavGraph
from ..services.path_service import PathService
from ..services.search_service import SearchService
from ..services.traffic_service import TrafficService
from ..services.vehicle_service import VehicleService
from ..services.navigation_service import NavigationService
from ..simulation.traffic_simulator import TrafficSimulator
from ..simulation.vehicle_simulator import VehicleSimulator
from ..models.transport import TransportMode
from ..models.traffic import CongestionLevel

from .map_canvas import MapCanvas
from .path_planning_tab import PathPlanningTab
from .map_management_tab import MapManagementTab
from .realtime_nav_tab import RealtimeNavTab
from .nearby_search_tab import NearbySearchTab
from .vehicle_monitor_tab import VehicleMonitorTab
from .comparison_panel import ComparisonPanel


class AppWindow:
    """Main Smart Navigation application window."""

    def __init__(
        self,
        map_manager: MapManager,
        path_service: PathService,
        search_service: SearchService,
        traffic_service: TrafficService,
        vehicle_service: VehicleService,
        navigation_service: NavigationService,
    ):
        self._map_manager = map_manager
        self._path_service = path_service
        self._search_service = search_service
        self._traffic_service = traffic_service
        self._vehicle_service = vehicle_service
        self._navigation_service = navigation_service

        # Active state
        self._active_scene_id: Optional[str] = None
        self._active_graph: Optional[NavGraph] = None
        self._current_path: list = []
        self._transport_mode = TransportMode.WALKING

        # Simulators (created lazily)
        self._traffic_sim: Optional[TrafficSimulator] = None
        self._vehicle_sim: Optional[VehicleSimulator] = None

        # Build UI
        self._root = tk.Tk()
        self._root.title("智慧导航 Smart Navigation v1.0")
        self._root.geometry("1400x800")
        self._root.minsize(1024, 600)

        # Configure ttk theme
        style = ttk.Style()
        style.theme_use("clam")

        # Variables needed by menu (must exist before _build_menu)
        self._labels_var = tk.BooleanVar(value=True)

        self._build_menu()
        self._build_layout()
        self._build_status_bar()

        # Load first map
        scenes = self._map_manager.list_scenes()
        if scenes:
            self._switch_map(scenes[0].scene_id)

        # Protocol
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self):
        """Build the main layout: control panel | map canvas."""
        # Main container
        main_frame = ttk.Frame(self._root)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left control panel (notebook with tabs)
        self._notebook = ttk.Notebook(main_frame, width=380)
        self._notebook.pack(side=tk.LEFT, fill=tk.Y, padx=(3, 0), pady=3)

        # --- Build all 6 tabs ---
        self._path_tab = PathPlanningTab(
            self._notebook, self,
            self._map_manager, self._path_service,
        )
        self._notebook.add(self._path_tab, text="🚏 路径规划")

        self._map_tab = MapManagementTab(
            self._notebook, self,
            self._map_manager,
        )
        self._notebook.add(self._map_tab, text="🗺 地图管理")

        self._nav_tab = RealtimeNavTab(
            self._notebook, self,
            self._traffic_service, self._navigation_service,
        )
        self._notebook.add(self._nav_tab, text="📡 实时导航")

        self._search_tab = NearbySearchTab(
            self._notebook, self,
            self._search_service,
        )
        self._notebook.add(self._search_tab, text="🔍 查找附近")

        self._vehicle_tab = VehicleMonitorTab(
            self._notebook, self,
            self._vehicle_service,
        )
        self._notebook.add(self._vehicle_tab, text="🚗 车辆监管")

        self._compare_tab = ComparisonPanel(
            self._notebook, self,
            self._path_service,
        )
        self._notebook.add(self._compare_tab, text="📊 路径比较")

        # Right side: canvas area
        canvas_frame = ttk.Frame(main_frame)
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=3)

        # Toolbar
        toolbar = ttk.Frame(canvas_frame)
        toolbar.pack(fill=tk.X, pady=(0, 2))

        ttk.Button(toolbar, text="🔍+", width=4,
                   command=self._zoom_in).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar, text="🔍-", width=4,
                   command=self._zoom_out).pack(side=tk.LEFT, padx=1)
        ttk.Button(toolbar, text="↺ 适应", width=6,
                   command=self._fit_view).pack(side=tk.LEFT, padx=1)

        self._zoom_label = ttk.Label(toolbar, text="100%", width=8)
        self._zoom_label.pack(side=tk.LEFT, padx=5)

        # Layer toggles
        ttk.Checkbutton(toolbar, text="标签", variable=self._labels_var,
                        command=self._toggle_labels).pack(side=tk.LEFT, padx=3)

        # Map combo in toolbar
        ttk.Label(toolbar, text="  地图:").pack(side=tk.LEFT, padx=(20, 2))
        self._map_combo = ttk.Combobox(toolbar, state="readonly", width=20)
        self._map_combo.pack(side=tk.LEFT, padx=2)
        self._map_combo.bind("<<ComboboxSelected>>", self._on_map_combo_select)

        # Canvas
        self._canvas = MapCanvas(canvas_frame, width=800, height=600)
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._canvas.set_node_click_callback(self._on_canvas_node_click)

    def _build_menu(self):
        """Build the menu bar."""
        menubar = tk.Menu(self._root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="加载所有地图", command=self._load_all_maps)
        file_menu.add_command(label="重置视图", command=self._fit_view)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=file_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="放大", command=self._zoom_in)
        view_menu.add_command(label="缩小", command=self._zoom_out)
        view_menu.add_command(label="适应窗口", command=self._fit_view)
        view_menu.add_separator()
        view_menu.add_checkbutton(label="显示标签", variable=self._labels_var,
                                  command=self._toggle_labels)
        menubar.add_cascade(label="视图", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

        self._root.config(menu=menubar)

    def _build_status_bar(self):
        """Build status bar at the bottom."""
        status_frame = ttk.Frame(self._root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(0, 0))

        self._status_map = ttk.Label(status_frame, text="未加载地图", relief=tk.SUNKEN, anchor=tk.W)
        self._status_map.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=1)

        self._status_info = ttk.Label(status_frame, text="就绪", relief=tk.SUNKEN, anchor=tk.CENTER, width=30)
        self._status_info.pack(side=tk.LEFT, padx=1)

        self._status_stats = ttk.Label(status_frame, text="", relief=tk.SUNKEN, anchor=tk.E, width=25)
        self._status_stats.pack(side=tk.RIGHT, padx=1)

    # ------------------------------------------------------------------
    # Map switching
    # ------------------------------------------------------------------

    def _switch_map(self, scene_id: str):
        """Switch to a different map scene."""
        graph = self._map_manager.get_graph(scene_id)
        scene = self._map_manager.get_scene(scene_id)
        if graph is None:
            return

        self._active_scene_id = scene_id
        self._active_graph = graph
        self._traffic_service.set_graph(graph)
        self._vehicle_service.set_graph(graph)

        self._canvas.set_graph(graph)
        self._canvas.clear_highlights()
        self._canvas.fit_to_view()

        # Update transports
        if scene:
            self._status_map.config(text=f"地图: {scene.name} ({scene.scene_type})")
            self._status_stats.config(
                text=f"节点: {graph.total_vertices} | 边: {graph.total_edges}"
            )

        # Update map combo
        scenes = self._map_manager.list_scenes()
        self._map_combo["values"] = [s.name for s in scenes]
        for i, s in enumerate(scenes):
            if s.scene_id == scene_id:
                self._map_combo.current(i)
                break

        # Notify tabs
        self._path_tab.on_map_changed(scene_id)
        self._nav_tab.on_map_changed(scene_id)
        self._search_tab.on_map_changed(scene_id)
        self._vehicle_tab.on_map_changed(scene_id)
        self._compare_tab.on_map_changed(scene_id)

        self._set_status("地图已加载")

    def _on_map_combo_select(self, event):
        """Handle map combo selection."""
        idx = self._map_combo.current()
        scenes = self._map_manager.list_scenes()
        if 0 <= idx < len(scenes):
            self._switch_map(scenes[idx].scene_id)

    def _load_all_maps(self):
        """Reload all demo maps."""
        self._map_manager.load_all_demo_maps()
        scenes = self._map_manager.list_scenes()
        if scenes:
            self._switch_map(scenes[0].scene_id)
        self._set_status(f"已加载 {len(scenes)} 个地图")

    # ------------------------------------------------------------------
    # Events from tabs
    # ------------------------------------------------------------------

    def _on_canvas_node_click(self, node_id: str):
        """Handle click on a canvas node."""
        self._set_status(f"点击节点: {node_id}")
        # Notify path planning tab
        self._path_tab.on_node_clicked(node_id)

    def show_path_on_map(self, path: list, start: str = None, goal: str = None):
        """Display a computed path on the canvas."""
        self._current_path = path
        self._canvas.show_path(path, start, goal)
        if path:
            self._set_status(f"路径已显示: {len(path)} 个节点, "
                           f"{len(path)-1} 段")

    def get_active_graph(self) -> Optional[NavGraph]:
        """Return the currently active graph."""
        return self._active_graph

    def get_active_scene_id(self) -> Optional[str]:
        """Return the currently active scene ID."""
        return self._active_scene_id

    def set_transport_mode(self, mode: TransportMode):
        """Set the active transport mode."""
        self._transport_mode = mode

    def get_transport_mode(self) -> TransportMode:
        """Get the active transport mode."""
        return self._transport_mode

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _set_status(self, msg: str):
        """Update the status bar message."""
        self._status_info.config(text=msg)

    def set_status(self, msg: str):
        """Public method to set status."""
        self._set_status(msg)

    # ------------------------------------------------------------------
    # View controls
    # ------------------------------------------------------------------

    def _zoom_in(self):
        self._canvas.zoom_in()
        self._update_zoom_label()

    def _zoom_out(self):
        self._canvas.zoom_out()
        self._update_zoom_label()

    def _fit_view(self):
        self._canvas.fit_to_view()
        self._update_zoom_label()

    def _toggle_labels(self):
        self._canvas._show_node_labels = self._labels_var.get()
        self._canvas.render()

    def _update_zoom_label(self):
        pct = int(self._canvas.get_scale() * 100)
        self._zoom_label.config(text=f"{pct}%")

    # ------------------------------------------------------------------
    # Simulators
    # ------------------------------------------------------------------

    def ensure_traffic_simulator(self) -> TrafficSimulator:
        """Get or create the traffic simulator."""
        if self._traffic_sim is None:
            self._traffic_sim = TrafficSimulator(
                self._root, self._active_graph,
                self._traffic_service,
                on_update=self._on_traffic_update,
            )
        return self._traffic_sim

    def ensure_vehicle_simulator(self) -> VehicleSimulator:
        """Get or create the vehicle simulator."""
        if self._vehicle_sim is None:
            self._vehicle_sim = VehicleSimulator(
                self._root, self._active_graph,
                self._vehicle_service,
                on_update=self._on_vehicle_update,
            )
        return self._vehicle_sim

    def _on_traffic_update(self):
        """Called when traffic simulator updates conditions."""
        # Update canvas congestion colors
        for entry in self._traffic_service.get_all_congested():
            edge_key = (entry["from"], entry["to"])
            self._canvas.set_congestion(edge_key, entry["level"])
        self._nav_tab.refresh_traffic_display()

    def _on_vehicle_update(self):
        """Called when vehicle simulator moves vehicles."""
        vehicles = self._vehicle_service.list_vehicles()
        self._canvas.show_vehicles(vehicles)
        self._vehicle_tab.refresh_vehicle_display()

    # ------------------------------------------------------------------
    # Misc
    # ------------------------------------------------------------------

    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "关于 智慧导航",
            "智慧导航 Smart Navigation v1.0\n\n"
            "多场景地图管理 | 多模式路径规划\n"
            "实时导航 | 查找附近 | 车辆监管\n\n"
            "Built with Python + tkinter\n"
            "Data structures: hand-built MinHeap, Queue, Stack\n"
            "Algorithms: Dijkstra, A*, BFS, Bidirectional\n"
            "2026 © Smart Navigation Team"
        )

    def _on_close(self):
        """Clean up and exit."""
        if self._traffic_sim:
            self._traffic_sim.stop()
        if self._vehicle_sim:
            self._vehicle_sim.stop()
        self._root.destroy()

    def run(self):
        """Start the tkinter main loop."""
        self._root.mainloop()

    @property
    def root(self):
        return self._root

    @property
    def canvas(self) -> MapCanvas:
        return self._canvas

    @property
    def map_manager(self) -> MapManager:
        return self._map_manager

    @property
    def path_service(self) -> PathService:
        return self._path_service

    @property
    def search_service(self) -> SearchService:
        return self._search_service

    @property
    def traffic_service(self) -> TrafficService:
        return self._traffic_service

    @property
    def vehicle_service(self) -> VehicleService:
        return self._vehicle_service

    @property
    def navigation_service(self) -> NavigationService:
        return self._navigation_service
