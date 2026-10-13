"""Live BLE scanner - thread-safe."""
from __future__ import annotations
import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

try:
    from bleak import BleakScanner
    BLEAK_OK = True
except ImportError:
    BLEAK_OK = False

STALE_SEC = 60

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

    def in_range(self, warn: float) -> bool:
        return self.distance <= warn

    @property
    def display_name(self) -> str:
        return self.name.strip() if self.name and self.name.strip() else "Hidden Device"


def estimate_distance(rssi: int, tx_power: int = -59, n: float = 2.2) -> float:
    if rssi >= 0:
        return 0.5
    return min(10 ** ((tx_power - rssi) / (10.0 * n)), 99.0)


def classify_name(name: str) -> str:
    if not name:
        return "Unknown"
    n = name.lower()
    rules = [
        (("airpods", "buds", "headset", "headphone", "beats"), "Headset"),
        (("airtag", "tile", "smarttag", "tracker", "find my"), "Tracker"),
        (("watch", "band", "fitbit", "garmin"), "Wearable"),
        (("speaker", "homepod", "echo", "soundbar", "jbl"), "Speaker"),
        (("iphone", "pixel", "galaxy", "phone", "oneplus"), "Phone"),
        (("macbook", "laptop", "pc", "desktop", "surface"), "Computer"),
        (("keyboard", "mouse", "trackpad", "magic"), "Input"),
    ]
    for keys, label in rules:
        if any(x in n for x in keys):
            return label
    return "Unknown"


class LiveScanner:
    """Background BLE scanner. UI must only touch devices via snapshot()."""

    def __init__(self, min_rssi: int = -120, warn_distance: float = 10.0):
        self.min_rssi = min_rssi
        self.warn_distance = warn_distance
        self._lock = threading.Lock()
        self.devices: Dict[str, DeviceInfo] = {}
        self.blacklist: Set[str] = set()
        self.packets = 0
        self.session_seen: Set[str] = set()
        self.is_scanning = False
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._loop = None
        self.last_error = ""
        self.on_alert: Optional[Callable[[DeviceInfo], None]] = None
        self.on_status: Optional[Callable[[str], None]] = None
        self._alerted: Dict[str, float] = {}

    def start(self):
        if self.is_scanning or not BLEAK_OK:
            return False
        self.is_scanning = True
        self._stop.clear()
        self.last_error = ""
        self._thread = threading.Thread(target=self._run, daemon=True, name="ble-scan")
        self._thread.start()
        return True

    def stop(self):
        self.is_scanning = False
        self._stop.set()
        if self._loop is not None:
            try:
                self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass

    def snapshot(self) -> List[DeviceInfo]:
        with self._lock:
            return list(self.devices.values())

    def stats(self):
        with self._lock:
            items = list(self.devices.values())
            return {
                "visible": len(items),
                "in_range": sum(1 for d in items if d.in_range(self.warn_distance)),
                "hidden": sum(1 for d in items if d.is_hidden),
                "packets": self.packets,
                "session": len(self.session_seen),
            }

    def clear(self):
        with self._lock:
            self.devices.clear()

    def ignore(self, addr: str):
        self.blacklist.add(addr.upper())
        with self._lock:
            self.devices.pop(addr.upper(), None)

    def _run(self):
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._scan())
        except Exception as e:
            self.last_error = f"{type(e).__name__}: {e}"
            if self.on_status:
                self.on_status(f"ERROR: {self.last_error}")
        finally:
            try:
                if self._loop and not self._loop.is_closed():
                    self._loop.close()
            except Exception:
                pass
            self._loop = None
            self.is_scanning = False
            if self.on_status:
                self.on_status("Stopped")

    async def _scan(self):
        def on_detect(device, adv):
            if not self.is_scanning or self._stop.is_set():
                return
            try:
                rssi = getattr(adv, "rssi", None)
                if rssi is None:
                    rssi = getattr(device, "rssi", None)
                try:
                    rssi = int(rssi) if rssi is not None else -100
                except (TypeError, ValueError):
                    rssi = -100
                if rssi < self.min_rssi:
                    return
                addr = (device.address or "").upper()
                if not addr or addr in self.blacklist:
                    return
                name = ""
                if device.name:
                    name = str(device.name)
                elif getattr(adv, "local_name", None):
                    name = str(adv.local_name)
                dist = estimate_distance(rssi)
                now = time.time()
                hidden = not bool(name.strip())
                dtype = classify_name(name)
                alert_dev = None
                with self._lock:
                    self.packets += 1
                    if addr in self.devices:
                        d = self.devices[addr]
                        d.rssi = rssi
                        d.distance = dist
                        d.last_seen = now
                        if name:
                            d.name = name
                            d.is_hidden = False
                        d.rssi_history = (d.rssi_history + [rssi])[-40:]
                        d.times_seen += 1
                        if dtype != "Unknown":
                            d.device_type = dtype
                    else:
                        self.devices[addr] = DeviceInfo(
                            address=addr, name=name, rssi=rssi, distance=dist,
                            first_seen=now, last_seen=now, rssi_history=[rssi],
                            is_hidden=hidden, device_type=dtype,
                        )
                        self.session_seen.add(addr)
                    if self.devices[addr].in_range(self.warn_distance):
                        alert_dev = self.devices[addr]
                if alert_dev is not None:
                    self._maybe_alert(alert_dev)
            except Exception:
                pass

        scanner = BleakScanner(detection_callback=on_detect)
        await scanner.start()
        if self.on_status:
            self.on_status("Live scanning - packets appear as they arrive")
        try:
            while self.is_scanning and not self._stop.is_set():
                await asyncio.sleep(0.25)
                now = time.time()
                with self._lock:
                    for a in [a for a, d in self.devices.items() if now - d.last_seen > STALE_SEC]:
                        del self.devices[a]
        finally:
            try:
                await scanner.stop()
            except Exception:
                pass

    def _maybe_alert(self, device: DeviceInfo):
        now = time.time()
        if now - self._alerted.get(device.address, 0) < 45:
            return
        self._alerted[device.address] = now
        device.alert_count += 1
        if self.on_alert:
            self.on_alert(device)
