"""Vehicle Monitor Tab — vehicle list, detail, and simulation controls (wxPython)."""

import wx
import random

from ..services.vehicle_service import VehicleService
from ..models.vehicle import VehicleStatus
from .theme import (
    dark_panel, dark_label, dark_button, dark_text, dark_listctrl,
    dark_slider, hex_to_wx_colour,
)
from .styles import PANEL_BG, TEXT_COLOR


class VehicleMonitorTab(wx.Panel):
    """Tab 5: Vehicle Monitoring with tracking and ETA display."""

    def __init__(self, parent, app, vehicle_service: VehicleService):
        super().__init__(parent)
        self._app = app
        self._vehicles = vehicle_service
        self._sim_running = False
        self._build_ui()

    def _build_ui(self):
        sizer = wx.BoxSizer(wx.VERTICAL)

        # --- Vehicle list ---
        sizer.Add(dark_label(self, label="车辆列表"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)

        self._vehicle_list = dark_listctrl(self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL)
        self._vehicle_list.InsertColumn(0, "车辆", width=120)
        self._vehicle_list.InsertColumn(1, "状态", width=60)
        self._vehicle_list.InsertColumn(2, "速度", width=50)
        self._vehicle_list.InsertColumn(3, "ETA", width=70)
        self._vehicle_list.InsertColumn(4, "进度", width=60)
        self._vehicle_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_vehicle_select)
        sizer.Add(self._vehicle_list, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        # --- Controls ---
        ctrl_sizer = wx.BoxSizer(wx.HORIZONTAL)
        add_btn = wx.Button(self, label="➕ 添加车辆")
        add_btn.Bind(wx.EVT_BUTTON, lambda e: self._add_vehicle())
        ctrl_sizer.Add(add_btn, proportion=0, flag=wx.RIGHT, border=3)
        rm_btn = wx.Button(self, label="➖ 移除车辆")
        rm_btn.Bind(wx.EVT_BUTTON, lambda e: self._remove_vehicle())
        ctrl_sizer.Add(rm_btn)
        sizer.Add(ctrl_sizer, proportion=0, flag=wx.BOTTOM, border=3)

        # --- Simulation ---
        sizer.Add(dark_label(self, label="车辆模拟"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        sim_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._sim_btn = wx.Button(self, label="▶ 开始车辆模拟")
        self._sim_btn.Bind(wx.EVT_BUTTON, lambda e: self._toggle_sim())
        sim_sizer.Add(self._sim_btn, proportion=0, flag=wx.RIGHT, border=4)
        self._sim_label = dark_label(self, label="已停止")
        sim_sizer.Add(self._sim_label, proportion=0, flag=wx.ALIGN_CENTER_VERTICAL)
        sizer.Add(sim_sizer, proportion=0, flag=wx.BOTTOM, border=3)

        sizer.Add(dark_label(self, label="模拟速度"), proportion=0, flag=wx.TOP, border=3)
        self._speed_slider = dark_slider(self, value=10, minValue=1, maxValue=50)
        self._speed_slider.Bind(wx.EVT_SLIDER, self._on_speed_change)
        sizer.Add(self._speed_slider, proportion=0, flag=wx.EXPAND)
        self._speed_label = dark_label(self, label="10×")
        sizer.Add(self._speed_label, proportion=0, flag=wx.BOTTOM, border=3)

        # --- Vehicle detail ---
        sizer.Add(dark_label(self, label="车辆详情"), proportion=0,
                 flag=wx.TOP | wx.BOTTOM, border=4)
        self._detail_text = dark_text(self, value="",
            style=wx.TE_MULTILINE | wx.TE_READONLY)
        self._detail_text.SetMinSize(wx.Size(-1, 100))
        sizer.Add(self._detail_text, proportion=0, flag=wx.EXPAND | wx.BOTTOM, border=3)

        self.SetSizer(sizer)

    def on_map_changed(self, scene_id: str):
        """Reset vehicles when map changes."""
        for v in self._vehicles.list_vehicles():
            self._vehicles.remove_vehicle(v.vehicle_id)
        self.refresh_vehicle_display()

    def _toggle_sim(self):
        """Start/stop vehicle simulation."""
        sim = self._app.ensure_vehicle_simulator()
        if self._sim_running:
            sim.stop()
            self._sim_running = False
            self._sim_btn.SetLabel("▶ 开始车辆模拟")
            self._sim_label.SetLabel("已停止")
        else:
            sim.set_speed_scale(self._speed_slider.GetValue())
            sim.start()
            self._sim_running = True
            self._sim_btn.SetLabel("⏸ 停止车辆模拟")
            self._sim_label.SetLabel("运行中...")

    def _on_speed_change(self, event):
        """Update simulation speed."""
        scale = self._speed_slider.GetValue()
        self._speed_label.SetLabel(f"{scale}×")
        sim = self._app.ensure_vehicle_simulator()
        sim.set_speed_scale(scale)

    def refresh_vehicle_display(self):
        """Refresh the vehicle list."""
        self._vehicle_list.DeleteAllItems()
        for v in self._vehicles.list_vehicles():
            idx = self._vehicle_list.InsertItem(10000, v.name)
            self._vehicle_list.SetItem(idx, 1, str(v.status))
            self._vehicle_list.SetItem(idx, 2, f"{v.speed_kmh:.0f}km/h")
            self._vehicle_list.SetItem(idx, 3, f"{v.eta_seconds:.0f}s")
            self._vehicle_list.SetItem(idx, 4, f"{v.progress_pct:.0f}%")

    def _on_vehicle_select(self, event):
        """Show vehicle details."""
        idx = event.GetIndex()
        vehicles = self._vehicles.list_vehicles()
        if idx < len(vehicles):
            v = vehicles[idx]
            info = (
                f"ID: {v.vehicle_id}\n"
                f"名称: {v.name}\n"
                f"状态: {v.status}\n"
                f"速度: {v.speed_kmh:.1f} km/h\n"
                f"位置: ({v.x:.1f}, {v.y:.1f})\n"
                f"ETA: {v.eta_seconds:.0f} 秒\n"
                f"进度: {v.progress_pct:.1f}%\n"
                f"下一站: {v.next_stop or '已到达'}\n"
            )
            self._detail_text.SetValue(info)

    def _add_vehicle(self):
        """Add a new vehicle on the current path."""
        path = self._app._current_path
        if not path or len(path) < 2:
            self._detail_text.SetValue("请先规划一条路径")
            return

        vid = f"V{random.randint(100, 999)}"
        names = ["公交车1号", "接驳车A", "班车B01", "物流车C3", "巡检车D"]

        v = self._app.ensure_vehicle_simulator().create_and_add_vehicle(
            vid, random.choice(names), path,
            speed_kmh=random.uniform(20, 50),
        )
        self.refresh_vehicle_display()
        self._app.set_status(f"已添加车辆: {v.name}")

    def _remove_vehicle(self):
        """Remove the selected vehicle."""
        idx = self._vehicle_list.GetFirstSelected()
        vehicles = self._vehicles.list_vehicles()
        if 0 <= idx < len(vehicles):
            self._vehicles.remove_vehicle(vehicles[idx].vehicle_id)
            self.refresh_vehicle_display()
