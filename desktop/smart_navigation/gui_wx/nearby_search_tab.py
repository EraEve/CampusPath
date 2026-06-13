"""Nearby Search Tab — POI proximity search and route-to-POI (wxPython)."""

import wx

from ..services.search_service import SearchService
from .theme import (
    dark_panel, dark_label, dark_button, dark_text, dark_combo,
    dark_listctrl, dark_checkbox, dark_spin, hex_to_wx_colour,
)
from .styles import PANEL_BG, TEXT_COLOR


class NearbySearchTab(wx.Panel):
    """Tab 4: Nearby POI Search with category filtering and routing."""

    def __init__(self, parent, app, search_service: SearchService):
        super().__init__(parent)
        self._app = app
        self._search = search_service
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Search center ---
        sizer.Add(dark_label(self, label="搜索中心"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        center_sizer = wx.BoxSizer(wx.HORIZONTAL)
        center_sizer.Add(dark_label(self, label="节点:"), proportion=0,
                        flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=3)
        self._center_combo = dark_combo(self, choices=[], style=wx.CB_READONLY)
        center_sizer.Add(self._center_combo, proportion=1)
        sizer.Add(center_sizer, proportion=0, flag=wx.EXPAND)

        # --- Categories ---
        sizer.Add(dark_label(self, label="POI类别"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        cat_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._cat_cbs = {}
        for cat, emoji in [("scenic", "🏛 景点"), ("food", "🍽 美食"),
                           ("parking", "🅿 停车场"), ("hospital", "🏥 医院")]:
            cb = dark_checkbox(self, label=emoji)
            cb.SetValue(True)
            self._cat_cbs[cat] = cb
            cat_sizer.Add(cb, proportion=0, flag=wx.RIGHT, border=3)
        sizer.Add(cat_sizer, proportion=0)

        # --- Radius ---
        sizer.Add(dark_label(self, label="搜索半径"), proportion=0,
                 flag=wx.TOP, border=4)
        radius_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._radius_combo = dark_combo(self, choices=["无限", "100", "200", "300", "500", "1000"],
                                       style=wx.CB_READONLY)
        self._radius_combo.SetSelection(0)
        radius_sizer.Add(self._radius_combo, proportion=0, flag=wx.RIGHT, border=4)

        radius_sizer.Add(dark_label(self, label="  最大结果:"), proportion=0,
                        flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=3)
        self._max_spin = dark_spin(self, value=20, min_val=1, max_val=100)
        radius_sizer.Add(self._max_spin, proportion=0)
        sizer.Add(radius_sizer, proportion=0, flag=wx.BOTTOM, border=3)

        # --- Search button ---
        search_btn = wx.Button(self, label="🔍 搜索附近")
        search_btn.Bind(wx.EVT_BUTTON, lambda e: self._do_search())
        sizer.Add(search_btn, proportion=0, flag=wx.EXPAND | wx.TOP | wx.BOTTOM, border=6)

        # --- Results ---
        self._result_list = dark_listctrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self._result_list.InsertColumn(0, "名称", width=130)
        self._result_list.InsertColumn(1, "类别", width=70)
        self._result_list.InsertColumn(2, "距离", width=60)
        self._result_list.InsertColumn(3, "方向", width=50)
        self._result_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_result_select)
        sizer.Add(self._result_list, proportion=1, flag=wx.EXPAND | wx.BOTTOM, border=3)

        route_btn = wx.Button(self, label="🚏 规划到此处路径")
        route_btn.Bind(wx.EVT_BUTTON, lambda e: self._route_to_selected())
        sizer.Add(route_btn, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        # --- POI Info ---
        self._info_text = dark_text(self, value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY)
        self._info_text.SetMinSize(wx.Size(-1, 60))
        sizer.Add(self._info_text, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        # --- Category summary ---
        sizer.Add(dark_label(self, label="POI概览"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        self._summary_text = dark_text(self, value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY)
        self._summary_text.SetMinSize(wx.Size(-1, 50))
        sizer.Add(self._summary_text, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        self.SetSizer(sizer)

    def on_map_changed(self, scene_id: str):
        """Update node list and POI summary when map changes."""
        graph = self._app.get_active_graph()
        if not graph:
            return

        nodes = graph.get_all_nodes()
        names = [f"{nid} - {graph.get_node(nid).name}" for nid in nodes]
        self._center_combo.Clear()
        self._center_combo.Set(names)

        self._summary_text.SetValue("")
        lines = []
        for cat_info in self._search.get_poi_categories(graph):
            lines.append(f"  {cat_info['label']}: {cat_info['count']} 个")
        self._summary_text.SetValue("\n".join(lines))

    def _do_search(self):
        """Execute nearby search."""
        graph = self._app.get_active_graph()
        if not graph:
            return

        center_str = self._center_combo.GetValue()
        if " - " in center_str:
            center_id = center_str.split(" - ")[0].strip()
        else:
            center_id = center_str.strip() if center_str else None

        categories = [cat for cat, cb in self._cat_cbs.items() if cb.GetValue()]
        if not categories:
            categories = None

        radius_str = self._radius_combo.GetValue()
        radius = float("inf") if radius_str == "无限" else float(radius_str)

        results = self._search.search_nearby(
            graph,
            center_node_id=center_id,
            categories=categories,
            radius=radius,
            max_results=self._max_spin.GetValue(),
        )

        self._result_list.DeleteAllItems()
        for r in results:
            idx = self._result_list.InsertItem(10000, r["name"])
            self._result_list.SetItem(idx, 1, r["category_label"])
            self._result_list.SetItem(idx, 2, f"{r['distance']:.0f}")
            self._result_list.SetItem(idx, 3, r["direction"])

    def _on_result_select(self, event):
        """POI result selected."""
        idx = event.GetIndex()
        results = self._search.get_last_results()
        if idx < len(results):
            r = results[idx]
            info = (
                f"名称: {r['name']}\n"
                f"类别: {r['category_label']}\n"
                f"距离: {r['distance']:.0f} 单位\n"
                f"方向: {r['direction']}\n"
                f"楼层: {r['floor']}\n"
                f"描述: {r.get('description', '无')}\n"
            )
            self._info_text.SetValue(info)
            # Highlight on canvas
            self._app.show_path_on_map([r["node_id"]])

    def _route_to_selected(self):
        """Plan a route from the center to the selected POI."""
        idx = self._result_list.GetFirstSelected()
        if idx < 0:
            return

        center_str = self._center_combo.GetValue()
        if " - " in center_str:
            center_id = center_str.split(" - ")[0].strip()
        else:
            center_id = center_str.strip()

        results = self._search.get_last_results()
        if idx >= len(results):
            return
        poi_id = results[idx]["node_id"]

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
