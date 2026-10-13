"""BlueRadar Windows - Advanced BLE radar with polished UI."""
from __future__ import annotations
import asyncio, csv, json, os, threading, time
from dataclasses import dataclass, field
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional, Set
import customtkinter as ctk
try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
    BLEAK_OK = True
except ImportError:
    BLEAK_OK = False
try:
    import winsound
    WINSOUND_OK = True
except ImportError:
    WINSOUND_OK = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
CYAN, MAGENTA, GREEN, RED, ORANGE = "#00F5FF", "#FF00E5", "#39FF14", "#FF2D55", "#FF6B00"
BG, PANEL, PANEL2, MUTED, WHITE = "#050510", "#0D0D1A", "#12122A", "#607090", "#E8F0FF"
STALE_SEC = 90
app_settings = {"warn_distance": 10.0, "min_rssi": -120, "sound_alerts": True, "flash_title": True, "sort_by": "distance"}

@dataclass
class DeviceInfo:
    address: str
    name: str
    rssi: int
    distance: float
    first_seen: float
    last_seen: float
    rssi_history: List[int] = field(default_factory=list)
    device_type: str = "Unknown"
    is_hidden: bool = False
    alert_count: int = 0
    times_seen: int = 1
    @property
    def in_range(self):
        return self.distance <= app_settings["warn_distance"]
    @property
    def display_name(self):
        return self.name.strip() if self.name and self.name.strip() else "Hidden Device"

def estimate_distance(rssi, tx_power=-59, n=2.2):
    if rssi == 0: return 99.0
    return min(10 ** ((tx_power - rssi) / (10.0 * n)), 100.0)

def classify_name(name):
    if not name: return "Unknown"
    n = name.lower()
    if any(x in n for x in ("airpods", "buds", "headset", "headphone", "beats")): return "Headset"
    if any(x in n for x in ("airtag", "tile", "smarttag", "tracker", "find my")): return "Tracker"
    if any(x in n for x in ("watch", "band", "fitbit")): return "Wearable"
    if any(x in n for x in ("speaker", "homepod", "echo")): return "Speaker"
    if any(x in n for x in ("iphone", "pixel", "galaxy", "phone")): return "Phone"
    if any(x in n for x in ("macbook", "laptop", "pc")): return "Computer"
    if any(x in n for x in ("keyboard", "mouse")): return "Input"
    return "Unknown"

class BlueRadarApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BlueRadar - Advanced Bluetooth Radar")
        self.geometry("1100x780")
        self.minsize(900, 650)
        self.configure(fg_color=BG)
        self.devices: Dict[str, DeviceInfo] = {}
        self.blacklist: Set[str] = set()
        self.favorites: Set[str] = set()
        self.is_scanning = False
        self.loop = None
        self.alerted: Dict[str, float] = {}
        self.start_time = 0.0
        self.total_alerts = 0
        self.session_seen: Set[str] = set()
        self.device_widgets: Dict[str, ctk.CTkFrame] = {}
        self._load_prefs()
        self._build_ui()
        self._start_ui_updater()
        if not BLEAK_OK:
            messagebox.showerror("Missing dependency", "pip install bleak customtkinter")

    def _prefs_path(self):
        return os.path.join(os.path.expanduser("~"), ".blueradar_prefs.json")

    def _load_prefs(self):
        try:
            with open(self._prefs_path(), "r", encoding="utf-8") as f:
                data = json.load(f)
            self.blacklist = set(data.get("blacklist", []))
            self.favorites = set(data.get("favorites", []))
            for k in ("warn_distance", "min_rssi", "sound_alerts", "flash_title", "sort_by"):
                if k in data: app_settings[k] = data[k]
        except Exception:
            pass

    def _save_prefs(self):
        data = {"blacklist": list(self.blacklist), "favorites": list(self.favorites),
                **{k: app_settings[k] for k in ("warn_distance", "min_rssi", "sound_alerts", "flash_title", "sort_by")}}
        try:
            with open(self._prefs_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=PANEL, height=64, corner_radius=0)
        header.pack(fill="x"); header.pack_propagate(False)
        ctk.CTkLabel(header, text="BlueRadar", font=ctk.CTkFont(size=26, weight="bold"), text_color=CYAN).pack(side="left", padx=20, pady=14)
        self.status_dot = ctk.CTkLabel(header, text="\u25cf", text_color="#333", font=ctk.CTkFont(size=18))
        self.status_dot.pack(side="left", padx=(0, 8))
        self.lbl_status = ctk.CTkLabel(header, text="Idle", text_color=MUTED, font=ctk.CTkFont(size=13))
        self.lbl_status.pack(side="left")
        ctk.CTkButton(header, text="Settings", width=90, height=32, fg_color=PANEL2, border_width=1, border_color=MUTED, text_color=WHITE, command=self._open_settings).pack(side="right", padx=12, pady=16)
        ctk.CTkButton(header, text="Export", width=80, height=32, fg_color=PANEL2, border_width=1, border_color=CYAN, text_color=CYAN, command=self._export).pack(side="right", padx=4, pady=16)

        stats = ctk.CTkFrame(self, fg_color=BG, height=56)
        stats.pack(fill="x", padx=16, pady=(10, 0))
        self.lbl_visible = self._stat(stats, "Visible", "0", CYAN)
        self.lbl_warning = self._stat(stats, "In range", "0", GREEN)
        self.lbl_hidden = self._stat(stats, "Hidden", "0", ORANGE)
        self.lbl_alerts = self._stat(stats, "Alerts", "0", RED)
        self.lbl_uptime = self._stat(stats, "Uptime", "0s", MUTED)
        self.lbl_session = self._stat(stats, "Session", "0", MAGENTA)

        ctrl = ctk.CTkFrame(self, fg_color=BG)
        ctrl.pack(fill="x", padx=16, pady=10)
        self.btn_scan = ctk.CTkButton(ctrl, text="START SCAN", command=self.toggle_scan, width=180, height=42, font=ctk.CTkFont(size=14, weight="bold"), fg_color=PANEL, border_width=2, border_color=CYAN, text_color=CYAN, hover_color="#0A2030")
        self.btn_scan.pack(side="left", padx=(0, 12))
        ctk.CTkButton(ctrl, text="Clear list", width=100, height=36, fg_color=PANEL2, text_color=MUTED, command=self._clear_list).pack(side="left", padx=4)
        self.search_var = ctk.StringVar()
        ctk.CTkEntry(ctrl, placeholder_text="Search name / MAC...", textvariable=self.search_var, width=220, height=36, fg_color=PANEL2, border_color=MUTED).pack(side="left", padx=12)
        self.var_hidden = ctk.BooleanVar(value=False)
        self.var_range = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(ctrl, text="Hidden only", variable=self.var_hidden, text_color=MUTED, fg_color=CYAN).pack(side="left", padx=8)
        ctk.CTkCheckBox(ctrl, text="In range only", variable=self.var_range, text_color=MUTED, fg_color=CYAN).pack(side="left", padx=8)
        ctk.CTkLabel(ctrl, text="Sort:", text_color=MUTED).pack(side="left", padx=(16, 4))
        self.sort_var = ctk.StringVar(value=app_settings["sort_by"])
        ctk.CTkOptionMenu(ctrl, values=["distance", "rssi", "name", "last_seen"], variable=self.sort_var, command=self._on_sort_change, width=120, height=32, fg_color=PANEL2, button_color=PANEL).pack(side="left")

        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        self.list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        ctk.CTkLabel(self, text="Tip: Fav / Ignore / Copy on each card  |  Settings: distance, sensitivity, sound  |  Export CSV/JSON", text_color=MUTED, font=ctk.CTkFont(size=11)).pack(pady=(0, 8))

    def _stat(self, parent, label, value, color):
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.pack(side="left", expand=True)
        val = ctk.CTkLabel(col, text=value, text_color=color, font=ctk.CTkFont(size=18, weight="bold"))
        val.pack()
        ctk.CTkLabel(col, text=label, text_color=MUTED, font=ctk.CTkFont(size=11)).pack()
        return val

    def toggle_scan(self):
        if self.is_scanning: self.stop_scan()
        else: self.start_scan()

    def start_scan(self):
        if not BLEAK_OK:
            messagebox.showerror("Error", "bleak not installed")
            return
        self.is_scanning = True
        self.start_time = time.time()
        self.btn_scan.configure(text="STOP SCAN", border_color=RED, text_color=RED)
        self.status_dot.configure(text_color=GREEN)
        self.lbl_status.configure(text="Scanning...", text_color=GREEN)
        def run_async():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try: self.loop.run_until_complete(self._scan_loop())
            except Exception: pass
        threading.Thread(target=run_async, daemon=True).start()

    def stop_scan(self):
        self.is_scanning = False
        self.btn_scan.configure(text="START SCAN", border_color=CYAN, text_color=CYAN)
        self.status_dot.configure(text_color="#333")
        self.lbl_status.configure(text="Idle", text_color=MUTED)
        if self.loop and self.loop.is_running():
            try: self.loop.call_soon_threadsafe(self.loop.stop)
            except Exception: pass
        self._save_prefs()

    async def _scan_loop(self):
        def callback(device, adv):
            if not self.is_scanning: return
            rssi = adv.rssi if adv.rssi is not None else -100
            if rssi < app_settings["min_rssi"]: return
            addr = device.address
            if addr in self.blacklist: return
            name = device.name or adv.local_name or ""
            dist = estimate_distance(rssi)
            now = time.time()
            hidden = not bool(name and name.strip())
            dtype = classify_name(name)
            if addr in self.devices:
                d = self.devices[addr]
                d.rssi, d.distance, d.last_seen = rssi, dist, now
                d.name = name or d.name
                d.is_hidden = hidden and not d.name
                d.rssi_history = (d.rssi_history + [rssi])[-50:]
                d.times_seen += 1
            else:
                self.devices[addr] = DeviceInfo(address=addr, name=name, rssi=rssi, distance=dist, first_seen=now, last_seen=now, rssi_history=[rssi], is_hidden=hidden, device_type=dtype)
                self.session_seen.add(addr)
            if dist <= app_settings["warn_distance"]:
                self._maybe_alert(self.devices[addr])
        scanner = BleakScanner(detection_callback=callback)
        await scanner.start()
        try:
            while self.is_scanning:
                await asyncio.sleep(0.4)
                now = time.time()
                for a in [a for a, d in self.devices.items() if now - d.last_seen > STALE_SEC]:
                    del self.devices[a]
        finally:
            await scanner.stop()

    def _maybe_alert(self, device):
        now = time.time()
        if now - self.alerted.get(device.address, 0) < 45: return
        self.alerted[device.address] = now
        device.alert_count += 1
        self.total_alerts += 1
        self.after(0, lambda: self._do_alert(device))

    def _do_alert(self, device):
        if app_settings["flash_title"]:
            original = self.title()
            self.title(f"IN RANGE - {device.display_name} ({device.distance:.1f} m)")
            self.after(3500, lambda: self.title(original))
        if app_settings["sound_alerts"] and WINSOUND_OK:
            try: winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception: pass

    def _start_ui_updater(self):
        def tick():
            self._refresh_list()
            self.after(700, tick)
        self.after(700, tick)

    def _filtered_sorted(self):
        items = list(self.devices.values())
        q = self.search_var.get().strip().lower()
        if q: items = [d for d in items if q in d.display_name.lower() or q in d.address.lower()]
        if self.var_hidden.get(): items = [d for d in items if d.is_hidden]
        if self.var_range.get(): items = [d for d in items if d.in_range]
        key = self.sort_var.get()
        if key == "distance": items.sort(key=lambda d: (d.distance, -d.rssi))
        elif key == "rssi": items.sort(key=lambda d: -d.rssi)
        elif key == "name": items.sort(key=lambda d: d.display_name.lower())
        else: items.sort(key=lambda d: -d.last_seen)
        return items

    def _refresh_list(self):
        visible = len(self.devices)
        in_range = sum(1 for d in self.devices.values() if d.in_range)
        hidden = sum(1 for d in self.devices.values() if d.is_hidden)
        uptime = int(time.time() - self.start_time) if self.is_scanning else 0
        self.lbl_visible.configure(text=str(visible))
        self.lbl_warning.configure(text=str(in_range), text_color=RED if in_range else GREEN)
        self.lbl_hidden.configure(text=str(hidden))
        self.lbl_alerts.configure(text=str(self.total_alerts))
        m, s = divmod(uptime, 60)
        self.lbl_uptime.configure(text=f"{m}m {s}s" if m else f"{s}s")
        self.lbl_session.configure(text=str(len(self.session_seen)))
        sorted_devs = self._filtered_sorted()
        current = {d.address for d in sorted_devs}
        for addr in list(self.device_widgets.keys()):
            if addr not in current:
                self.device_widgets[addr].destroy()
                del self.device_widgets[addr]
        for device in sorted_devs:
            if device.address not in self.device_widgets:
                self.device_widgets[device.address] = self._create_card(device)
            else:
                self._update_card(self.device_widgets[device.address], device)

    def _create_card(self, device):
        border = RED if device.in_range else (ORANGE if device.is_hidden else PANEL)
        frame = ctk.CTkFrame(self.list_frame, fg_color=PANEL, border_width=1, border_color=border, corner_radius=12)
        frame.pack(fill="x", pady=3, padx=4)
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 2))
        left = ctk.CTkFrame(top, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        star = "* " if device.address in self.favorites else ""
        name_lbl = ctk.CTkLabel(left, text=f"{star}{device.display_name}", font=ctk.CTkFont(size=15, weight="bold"), text_color=WHITE, anchor="w")
        name_lbl.pack(anchor="w"); frame.name_lbl = name_lbl
        ctk.CTkLabel(left, text=device.address, font=ctk.CTkFont(size=11, family="Consolas"), text_color=MUTED, anchor="w").pack(anchor="w")
        dist_color = RED if device.distance <= 1.5 else (ORANGE if device.distance <= 4 else CYAN)
        dist_lbl = ctk.CTkLabel(top, text=f"{device.distance:.1f} m", font=ctk.CTkFont(size=15, weight="bold"), text_color=dist_color)
        dist_lbl.pack(side="right"); frame.dist_lbl = dist_lbl
        meta = ctk.CTkFrame(frame, fg_color="transparent")
        meta.pack(fill="x", padx=14, pady=(2, 10))
        info = ctk.CTkLabel(meta, text=f"{device.rssi} dBm  |  {device.device_type}  |  seen x{device.times_seen}", font=ctk.CTkFont(size=12), text_color=CYAN, anchor="w")
        info.pack(side="left"); frame.info_lbl = info
        ctk.CTkButton(meta, text="Copy", width=50, height=24, font=ctk.CTkFont(size=11), fg_color=PANEL2, text_color=MUTED, command=lambda a=device.address: self._copy_mac(a)).pack(side="right", padx=2)
        ctk.CTkButton(meta, text="Ignore", width=55, height=24, font=ctk.CTkFont(size=11), fg_color=PANEL2, text_color=RED, command=lambda a=device.address: self._blacklist(a)).pack(side="right", padx=2)
        ctk.CTkButton(meta, text="Fav", width=45, height=24, font=ctk.CTkFont(size=11), fg_color=PANEL2, text_color=ORANGE, command=lambda a=device.address: self._toggle_fav(a)).pack(side="right", padx=2)
        return frame

    def _update_card(self, frame, device):
        star = "* " if device.address in self.favorites else ""
        frame.name_lbl.configure(text=f"{star}{device.display_name}")
        dist_color = RED if device.distance <= 1.5 else (ORANGE if device.distance <= 4 else CYAN)
        frame.dist_lbl.configure(text=f"{device.distance:.1f} m", text_color=dist_color)
        frame.info_lbl.configure(text=f"{device.rssi} dBm  |  {device.device_type}  |  seen x{device.times_seen}")
        frame.configure(border_color=RED if device.in_range else (ORANGE if device.is_hidden else PANEL))

    def _copy_mac(self, addr):
        self.clipboard_clear(); self.clipboard_append(addr)
        self.lbl_status.configure(text=f"Copied {addr}", text_color=CYAN)

    def _blacklist(self, addr):
        self.blacklist.add(addr); self.devices.pop(addr, None); self._save_prefs()

    def _toggle_fav(self, addr):
        if addr in self.favorites: self.favorites.discard(addr)
        else: self.favorites.add(addr)
        self._save_prefs()

    def _clear_list(self):
        self.devices.clear()
        for w in list(self.device_widgets.values()): w.destroy()
        self.device_widgets.clear()

    def _on_sort_change(self, _=None):
        app_settings["sort_by"] = self.sort_var.get(); self._save_prefs()

    def _open_settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Settings"); win.geometry("420x400"); win.configure(fg_color=BG); win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="Settings", font=ctk.CTkFont(size=20, weight="bold"), text_color=CYAN).pack(pady=16)
        ctk.CTkLabel(win, text="Warning distance (m)", text_color=MUTED).pack(anchor="w", padx=24)
        dist_var = ctk.DoubleVar(value=app_settings["warn_distance"])
        ctk.CTkSlider(win, from_=2, to=30, variable=dist_var, number_of_steps=28, progress_color=CYAN).pack(fill="x", padx=24, pady=4)
        dist_lbl = ctk.CTkLabel(win, text=f"{app_settings['warn_distance']:.0f} m", text_color=WHITE); dist_lbl.pack()
        dist_var.trace_add("write", lambda *_: dist_lbl.configure(text=f"{dist_var.get():.0f} m"))
        ctk.CTkLabel(win, text="Min RSSI (dBm)", text_color=MUTED).pack(anchor="w", padx=24, pady=(12, 0))
        rssi_var = ctk.IntVar(value=app_settings["min_rssi"])
        ctk.CTkSlider(win, from_=-120, to=-50, variable=rssi_var, number_of_steps=70, progress_color=CYAN).pack(fill="x", padx=24, pady=4)
        rssi_lbl = ctk.CTkLabel(win, text=f"{app_settings['min_rssi']} dBm", text_color=WHITE); rssi_lbl.pack()
        rssi_var.trace_add("write", lambda *_: rssi_lbl.configure(text=f"{rssi_var.get()} dBm"))
        sound_var = ctk.BooleanVar(value=app_settings["sound_alerts"])
        flash_var = ctk.BooleanVar(value=app_settings["flash_title"])
        ctk.CTkCheckBox(win, text="Sound alerts", variable=sound_var, text_color=WHITE, fg_color=CYAN).pack(anchor="w", padx=24, pady=8)
        ctk.CTkCheckBox(win, text="Flash title on alert", variable=flash_var, text_color=WHITE, fg_color=CYAN).pack(anchor="w", padx=24, pady=4)
        def save():
            app_settings["warn_distance"] = dist_var.get()
            app_settings["min_rssi"] = rssi_var.get()
            app_settings["sound_alerts"] = sound_var.get()
            app_settings["flash_title"] = flash_var.get()
            self._save_prefs(); win.destroy()
        ctk.CTkButton(win, text="Save", command=save, fg_color=CYAN, text_color=BG, width=120).pack(pady=20)
        ctk.CTkLabel(win, text=f"Blacklisted: {len(self.blacklist)}  |  Favorites: {len(self.favorites)}", text_color=MUTED).pack()

    def _export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("JSON", "*.json")], title="Export")
        if not path: return
        try:
            if path.lower().endswith(".json"):
                data = [{"address": d.address, "name": d.display_name, "rssi": d.rssi, "distance_m": round(d.distance, 2), "type": d.device_type, "hidden": d.is_hidden, "times_seen": d.times_seen, "alerts": d.alert_count, "last_seen": datetime.fromtimestamp(d.last_seen).isoformat()} for d in self.devices.values()]
                with open(path, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)
            else:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["address", "name", "rssi", "distance_m", "type", "hidden", "times_seen", "alerts", "last_seen"])
                    for d in self.devices.values():
                        w.writerow([d.address, d.display_name, d.rssi, f"{d.distance:.2f}", d.device_type, d.is_hidden, d.times_seen, d.alert_count, datetime.fromtimestamp(d.last_seen).isoformat()])
            messagebox.showinfo("Export", f"Saved {len(self.devices)} devices")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

if __name__ == "__main__":
    BlueRadarApp().mainloop()
