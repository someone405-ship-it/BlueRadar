"""BlueRadar for Windows - Ultra-sensitive Bluetooth LE scanner with dark cyber UI."""
import asyncio, threading, time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import customtkinter as ctk
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

NEON_CYAN, NEON_GREEN, WARNING_RED, ORANGE, BG, PANEL = "#00F5FF", "#39FF14", "#FF2D55", "#FF6B00", "#050510", "#0D0D1A"
MIN_RSSI, WARNING_DISTANCE = -120, 10.0

@dataclass
class DeviceInfo:
    address: str
    name: str
    rssi: int
    distance: float
    first_seen: float
    last_seen: float
    rssi_history: List[int] = field(default_factory=list)
    @property
    def in_range(self): return self.distance <= WARNING_DISTANCE
    @property
    def display_name(self): return self.name if self.name and self.name.strip() else "Hidden Device"

def estimate_distance(rssi, tx_power=-59, n=2.2):
    if rssi == 0: return 99.0
    return min(10 ** ((tx_power - rssi) / (10.0 * n)), 100.0)

class BlueRadarApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BlueRadar — Windows")
        self.geometry("920x720")
        self.configure(fg_color=BG)
        self.minsize(800, 600)
        self.devices: Dict[str, DeviceInfo] = {}
        self.is_scanning = False
        self.loop = None
        self.alerted: Dict[str, float] = {}
        self.start_time = 0.0
        self._build_ui()
        self._start_ui_updater()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=PANEL, height=60, corner_radius=0)
        header.pack(fill="x"); header.pack_propagate(False)
        ctk.CTkLabel(header, text="BlueRadar", font=ctk.CTkFont(size=24, weight="bold"), text_color=NEON_CYAN).pack(side="left", padx=20, pady=12)
        self.status_dot = ctk.CTkLabel(header, text="\u25cf", text_color="#333", font=ctk.CTkFont(size=16))
        self.status_dot.pack(side="left")
        stats = ctk.CTkFrame(self, fg_color=BG, height=50)
        stats.pack(fill="x", padx=16, pady=(8, 0))
        self.lbl_visible = ctk.CTkLabel(stats, text="Visible: 0", text_color=NEON_CYAN, font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_visible.pack(side="left", padx=12)
        self.lbl_warning = ctk.CTkLabel(stats, text="In 10 m: 0", text_color=NEON_GREEN, font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_warning.pack(side="left", padx=12)
        self.lbl_uptime = ctk.CTkLabel(stats, text="Uptime: 0s", text_color="#A0B0D0", font=ctk.CTkFont(size=13))
        self.lbl_uptime.pack(side="left", padx=12)
        btn_frame = ctk.CTkFrame(self, fg_color=BG); btn_frame.pack(pady=12)
        self.btn_scan = ctk.CTkButton(btn_frame, text="START SCAN", command=self.toggle_scan, width=200, height=44,
            font=ctk.CTkFont(size=15, weight="bold"), fg_color=PANEL, border_width=2, border_color=NEON_CYAN,
            text_color=NEON_CYAN, hover_color="#0A2030")
        self.btn_scan.pack()
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        self.list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.device_widgets: Dict[str, ctk.CTkFrame] = {}

    def toggle_scan(self):
        if self.is_scanning: self.stop_scan()
        else: self.start_scan()

    def start_scan(self):
        self.is_scanning = True
        self.start_time = time.time()
        self.btn_scan.configure(text="STOP SCAN", border_color=WARNING_RED, text_color=WARNING_RED)
        self.status_dot.configure(text_color=NEON_GREEN)
        def run_async():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.loop.run_until_complete(self._scan_loop())
        threading.Thread(target=run_async, daemon=True).start()

    def stop_scan(self):
        self.is_scanning = False
        self.btn_scan.configure(text="START SCAN", border_color=NEON_CYAN, text_color=NEON_CYAN)
        self.status_dot.configure(text_color="#333")
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

    async def _scan_loop(self):
        def callback(device: BLEDevice, adv: AdvertisementData):
            if not self.is_scanning: return
            rssi = adv.rssi if adv.rssi is not None else -100
            if rssi < MIN_RSSI: return
            addr = device.address
            name = device.name or adv.local_name or ""
            dist = estimate_distance(rssi)
            now = time.time()
            if addr in self.devices:
                d = self.devices[addr]
                d.rssi, d.distance, d.last_seen = rssi, dist, now
                d.name = name or d.name
                d.rssi_history = (d.rssi_history + [rssi])[-40:]
            else:
                self.devices[addr] = DeviceInfo(addr, name, rssi, dist, now, now, [rssi])
            if dist <= WARNING_DISTANCE:
                self._maybe_alert(self.devices[addr])
        scanner = BleakScanner(detection_callback=callback)
        await scanner.start()
        try:
            while self.is_scanning:
                await asyncio.sleep(0.5)
                now = time.time()
                for a in [a for a, d in self.devices.items() if now - d.last_seen > 90]:
                    del self.devices[a]
        finally:
            await scanner.stop()

    def _maybe_alert(self, device):
        now = time.time()
        if now - self.alerted.get(device.address, 0) < 45: return
        self.alerted[device.address] = now
        self.after(0, lambda: self._flash_alert(device))

    def _flash_alert(self, device):
        original = self.title()
        self.title(f"DEVICE IN RANGE — {device.display_name} ({device.distance:.1f} m)")
        self.after(3000, lambda: self.title(original))

    def _start_ui_updater(self):
        def update():
            if self.is_scanning or self.devices: self._refresh_list()
            self.after(800, update)
        self.after(800, update)

    def _refresh_list(self):
        visible = len(self.devices)
        in_range = sum(1 for d in self.devices.values() if d.in_range)
        uptime = int(time.time() - self.start_time) if self.is_scanning else 0
        self.lbl_visible.configure(text=f"Visible: {visible}")
        self.lbl_warning.configure(text=f"In 10 m: {in_range}", text_color=WARNING_RED if in_range > 0 else NEON_GREEN)
        mins, secs = divmod(uptime, 60)
        self.lbl_uptime.configure(text=f"Uptime: {mins}m {secs}s" if mins else f"Uptime: {secs}s")
        sorted_devs = sorted(self.devices.values(), key=lambda d: (d.distance, -d.rssi))
        current = {d.address for d in sorted_devs}
        for addr in list(self.device_widgets.keys()):
            if addr not in current:
                self.device_widgets[addr].destroy()
                del self.device_widgets[addr]
        for device in sorted_devs:
            if device.address not in self.device_widgets:
                self.device_widgets[device.address] = self._create_device_card(device)
            else:
                self._update_device_card(self.device_widgets[device.address], device)

    def _create_device_card(self, device):
        border = WARNING_RED if device.in_range else PANEL
        frame = ctk.CTkFrame(self.list_frame, fg_color=PANEL, border_width=1, border_color=border, corner_radius=12)
        frame.pack(fill="x", pady=4, padx=4)
        top = ctk.CTkFrame(frame, fg_color="transparent"); top.pack(fill="x", padx=12, pady=(10, 2))
        name_lbl = ctk.CTkLabel(top, text=device.display_name, font=ctk.CTkFont(size=15, weight="bold"), text_color="#E8F0FF")
        name_lbl.pack(side="left"); frame.name_lbl = name_lbl
        dist_color = WARNING_RED if device.distance <= 1.5 else (ORANGE if device.distance <= 4 else NEON_CYAN)
        dist_lbl = ctk.CTkLabel(top, text=f"{device.distance:.1f} m", font=ctk.CTkFont(size=14, weight="bold"), text_color=dist_color)
        dist_lbl.pack(side="right"); frame.dist_lbl = dist_lbl
        addr_lbl = ctk.CTkLabel(frame, text=device.address, font=ctk.CTkFont(size=11, family="Consolas"), text_color="#607090")
        addr_lbl.pack(anchor="w", padx=12); frame.addr_lbl = addr_lbl
        info = ctk.CTkLabel(frame, text=f"{device.rssi} dBm", font=ctk.CTkFont(size=12), text_color=NEON_CYAN)
        info.pack(anchor="w", padx=12, pady=(2, 10)); frame.info_lbl = info
        return frame

    def _update_device_card(self, frame, device):
        frame.name_lbl.configure(text=device.display_name)
        dist_color = WARNING_RED if device.distance <= 1.5 else (ORANGE if device.distance <= 4 else NEON_CYAN)
        frame.dist_lbl.configure(text=f"{device.distance:.1f} m", text_color=dist_color)
        frame.info_lbl.configure(text=f"{device.rssi} dBm")
        frame.configure(border_color=WARNING_RED if device.in_range else PANEL)

if __name__ == "__main__":
    BlueRadarApp().mainloop()
