"""Windows in-app updater — checks GitHub Releases and replaces the EXE."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import urllib.request
from typing import Callable, Optional, Tuple

REPO = "someone405-ship-it/BlueRadar"
VERSION_URL = f"https://raw.githubusercontent.com/{REPO}/main/VERSION"
RELEASES_API = f"https://api.github.com/repos/{REPO}/releases/latest"
APP_VERSION = "1.1.0"
USER_AGENT = f"BlueRadar/{APP_VERSION}"


def current_version() -> str:
    return APP_VERSION


def _http_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_remote_version() -> Optional[str]:
    try:
        raw = _http_get(VERSION_URL, timeout=10).decode("utf-8").strip()
        for line in raw.splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return line
    except Exception:
        return None
    return None


def _parse_ver(v: str) -> Tuple[int, ...]:
    parts = []
    for p in v.strip().lstrip("vV").split("."):
        try:
            parts.append(int(p))
        except ValueError:
            parts.append(0)
    return tuple(parts) if parts else (0,)


def is_newer(remote: str, local: str = APP_VERSION) -> bool:
    try:
        return _parse_ver(remote) > _parse_ver(local)
    except Exception:
        return False


def find_exe_download_url() -> Optional[str]:
    try:
        data = json.loads(_http_get(RELEASES_API, timeout=15).decode("utf-8"))
        for asset in data.get("assets") or []:
            name = (asset.get("name") or "").lower()
            if name.endswith(".exe") and "blueradar" in name:
                return asset.get("browser_download_url")
        for asset in data.get("assets") or []:
            if (asset.get("name") or "").lower().endswith(".exe"):
                return asset.get("browser_download_url")
    except Exception:
        pass
    return None


def download_file(url: str, dest: str, progress: Optional[Callable[[int, int], None]] = None) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        with open(dest, "wb") as out:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)


def apply_update(downloaded_exe: str) -> str:
    if not getattr(sys, "frozen", False):
        return ""
    current = sys.executable
    bat = os.path.join(tempfile.gettempdir(), "blueradar_update.bat")
    script = f"""@echo off
timeout /t 2 /nobreak >nul
copy /Y "{downloaded_exe}" "{current}"
start "" "{current}"
del "%~f0"
"""
    with open(bat, "w", encoding="utf-8") as f:
        f.write(script)
    return bat


def check_for_update() -> dict:
    local = APP_VERSION
    remote = fetch_remote_version()
    if not remote:
        return {"available": False, "local_version": local, "remote_version": None, "download_url": None, "error": "Could not reach update server"}
    if not is_newer(remote, local):
        return {"available": False, "local_version": local, "remote_version": remote, "download_url": None, "error": None}
    url = find_exe_download_url()
    if not url:
        return {
            "available": True,
            "local_version": local,
            "remote_version": remote,
            "download_url": None,
            "error": "Update found but no EXE on GitHub Releases yet",
        }
    return {"available": True, "local_version": local, "remote_version": remote, "download_url": url, "error": None}


def run_update_async(on_progress: Callable[[str], None], on_done: Callable[[bool, str], None]) -> None:
    def worker():
        try:
            info = check_for_update()
            if not info["available"]:
                on_done(False, info.get("error") or f"Up to date (v{info['local_version']})")
                return
            url = info.get("download_url")
            if not url:
                on_done(False, info.get("error") or "No download URL")
                return
            on_progress(f"Downloading v{info['remote_version']}...")
            dest = os.path.join(tempfile.gettempdir(), "BlueRadar_update.exe")

            def prog(done, total):
                if total > 0:
                    on_progress(f"Downloading... {int(100 * done / total)}%")
                else:
                    on_progress(f"Downloading... {done // 1024} KB")

            download_file(url, dest, progress=prog)
            bat = apply_update(dest)
            if bat:
                on_progress("Installing... app will restart")
                on_done(True, bat)
            else:
                on_done(True, f"Downloaded to {dest}")
        except Exception as e:
            on_done(False, str(e))

    threading.Thread(target=worker, daemon=True, name="updater").start()
