"""Vehicle Monitor Tab — vehicle list, detail, and simulation controls."""

import tkinter as tk
from tkinter import ttk

from ..services.vehicle_service import VehicleService
from ..models.vehicle import VehicleStatus


class VehicleMonitorTab(ttk.Frame):
    """Tab 5: Vehicle Monitoring with tracking and ETA display."""

    def __init__(self, parent, app, vehicle_service: VehicleService):
        super().__init__(parent)
        self._app = app
        self._vehicles = vehicle_service
        self._sim_running = False
        self._build_ui()

    def _build_ui(self):
        # --- Vehicle list ---
        ttk.Label(self, text="车辆列表", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(5, 2))

        self._vehicle_tree = ttk.Treeview(
            self, columns=("status", "speed", "eta", "progress"),
            show="headings", height=6,
        )
        self._vehicle_tree.heading("#0", text="车辆")
        self._vehicle_tree.heading("status", text="状态")
        self._vehicle_tree.heading("speed", text="速度")
        self._vehicle_tree.heading("eta", text="ETA")
        self._vehicle_tree.heading("progress", text="进度")
        self._vehicle_tree.column("#0", width=120)
        self._vehicle_tree.column("status", width=60)
        self._vehicle_tree.column("speed", width=50)
        self._vehicle_tree.column("eta", width=70)
        self._vehicle_tree.column("progress", width=60)
        self._vehicle_tree.pack(fill=tk.X, pady=3)
        self._vehicle_tree.bind("<<TreeviewSelect>>", self._on_vehicle_select)

        # --- Controls ---
        ctrl_frame = ttk.Frame(self)
        ctrl_frame.pack(fill=tk.X, pady=3)
        ttk.Button(ctrl_frame, text="➕ 添加车辆", command=self._add_vehicle).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl_frame, text="➖ 移除车辆", command=self._remove_vehicle).pack(side=tk.LEFT, padx=2)

        # --- Simulation ---
        ttk.Label(self, text="车辆模拟", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))
        sim_frame = ttk.Frame(self)
        sim_frame.pack(fill=tk.X)
        self._sim_btn = ttk.Button(sim_frame, text="▶ 开始车辆模拟", command=self._toggle_sim)
        self._sim_btn.pack(side=tk.LEFT, padx=2)
        self._sim_label = ttk.Label(sim_frame, text="已停止", foreground="gray")
        self._sim_label.pack(side=tk.LEFT, padx=5)

        ttk.Label(self, text="模拟速度").pack(anchor=tk.W, pady=(5, 0))
        self._speed_scale = ttk.Scale(self, from_=1, to=50, value=10,
                                     orient=tk.HORIZONTAL, command=self._on_speed_change)
        self._speed_scale.pack(fill=tk.X)
        self._speed_label = ttk.Label(self, text="10×")
        self._speed_label.pack(anchor=tk.W)

        # --- Vehicle detail ---
        ttk.Label(self, text="车辆详情", font=("SimHei", 10, "bold")).pack(anchor=tk.W, pady=(8, 2))
        self._detail_text = tk.Text(self, height=8, width=40,
                                    bg="#1a1a2e", fg="#ecf0f1",
                                    font=("SimHei", 9))
        self._detail_text.pack(fill=tk.X, pady=3)

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
            self._sim_btn.config(text="▶ 开始车辆模拟")
            self._sim_label.config(text="已停止", foreground="gray")
        else:
            sim.set_speed_scale(self._speed_scale.get())
            sim.start()
            self._sim_running = True
            self._sim_btn.config(text="⏸ 停止车辆模拟")
            self._sim_label.config(text="运行中...", foreground="green")

    def _on_speed_change(self, val):
        """Update simulation speed."""
        scale = float(val)
        self._speed_label.config(text=f"{scale:.0f}×")
        sim = self._app.ensure_vehicle_simulator()
        sim.set_speed_scale(scale)

    def refresh_vehicle_display(self):
        """Refresh the vehicle list."""
        self._vehicle_tree.delete(*self._vehicle_tree.get_children())
        for v in self._vehicles.list_vehicles():
            self._vehicle_tree.insert("", tk.END, iid=v.vehicle_id,
                                     text=v.name,
                                     values=(
                                         str(v.status),
                                         f"{v.speed_kmh:.0f}km/h",
                                         f"{v.eta_seconds:.0f}s",
                                         f"{v.progress_pct:.0f}%",
                                     ))

    def _on_vehicle_select(self, event):
        """Show vehicle details."""
        sel = self._vehicle_tree.selection()
        if not sel:
            return
        v = self._vehicles.get_vehicle(sel[0])
        if not v:
            return

        self._detail_text.delete("1.0", tk.END)
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
        self._detail_text.insert("1.0", info)

    def _add_vehicle(self):
        """Add a new vehicle on the current path."""
        path = self._app._current_path
        if not path or len(path) < 2:
            self._detail_text.delete("1.0", tk.END)
            self._detail_text.insert("1.0", "请先规划一条路径")
            return

        import random
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
        sel = self._vehicle_tree.selection()
        if sel:
            self._vehicles.remove_vehicle(sel[0])
            self.refresh_vehicle_display()
