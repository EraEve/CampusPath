"""Map Management Tab — map CRUD, scene switching, and simple editor (wxPython)."""

import wx

from ..core.map_manager import MapManager
from ..models.transport import SceneType
from .theme import (
    dark_panel, dark_label, dark_button, dark_text, dark_listctrl,
    hex_to_wx_colour,
)
from .styles import PANEL_BG, TEXT_COLOR


class MapManagementTab(wx.Panel):
    """Tab 2: Map Management with scene listing, info, and map editor."""

    def __init__(self, parent, app, map_manager: MapManager):
        super().__init__(parent)
        self._app = app
        self._map_manager = map_manager
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # Scene filter
        filter_sizer = wx.BoxSizer(wx.HORIZONTAL)
        filter_sizer.Add(dark_label(self, label="场景类型:"), proportion=0,
                        flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=4)
        self._filter_combo = wx.ComboBox(self, choices=[
            "全部", "室外校园", "室内商场", "室外城市", "地下通道"],
            style=wx.CB_READONLY)
        self._filter_combo.SetSelection(0)
        self._filter_combo.Bind(wx.EVT_COMBOBOX, self._refresh_maps)
        filter_sizer.Add(self._filter_combo, proportion=1)
        sizer.Add(filter_sizer, proportion=0, flag=wx.EXPAND | wx.ALL, border=3)

        # Map list
        self._map_list = dark_listctrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self._map_list.InsertColumn(0, "地图名称", width=140)
        self._map_list.InsertColumn(1, "类型", width=80)
        self._map_list.InsertColumn(2, "节点", width=50)
        self._map_list.InsertColumn(3, "边", width=50)
        self._map_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_map_select)
        sizer.Add(self._map_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=3)

        # Buttons
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        load_btn = wx.Button(self, label="加载选中")
        load_btn.Bind(wx.EVT_BUTTON, lambda e: self._load_selected())
        btn_sizer.Add(load_btn, proportion=0, flag=wx.RIGHT, border=3)
        refresh_btn = wx.Button(self, label="刷新列表")
        refresh_btn.Bind(wx.EVT_BUTTON, lambda e: self._refresh_maps(None))
        btn_sizer.Add(refresh_btn)
        sizer.Add(btn_sizer, proportion=0, flag=wx.ALL, border=3)

        # Map info
        sizer.Add(dark_label(self, label="地图信息"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        self._info_text = dark_text(self, value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY)
        self._info_text.SetMinSize(wx.Size(-1, 100))
        sizer.Add(self._info_text, proportion=0, flag=wx.EXPAND | wx.ALL, border=3)

        # Transport modes
        sizer.Add(dark_label(self, label="支持交通方式"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        self._modes_panel = wx.Panel(self)
        self._modes_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._modes_panel.SetSizer(self._modes_sizer)
        sizer.Add(self._modes_panel, proportion=0, flag=wx.EXPAND | wx.ALL, border=3)

        # Scene statistics
        sizer.Add(dark_label(self, label="场景统计"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        self._stats_text = dark_text(self, value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY)
        self._stats_text.SetMinSize(wx.Size(-1, 80))
        sizer.Add(self._stats_text, proportion=0, flag=wx.EXPAND | wx.ALL, border=3)

        self.SetSizer(sizer)
        self._refresh_maps()

    def on_map_changed(self, scene_id: str):
        """Update when active map changes."""
        self._refresh_maps()
        self._show_map_info(scene_id)

    def _refresh_maps(self, event=None):
        """Reload the map list."""
        self._map_list.DeleteAllItems()
        filter_val = self._filter_combo.GetValue() if self._filter_combo.GetValue() else "全部"

        for scene in self._map_manager.list_scenes():
            scene_label = str(scene.scene_type)
            if filter_val != "全部" and filter_val != scene_label:
                continue
            idx = self._map_list.InsertItem(10000, scene.name)
            self._map_list.SetItem(idx, 1, scene_label)
            self._map_list.SetItem(idx, 2, str(scene.node_count))
            self._map_list.SetItem(idx, 3, str(scene.edge_count))
            # Store scene_id as item data
            self._map_list.SetItemData(idx, hash(scene.scene_id))

        self._update_stats()

    def _on_map_select(self, event):
        """Map selected in list."""
        idx = event.GetIndex()
        scenes = self._map_manager.list_scenes()
        if 0 <= idx < len(scenes):
            self._show_map_info(scenes[idx].scene_id)

    def _show_map_info(self, scene_id: str):
        """Display map details."""
        scene = self._map_manager.get_scene(scene_id)
        graph = self._map_manager.get_graph(scene_id)
        if scene is None:
            return

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
        self._info_text.SetValue(info)

        # Show transport modes
        self._modes_sizer.Clear(True)
        if scene:
            for mode in scene.transport_modes:
                lbl = dark_label(self._modes_panel, label=f"  {mode}  ")
                self._modes_sizer.Add(lbl, proportion=0, flag=wx.RIGHT, border=3)
        self._modes_panel.Layout()

    def _load_selected(self):
        """Load the selected map."""
        idx = self._map_list.GetFirstSelected()
        scenes = self._map_manager.list_scenes()
        if idx >= 0 and idx < len(scenes):
            self._app._switch_map(scenes[idx].scene_id)

    def _update_stats(self):
        """Update scene statistics."""
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

        self._stats_text.SetValue(stats)
