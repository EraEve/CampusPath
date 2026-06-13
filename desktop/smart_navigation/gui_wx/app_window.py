"""Main Application Window — wxPython GUI shell.

Creates the main window with menu bar, tabbed control panel,
map canvas, and status bar. Wires together all services and tabs.
"""

import wx
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
from .theme import (
    hex_to_wx_colour, configure_dark_panel,
    dark_label, dark_combo, dark_checkbox,
)
from .styles import BG_COLOR, TEXT_COLOR


class AppWindow:
    """Main Smart Navigation application window (wxPython)."""

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

        # wx.Application must be created before any wx widgets
        self._app = wx.App()
        self._app.SetAppName("SmartNavigation")

        # Build the frame
        self._frame = wx.Frame(None, title="智慧导航 Smart Navigation v1.0",
                               size=(1400, 800), pos=wx.DefaultPosition)
        self._frame.SetMinSize(wx.Size(1024, 600))
        self._frame.SetBackgroundColour(hex_to_wx_colour(BG_COLOR))
        self._frame.SetForegroundColour(hex_to_wx_colour(TEXT_COLOR))

        # Show labels toggle state
        self._show_labels = True

        self._build_menu()
        self._build_layout()
        self._build_status_bar()

        # Load first map
        scenes = self._map_manager.list_scenes()
        if scenes:
            self._switch_map(scenes[0].scene_id)

        # Close event
        self._frame.Bind(wx.EVT_CLOSE, self._on_close)

    # ------------------------------------------------------------------
    # Timer adapter (for simulators)
    # ------------------------------------------------------------------

    def _schedule_timer(self, ms: int, callback):
        """Schedule a one-shot timer for simulator use. Returns a token."""
        timer = wx.Timer()
        timer.Bind(wx.EVT_TIMER, lambda evt, cb=callback: cb())
        timer.Start(ms, oneShot=True)
        return timer

    def _cancel_timer(self, token):
        """Cancel a scheduled timer token."""
        if token is not None and token.IsRunning():
            token.Stop()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _build_layout(self):
        """Build the main layout: control panel | map canvas."""
        panel = wx.Panel(self._frame)
        panel.SetBackgroundColour(hex_to_wx_colour(BG_COLOR))

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # Left control panel (notebook with tabs)
        self._notebook = wx.Notebook(panel, style=wx.NB_LEFT)
        self._notebook.SetMinSize(wx.Size(400, -1))

        # --- Build all 6 tabs ---
        self._path_tab = PathPlanningTab(
            self._notebook, self,
            self._map_manager, self._path_service,
        )
        self._notebook.AddPage(self._path_tab, "🚏 路径规划")

        self._map_tab = MapManagementTab(
            self._notebook, self,
            self._map_manager,
        )
        self._notebook.AddPage(self._map_tab, "🗺 地图管理")

        self._nav_tab = RealtimeNavTab(
            self._notebook, self,
            self._traffic_service, self._navigation_service,
        )
        self._notebook.AddPage(self._nav_tab, "📡 实时导航")

        self._search_tab = NearbySearchTab(
            self._notebook, self,
            self._search_service,
        )
        self._notebook.AddPage(self._search_tab, "🔍 查找附近")

        self._vehicle_tab = VehicleMonitorTab(
            self._notebook, self,
            self._vehicle_service,
        )
        self._notebook.AddPage(self._vehicle_tab, "🚗 车辆监管")

        self._compare_tab = ComparisonPanel(
            self._notebook, self,
            self._path_service,
        )
        self._notebook.AddPage(self._compare_tab, "📊 路径比较")

        main_sizer.Add(self._notebook, proportion=0, flag=wx.EXPAND | wx.ALL, border=3)

        # Right side: toolbar + canvas
        right_panel = wx.Panel(panel)
        right_panel.SetBackgroundColour(hex_to_wx_colour(BG_COLOR))
        right_sizer = wx.BoxSizer(wx.VERTICAL)

        # Toolbar
        toolbar = wx.Panel(right_panel)
        toolbar.SetBackgroundColour(hex_to_wx_colour(BG_COLOR))
        toolbar_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._zoom_in_btn = wx.Button(toolbar, label="🔍+", size=(40, 28))
        self._zoom_in_btn.Bind(wx.EVT_BUTTON, lambda e: self._zoom_in())
        toolbar_sizer.Add(self._zoom_in_btn, proportion=0, flag=wx.RIGHT, border=2)

        self._zoom_out_btn = wx.Button(toolbar, label="🔍-", size=(40, 28))
        self._zoom_out_btn.Bind(wx.EVT_BUTTON, lambda e: self._zoom_out())
        toolbar_sizer.Add(self._zoom_out_btn, proportion=0, flag=wx.RIGHT, border=2)

        self._fit_btn = wx.Button(toolbar, label="↺ 适应", size=(60, 28))
        self._fit_btn.Bind(wx.EVT_BUTTON, lambda e: self._fit_view())
        toolbar_sizer.Add(self._fit_btn, proportion=0, flag=wx.RIGHT, border=10)

        self._zoom_label = dark_label(toolbar, label="100%")
        toolbar_sizer.Add(self._zoom_label, proportion=0,
                          flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=10)

        self._labels_cb = dark_checkbox(toolbar, label="标签")
        self._labels_cb.SetValue(True)
        self._labels_cb.Bind(wx.EVT_CHECKBOX, lambda e: self._toggle_labels())
        toolbar_sizer.Add(self._labels_cb, proportion=0,
                          flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=10)

        map_lbl = dark_label(toolbar, label="地图:")
        toolbar_sizer.Add(map_lbl, proportion=0,
                          flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=3)

        self._map_combo = dark_combo(toolbar, choices=[], style=wx.CB_READONLY)
        self._map_combo.SetMinSize(wx.Size(150, -1))
        self._map_combo.Bind(wx.EVT_COMBOBOX, self._on_map_combo_select)
        toolbar_sizer.Add(self._map_combo, proportion=0,
                          flag=wx.ALIGN_CENTER_VERTICAL)

        toolbar.SetSizer(toolbar_sizer)
        right_sizer.Add(toolbar, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        # Canvas
        self._canvas = MapCanvas(right_panel)
        self._canvas.set_node_click_callback(self._on_canvas_node_click)
        right_sizer.Add(self._canvas, proportion=1, flag=wx.EXPAND)

        right_panel.SetSizer(right_sizer)
        main_sizer.Add(right_panel, proportion=1, flag=wx.EXPAND | wx.ALL, border=3)

        panel.SetSizer(main_sizer)

    def _build_menu(self):
        """Build the menu bar."""
        menubar = wx.MenuBar()

        file_menu = wx.Menu()
        self._mi_load_all = file_menu.Append(wx.ID_ANY, "加载所有地图\tCtrl+L")
        self._mi_reset_view = file_menu.Append(wx.ID_ANY, "重置视图\tCtrl+R")
        file_menu.AppendSeparator()
        self._mi_exit = file_menu.Append(wx.ID_EXIT, "退出\tCtrl+Q")
        menubar.Append(file_menu, "文件")

        view_menu = wx.Menu()
        self._mi_zoom_in = view_menu.Append(wx.ID_ANY, "放大\tCtrl++")
        self._mi_zoom_out = view_menu.Append(wx.ID_ANY, "缩小\tCtrl+-")
        self._mi_fit_view = view_menu.Append(wx.ID_ANY, "适应窗口\tCtrl+F")
        view_menu.AppendSeparator()
        self._mi_show_labels = view_menu.Append(wx.ID_ANY, "显示标签", kind=wx.ITEM_CHECK)
        self._mi_show_labels.Check(True)
        menubar.Append(view_menu, "视图")

        help_menu = wx.Menu()
        self._mi_about = help_menu.Append(wx.ID_ABOUT, "关于")
        menubar.Append(help_menu, "帮助")

        self._frame.SetMenuBar(menubar)

        # Bind menu events
        self._frame.Bind(wx.EVT_MENU, lambda e: self._load_all_maps(),
                         id=self._mi_load_all.GetId())
        self._frame.Bind(wx.EVT_MENU, lambda e: self._fit_view(),
                         id=self._mi_reset_view.GetId())
        self._frame.Bind(wx.EVT_MENU, lambda e: self._on_close(None),
                         id=self._mi_exit.GetId())

        self._frame.Bind(wx.EVT_MENU, lambda e: self._zoom_in(),
                         id=self._mi_zoom_in.GetId())
        self._frame.Bind(wx.EVT_MENU, lambda e: self._zoom_out(),
                         id=self._mi_zoom_out.GetId())
        self._frame.Bind(wx.EVT_MENU, lambda e: self._fit_view(),
                         id=self._mi_fit_view.GetId())
        self._frame.Bind(wx.EVT_MENU, self._on_toggle_labels_menu,
                         id=self._mi_show_labels.GetId())

        self._frame.Bind(wx.EVT_MENU, lambda e: self._show_about(),
                         id=self._mi_about.GetId())

    def _on_toggle_labels_menu(self, event):
        self._show_labels = event.IsChecked()
        self._labels_cb.SetValue(self._show_labels)
        self._toggle_labels()

    def _build_status_bar(self):
        """Build status bar at the bottom."""
        self._statusbar = self._frame.CreateStatusBar(3)
        self._statusbar.SetStatusText("未加载地图", 0)
        self._statusbar.SetStatusText("就绪", 1)
        self._statusbar.SetStatusText("", 2)

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

        # Update status bar
        if scene:
            self._statusbar.SetStatusText(
                f"地图: {scene.name} ({scene.scene_type})", 0)
            self._statusbar.SetStatusText(
                f"节点: {graph.total_vertices} | 边: {graph.total_edges}", 2)

        # Update map combo
        scenes = self._map_manager.list_scenes()
        self._map_combo.Clear()
        self._map_combo.Set([s.name for s in scenes])
        for i, s in enumerate(scenes):
            if s.scene_id == scene_id:
                self._map_combo.SetSelection(i)
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
        idx = self._map_combo.GetSelection()
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
        self._statusbar.SetStatusText(msg, 1)

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
        show = self._labels_cb.GetValue()
        self._canvas.set_show_labels(show)
        self._canvas.Refresh()

    def _update_zoom_label(self):
        pct = int(self._canvas.get_scale() * 100)
        self._zoom_label.SetLabel(f"{pct}%")

    # ------------------------------------------------------------------
    # Simulators
    # ------------------------------------------------------------------

    def ensure_traffic_simulator(self) -> TrafficSimulator:
        """Get or create the traffic simulator."""
        if self._traffic_sim is None:
            self._traffic_sim = TrafficSimulator(
                graph=self._active_graph,
                traffic_service=self._traffic_service,
                on_update=self._on_traffic_update,
                schedule_timer=self._schedule_timer,
                cancel_timer=self._cancel_timer,
            )
        return self._traffic_sim

    def ensure_vehicle_simulator(self) -> VehicleSimulator:
        """Get or create the vehicle simulator."""
        if self._vehicle_sim is None:
            self._vehicle_sim = VehicleSimulator(
                graph=self._active_graph,
                vehicle_service=self._vehicle_service,
                on_update=self._on_vehicle_update,
                schedule_timer=self._schedule_timer,
                cancel_timer=self._cancel_timer,
            )
        return self._vehicle_sim

    def _on_traffic_update(self):
        """Called when traffic simulator updates conditions."""
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
        wx.MessageBox(
            "智慧导航 Smart Navigation v1.0\n\n"
            "多场景地图管理 | 多模式路径规划\n"
            "实时导航 | 查找附近 | 车辆监管\n\n"
            "Built with Python + wxPython\n"
            "Data structures: hand-built MinHeap, Queue, Stack\n"
            "Algorithms: Dijkstra, A*, BFS, Bidirectional\n"
            "2026 © Smart Navigation Team",
            "关于 智慧导航",
            wx.OK | wx.ICON_INFORMATION
        )

    def _on_close(self, event):
        """Clean up and exit."""
        if self._traffic_sim:
            self._traffic_sim.stop()
        if self._vehicle_sim:
            self._vehicle_sim.stop()
        if event:
            self._frame.Destroy()

    def run(self):
        """Start the wxPython main loop."""
        self._frame.Show()
        self._app.MainLoop()

    @property
    def root(self):
        return self._frame

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
