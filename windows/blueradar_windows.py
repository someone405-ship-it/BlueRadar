"""BlueRadar Windows UI - live BLE radar."""
from __future__ import annotations
import csv, json, os, sys, time
from datetime import datetime
from tkinter import filedialog, messagebox
from typing import Dict, Set
import customtkinter as ctk
from blueradar_scanner import BLEAK_OK, DeviceInfo, LiveScanner
try:
    import winsound
    WINSOUND_OK = True
except ImportError:
    WINSOUND_OK = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
CYAN, MAGENTA, GREEN, RED, ORANGE = "#00F5FF", "#FF00E5", "#39FF14", "#FF2D55", "#FF6B00"
BG, PANEL, PANEL2, MUTED, WHITE = "#050510", "#0D0D1A", "#12122A", "#607090", "#E8F0FF"
UI_MS = 350
app_settings = {"warn_distance": 10.0, "min_rssi": -120, "sound_alerts": True, "flash_title": True, "sort_by": "distance"}

class BlueRadarApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("BlueRadar - Live Bluetooth Radar")
        self.geometry("1100x780")
        self.minsize(900, 650)
        self.configure(fg_color=BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.favorites: Set[str] = set()
        self.device_widgets: Dict[str, ctk.CTkFrame] = {}
        self.total_alerts = 0
        self.start_time = 0.0
        self.scanner = LiveScanner(min_rssi=app_settings["min_rssi"], warn_distance=app_settings["warn_distance"])
        self.scanner.on_alert = self._queue_alert
        self.scanner.on_status = self._queue_status
        self._pending_status = None
        self._pending_alert = None
        self._load_prefs()
        self._build_ui()
        self.after(UI_MS, self._tick)
        if not BLEAK_OK:
            messagebox.showerror("Error", "bleak missing. Re-download EXE or: pip install bleak customtkinter")

    def _prefs_path(self):
        return os.path.join(os.path.expanduser("~"), ".blueradar_prefs.json")

    def _load_prefs(self):
        try:
            with open(self._prefs_path(), encoding="utf-8") as f:
                data = json.load(f)
            self.favorites = set(data.get("favorites", []))
            self.scanner.blacklist = set(data.get("blacklist", []))
            for k in app_settings:
                if k in data:
                    app_settings[k] = data[k]
            self.scanner.min_rssi = app_settings["min_rssi"]
            self.scanner.warn_distance = app_settings["warn_distance"]
        except Exception:
            pass

    def _save_prefs(self):
        data = {"favorites": list(self.favorites), "blacklist": list(self.scanner.blacklist), **app_settings}
        try:
            with open(self._prefs_path(), "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=PANEL, height=64, corner_radius=0)
        header.pack(fill="x"); header.pack_propagate(False)
        ctk.CTkLabel(header, text="BlueRadar", font=ctk.CTkFont(size=26, weight="bold"), text_color=CYAN).pack(side="left", padx=20, pady=14)
        self.status_dot = ctk.CTkLabel(header, text="*", text_color="#333", font=ctk.CTkFont(size=18))
        self.status_dot.pack(side="left", padx=(0, 8))
        self.lbl_status = ctk.CTkLabel(header, text="Idle - press START SCAN", text_color=MUTED, font=ctk.CTkFont(size=13))
        self.lbl_status.pack(side="left")
        ctk.CTkButton(header, text="Settings", width=90, height=32, fg_color=PANEL2, border_width=1, border_color=MUTED, text_color=WHITE, command=self._settings).pack(side="right", padx=12, pady=16)
        ctk.CTkButton(header, text="Export", width=80, height=32, fg_color=PANEL2, border_width=1, border_color=CYAN, text_color=CYAN, command=self._export).pack(side="right", padx=4, pady=16)
        stats = ctk.CTkFrame(self, fg_color=BG)
        stats.pack(fill="x", padx=16, pady=(10, 0))
        self.lbl_visible = self._stat(stats, "Visible", "0", CYAN)
        self.lbl_warning = self._stat(stats, "In range", "0", GREEN)
        self.lbl_hidden = self._stat(stats, "Hidden", "0", ORANGE)
        self.lbl_alerts = self._stat(stats, "Alerts", "0", RED)
        self.lbl_packets = self._stat(stats, "Live pkts", "0", MAGENTA)
        self.lbl_uptime = self._stat(stats, "Uptime", "0s", MUTED)
        ctrl = ctk.CTkFrame(self, fg_color=BG)
        ctrl.pack(fill="x", padx=16, pady=10)
        self.btn_scan = ctk.CTkButton(ctrl, text="START SCAN", command=self.toggle, width=180, height=42, font=ctk.CTkFont(size=14, weight="bold"), fg_color=PANEL, border_width=2, border_color=CYAN, text_color=CYAN, hover_color="#0A2030")
        self.btn_scan.pack(side="left", padx=(0, 12))
        ctk.CTkButton(ctrl, text="Clear list", width=100, height=36, fg_color=PANEL2, text_color=MUTED, command=self._clear).pack(side="left", padx=4)
        self.search_var = ctk.StringVar()
        ctk.CTkEntry(ctrl, placeholder_text="Search name / MAC...", textvariable=self.search_var, width=220, height=36, fg_color=PANEL2, border_color=MUTED).pack(side="left", padx=12)
        self.var_hidden = ctk.BooleanVar(value=False)
        self.var_range = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(ctrl, text="Hidden only", variable=self.var_hidden, text_color=MUTED, fg_color=CYAN).pack(side="left", padx=8)
        ctk.CTkCheckBox(ctrl, text="In range only", variable=self.var_range, text_color=MUTED, fg_color=CYAN).pack(side="left", padx=8)
        self.sort_var = ctk.StringVar(value=app_settings["sort_by"])
        ctk.CTkLabel(ctrl, text="Sort:", text_color=MUTED).pack(side="left", padx=(16, 4))
        ctk.CTkOptionMenu(ctrl, values=["distance", "rssi", "name", "last_seen"], variable=self.sort_var, width=120, height=32, fg_color=PANEL2, button_color=PANEL).pack(side="left")
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color=BG, corner_radius=0)
        self.list_frame.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        ctk.CTkLabel(self, text="Live scan: devices appear as BLE packets arrive | Bluetooth must be ON", text_color=MUTED, font=ctk.CTkFont(size=11)).pack(pady=(0, 8))

    def _stat(self, parent, label, value, color):
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.pack(side="left", expand=True)
        val = ctk.CTkLabel(col, text=value, text_color=color, font=ctk.CTkFont(size=18, weight="bold"))
        val.pack()
        ctk.CTkLabel(col, text=label, text_color=MUTED, font=ctk.CTkFont(size=11)).pack()
        return val

    def toggle(self):
        if self.scanner.is_scanning:
            self.scanner.stop()
            self.btn_scan.configure(text="START SCAN", border_color=CYAN, text_color=CYAN)
            self.status_dot.configure(text_color="#333")
            self.lbl_status.configure(text="Stopping...", text_color=MUTED)
            self._save_prefs()
        else:
            self.scanner.min_rssi = app_settings["min_rssi"]
            self.scanner.warn_distance = app_settings["warn_distance"]
            self.start_time = time.time()
            if not self.scanner.start():
                messagebox.showerror("Error", "Cannot start scanner (bleak missing or already running)")
                return
            self.btn_scan.configure(text="STOP SCAN", border_color=RED, text_color=RED)
            self.status_dot.configure(text_color=GREEN)
            self.lbl_status.configure(text="Scanning live...", text_color=GREEN)

    def _queue_alert(self, device: DeviceInfo):
        self._pending_alert = device

    def _queue_status(self, text: str):
        self._pending_status = text

    def _tick(self):
        if self._pending_status is not None:
            t = self._pending_status
            self._pending_status = None
            color = RED if t.startswith("ERROR") else (MUTED if t == "Stopped" else GREEN)
            self.lbl_status.configure(text=t[:90], text_color=color)
            if t == "Stopped":
                self.btn_scan.configure(text="START SCAN", border_color=CYAN, text_color=CYAN)
                self.status_dot.configure(text_color="#333")
            if t.startswith("ERROR"):
                self.status_dot.configure(text_color=RED)
        if self._pending_alert is not None:
            d = self._pending_alert
            self._pending_alert = None
            self.total_alerts += 1
            if app_settings["flash_title"]:
                orig = self.title()
                self.title(f"IN RANGE - {d.display_name} ({d.distance:.1f} m)")
                self.after(3000, lambda: self.title(orig))
            if app_settings["sound_alerts"] and WINSOUND_OK:
                try:
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                except Exception:
                    pass
        self._refresh()
        self.after(UI_MS, self._tick)

    def _filtered(self):
        items = self.scanner.snapshot()
        q = self.search_var.get().strip().lower()
        if q:
            items = [d for d in items if q in d.display_name.lower() or q in d.address.lower()]
        if self.var_hidden.get():
            items = [d for d in items if d.is_hidden]
        if self.var_range.get():
            items = [d for d in items if d.in_range(app_settings["warn_distance"])]
        key = self.sort_var.get()
        if key == "distance":
            items.sort(key=lambda d: (d.distance, -d.rssi))
        elif key == "rssi":
            items.sort(key=lambda d: -d.rssi)
        elif key == "name":
            items.sort(key=lambda d: d.display_name.lower())
        else:
            items.sort(key=lambda d: -d.last_seen)
        return items

    def _refresh(self):
        st = self.scanner.stats()
        self.lbl_visible.configure(text=str(st["visible"]))
        self.lbl_warning.configure(text=str(st["in_range"]), text_color=RED if st["in_range"] else GREEN)
        self.lbl_hidden.configure(text=str(st["hidden"]))
        self.lbl_alerts.configure(text=str(self.total_alerts))
        self.lbl_packets.configure(text=str(st["packets"]))
        up = int(time.time() - self.start_time) if self.scanner.is_scanning else 0
        m, s = divmod(up, 60)
        self.lbl_uptime.configure(text=f"{m}m {s}s" if m else f"{s}s")
        if self.scanner.is_scanning and st["packets"] > 0:
            self.lbl_status.configure(text=f"Live | {st['packets']} packets | {st['visible']} devices", text_color=GREEN)
        sorted_devs = self._filtered()
        current = {d.address for d in sorted_devs}
        for addr in list(self.device_widgets):
            if addr not in current:
                try:
                    self.device_widgets[addr].destroy()
                except Exception:
                    pass
                del self.device_widgets[addr]
        for d in sorted_devs:
            if d.address not in self.device_widgets:
                self.device_widgets[d.address] = self._card(d)
            else:
                self._update_card(self.device_widgets[d.address], d)

    def _card(self, d: DeviceInfo):
        border = RED if d.in_range(app_settings["warn_distance"]) else (ORANGE if d.is_hidden else PANEL)
        frame = ctk.CTkFrame(self.list_frame, fg_color=PANEL, border_width=1, border_color=border, corner_radius=12)
        frame.pack(fill="x", pady=3, padx=4)
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=14, pady=(10, 2))
        left = ctk.CTkFrame(top, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        star = "* " if d.address in self.favorites else ""
        name_lbl = ctk.CTkLabel(left, text=f"{star}{d.display_name}", font=ctk.CTkFont(size=15, weight="bold"), text_color=WHITE, anchor="w")
        name_lbl.pack(anchor="w")
        frame.name_lbl = name_lbl
        ctk.CTkLabel(left, text=d.address, font=ctk.CTkFont(size=11, family="Consolas"), text_color=MUTED, anchor="w").pack(anchor="w")
        dc = RED if d.distance <= 1.5 else (ORANGE if d.distance <= 4 else CYAN)
        dist_lbl = ctk.CTkLabel(top, text=f"{d.distance:.1f} m", font=ctk.CTkFont(size=15, weight="bold"), text_color=dc)
        dist_lbl.pack(side="right")
        frame.dist_lbl = dist_lbl
        meta = ctk.CTkFrame(frame, fg_color="transparent")
        meta.pack(fill="x", padx=14, pady=(2, 10))
        info = ctk.CTkLabel(meta, text=f"{d.rssi} dBm | {d.device_type} | x{d.times_seen}", font=ctk.CTkFont(size=12), text_color=CYAN, anchor="w")
        info.pack(side="left")
        frame.info_lbl = info
        ctk.CTkButton(meta, text="Copy", width=50, height=24, font=ctk.CTkFont(size=11), fg_color=PANEL2, text_color=MUTED, command=lambda a=d.address: self._copy(a)).pack(side="right", padx=2)
        ctk.CTkButton(meta, text="Ignore", width=55, height=24, font=ctk.CTkFont(size=11), fg_color=PANEL2, text_color=RED, command=lambda a=d.address: self._ignore(a)).pack(side="right", padx=2)
        ctk.CTkButton(meta, text="Fav", width=45, height=24, font=ctk.CTkFont(size=11), fg_color=PANEL2, text_color=ORANGE, command=lambda a=d.address: self._fav(a)).pack(side="right", padx=2)
        return frame

    def _update_card(self, frame, d: DeviceInfo):
        try:
            star = "* " if d.address in self.favorites else ""
            frame.name_lbl.configure(text=f"{star}{d.display_name}")
            dc = RED if d.distance <= 1.5 else (ORANGE if d.distance <= 4 else CYAN)
            frame.dist_lbl.configure(text=f"{d.distance:.1f} m", text_color=dc)
            frame.info_lbl.configure(text=f"{d.rssi} dBm | {d.device_type} | x{d.times_seen}")
            frame.configure(border_color=RED if d.in_range(app_settings["warn_distance"]) else (ORANGE if d.is_hidden else PANEL))
        except Exception:
            pass

    def _copy(self, addr):
        self.clipboard_clear()
        self.clipboard_append(addr)
        self.lbl_status.configure(text=f"Copied {addr}", text_color=CYAN)

    def _ignore(self, addr):
        self.scanner.ignore(addr)
        self._save_prefs()

    def _fav(self, addr):
        if addr in self.favorites:
            self.favorites.discard(addr)
        else:
            self.favorites.add(addr)
        self._save_prefs()

    def _clear(self):
        self.scanner.clear()
        for w in list(self.device_widgets.values()):
            try:
                w.destroy()
            except Exception:
                pass
        self.device_widgets.clear()

    def _settings(self):
        win = ctk.CTkToplevel(self)
        win.title("Settings")
        win.geometry("400x360")
        win.configure(fg_color=BG)
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="Settings", font=ctk.CTkFont(size=20, weight="bold"), text_color=CYAN).pack(pady=14)
        ctk.CTkLabel(win, text="Warning distance (m)", text_color=MUTED).pack(anchor="w", padx=24)
        dist_var = ctk.DoubleVar(value=app_settings["warn_distance"])
        ctk.CTkSlider(win, from_=2, to=30, variable=dist_var, number_of_steps=28, progress_color=CYAN).pack(fill="x", padx=24, pady=4)
        dist_lbl = ctk.CTkLabel(win, text=f"{app_settings['warn_distance']:.0f} m", text_color=WHITE)
        dist_lbl.pack()
        dist_var.trace_add("write", lambda *_: dist_lbl.configure(text=f"{dist_var.get():.0f} m"))
        ctk.CTkLabel(win, text="Min RSSI (dBm)", text_color=MUTED).pack(anchor="w", padx=24, pady=(10, 0))
        rssi_var = ctk.IntVar(value=app_settings["min_rssi"])
        ctk.CTkSlider(win, from_=-120, to=-50, variable=rssi_var, number_of_steps=70, progress_color=CYAN).pack(fill="x", padx=24, pady=4)
        rssi_lbl = ctk.CTkLabel(win, text=f"{app_settings['min_rssi']} dBm", text_color=WHITE)
        rssi_lbl.pack()
        rssi_var.trace_add("write", lambda *_: rssi_lbl.configure(text=f"{rssi_var.get()} dBm"))
        sound_var = ctk.BooleanVar(value=app_settings["sound_alerts"])
        flash_var = ctk.BooleanVar(value=app_settings["flash_title"])
        ctk.CTkCheckBox(win, text="Sound alerts", variable=sound_var, text_color=WHITE, fg_color=CYAN).pack(anchor="w", padx=24, pady=8)
        ctk.CTkCheckBox(win, text="Flash title on alert", variable=flash_var, text_color=WHITE, fg_color=CYAN).pack(anchor="w", padx=24, pady=4)
        def save():
            app_settings["warn_distance"] = float(dist_var.get())
            app_settings["min_rssi"] = int(rssi_var.get())
            app_settings["sound_alerts"] = bool(sound_var.get())
            app_settings["flash_title"] = bool(flash_var.get())
            self.scanner.warn_distance = app_settings["warn_distance"]
            self.scanner.min_rssi = app_settings["min_rssi"]
            self._save_prefs()
            win.destroy()
        ctk.CTkButton(win, text="Save", command=save, fg_color=CYAN, text_color=BG, width=120).pack(pady=16)

    def _export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv"), ("JSON", "*.json")])
        if not path:
            return
        snap = self.scanner.snapshot()
        try:
            if path.lower().endswith(".json"):
                data = [{"address": d.address, "name": d.display_name, "rssi": d.rssi, "distance_m": round(d.distance, 2), "type": d.device_type, "hidden": d.is_hidden, "times_seen": d.times_seen} for d in snap]
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            else:
                with open(path, "w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["address", "name", "rssi", "distance_m", "type", "hidden", "times_seen"])
                    for d in snap:
                        w.writerow([d.address, d.display_name, d.rssi, f"{d.distance:.2f}", d.device_type, d.is_hidden, d.times_seen])
            messagebox.showinfo("Export", f"Saved {len(snap)} devices")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _on_close(self):
        self.scanner.stop()
        self._save_prefs()
        self.destroy()

def main():
    if getattr(sys, "frozen", False):
        try:
            import bleak.backends  # noqa: F401
        except Exception:
            pass
    BlueRadarApp().mainloop()

if __name__ == "__main__":
    main()
