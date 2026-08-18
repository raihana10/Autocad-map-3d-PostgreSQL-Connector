#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
PROJECT : Autocad-map-3d-PostgreSQL-Connector
MODULE  : System Tray GUI Application (Admin Panel + Background Service)
PHASE   : Phase 6 -- Deployment & Industrialization
===============================================================================

DESCRIPTION:
    This module provides the end-user facing graphical interface for the
    Autodesk-to-PostgreSQL synchronization service.

    Components:
    - System Tray Icon (pystray):  Displays service status in the Windows
      system tray (near clock). Right-click menu: Status / Settings / Logs /
      Pause / Exit.
    - Settings Panel (tkinter):    GUI form for PostgreSQL credentials, SRID,
      and watched directory. Settings are persisted to a local JSON config file.
    - Background Sync Engine:       Runs watch_and_sync.main() in a daemon
      thread so the GUI remains responsive.

DEPENDENCIES:
    pip install pystray pillow psycopg2-binary watchdog

USAGE (development):
    python gui_tray_app.py

USAGE (packaged):
    dist/PostMapLive.exe  (compiled via build_exe.py)
===============================================================================
"""

import os
import sys
import json
import ctypes
import threading
import logging
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Resolve working directory (handles both dev mode and PyInstaller onefile)
# ---------------------------------------------------------------------------
# IMPORTANT: Config and logs MUST be stored in a user-writable directory.
# Writing to the install dir (e.g. Program Files) causes PermissionError.
# We use %APPDATA%\PostMapLive which is always writable.
BASE_DIR = Path(__file__).resolve().parent

APP_DATA_DIR = Path(os.environ.get("APPDATA", Path.home())) / "PostMapLive"
APP_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Persistent config/log storage (AppData, not the temp extraction folder used by PyInstaller)
CONFIG_ENV_FILE = APP_DATA_DIR / "config.env"
CONFIG_FILE     = APP_DATA_DIR / "connector_config.json"
LOG_FILE        = APP_DATA_DIR / "connector.log"


# ---------------------------------------------------------------------------
# Logging setup (dual: file + in-memory for GUI log viewer)
# ---------------------------------------------------------------------------
log_memory_handler = None

def setup_logging():
    global log_memory_handler
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter(fmt))
    root.addHandler(ch)

    # File handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter(fmt))
    root.addHandler(fh)

    # In-memory handler for GUI log viewer
    log_memory_handler = _MemoryLogHandler()
    log_memory_handler.setFormatter(logging.Formatter(fmt))
    root.addHandler(log_memory_handler)

logger = logging.getLogger(__name__)


class _MemoryLogHandler(logging.Handler):
    """Keeps the last 500 log lines in memory for the GUI log viewer."""
    def __init__(self):
        super().__init__()
        self.records = []
        self._lock = threading.Lock()

    def emit(self, record):
        with self._lock:
            self.records.append(self.format(record))
            if len(self.records) > 500:
                self.records.pop(0)

    def get_logs(self):
        with self._lock:
            return list(self.records)


# ---------------------------------------------------------------------------
# Config helpers (reads and writes config.env)
# ---------------------------------------------------------------------------
DEFAULT_CONFIG = {
    "pg_host": "localhost",
    "pg_port": "5432",
    "pg_user": "postgres",
    "pg_pass": "",
    "srid": "2154",
    "auto_start": True,
}

def find_config_env_file() -> Path:
    """Finds a persistent config file in AppData first, then falls back to local files."""
    candidates = [
        APP_DATA_DIR / "config.env",
        APP_DATA_DIR / ".env",
        BASE_DIR / "config.env",
        BASE_DIR / ".env",
        BASE_DIR.parent / "config.env",
        BASE_DIR.parent / ".env",
        Path.cwd() / "config.env",
        Path.cwd() / ".env",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return APP_DATA_DIR / "config.env"

def load_config() -> dict:
    """Reads config.env or .env and returns a dictionary of settings."""
    cfg = dict(DEFAULT_CONFIG)
    target_env = find_config_env_file()
    if not target_env.exists():
        save_config(cfg)
        return cfg

    try:
        with open(target_env, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip().upper()
                v = v.strip().strip("'\"")
                if k == "PG_HOST":
                    cfg["pg_host"] = v
                elif k == "PG_PORT":
                    cfg["pg_port"] = v
                elif k == "PG_USER":
                    cfg["pg_user"] = v
                elif k in ("PG_PASS", "PG_PASSWORD"):
                    cfg["pg_pass"] = v
                elif k in ("PG_SRID", "SRID"):
                    cfg["srid"] = v
                elif k == "AUTO_START":
                    cfg["auto_start"] = (v.lower() in ("true", "1", "yes"))
        logger.info("Loaded credentials from: %s", target_env)
    except Exception as err:
        logger.warning("Could not read env file '%s': %s", target_env, err)
    return cfg

def save_config(cfg: dict):
    """Persists settings to the persistent AppData config.env file."""
    target_env = APP_DATA_DIR / "config.env"
    target_env.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# ===========================================================================",
        "# PostMap Live Configuration File",
        "# ===========================================================================",
        f"PG_HOST={cfg.get('pg_host', 'localhost')}",
        f"PG_PORT={cfg.get('pg_port', '5432')}",
        f"PG_USER={cfg.get('pg_user', 'postgres')}",
        f"PG_PASS={cfg.get('pg_pass', '')}",
        f"PG_SRID={cfg.get('srid', '2154')}",
        f"AUTO_START={'True' if cfg.get('auto_start', True) else 'False'}",
    ]
    with open(target_env, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info("Saved settings to %s", target_env)


# ---------------------------------------------------------------------------
# Sync Engine wrapper
# ---------------------------------------------------------------------------
class SyncEngine:
    """Wraps watch_and_sync in a stoppable background daemon thread."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self.status = "Stopped"
        self.last_sync: str | None = None

    def start(self, cfg: dict):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.status = "Running"
        self._thread = threading.Thread(
            target=self._run,
            args=(cfg,),
            daemon=True,
            name="SyncEngineThread",
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        self.status = "Stopped"

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def _run(self, cfg: dict):
        """Import and run watch_and_sync main function."""
        try:
            # Add scripts dir to path so we can import watch_and_sync
            scripts_dir = str(Path(__file__).parent)
            if scripts_dir not in sys.path:
                sys.path.insert(0, scripts_dir)

            import watch_and_sync as ws

            args_list = [
                "--pg-host", cfg.get("pg_host", "localhost"),
                "--pg-port", str(cfg.get("pg_port", "5432")),
                "--pg-user", cfg.get("pg_user", "postgres"),
                "--pg-pass", cfg.get("pg_pass", ""),
                "--srid",    str(cfg.get("srid", "2154")),
                "--initial-sync",
            ]

            import argparse
            parser = ws.build_arg_parser() if hasattr(ws, "build_arg_parser") else _build_fallback_parser()
            parsed = parser.parse_args(args_list)

            ws.setup_logging(log_file=str(LOG_FILE))
            ws.main(parsed, stop_event=self._stop_event)
        except Exception as exc:
            logger.error(f"Sync engine error: {exc}", exc_info=True)
            self.status = f"Error: {exc}"


def _build_fallback_parser():
    """Fallback argparse parser if watch_and_sync doesn't expose build_arg_parser()."""
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--pg-host", default="localhost")
    p.add_argument("--pg-port", default="5432")
    p.add_argument("--pg-user", default="postgres")
    p.add_argument("--pg-pass", default="")
    p.add_argument("--srid", default="2154")
    p.add_argument("--dir", default="")
    p.add_argument("--initial-sync", action="store_true")
    return p


# ---------------------------------------------------------------------------
# Settings Window (tkinter)
# ---------------------------------------------------------------------------
class SettingsWindow(tk.Toplevel):
    def __init__(self, parent, cfg: dict, on_save):
        super().__init__(parent)
        self.title("PostMap Live — Settings")
        self.resizable(False, False)
        self.grab_set()

        self._on_save = on_save
        self._cfg = dict(cfg)

        self._fields = {}
        labels = [
            ("pg_host",  "PostgreSQL Host",    "localhost"),
            ("pg_port",  "PostgreSQL Port",    "5432"),
            ("pg_user",  "PostgreSQL User",    "postgres"),
            ("pg_pass",  "PostgreSQL Password",""),
            ("srid",     "SRID / EPSG Code",   "2154"),
        ]

        frame = ttk.LabelFrame(self, text=" PostgreSQL Connection & Sync Settings ", padding=12)
        frame.pack(padx=16, pady=14, fill=tk.BOTH, expand=True)

        for row_idx, (key, label, _) in enumerate(labels):
            ttk.Label(frame, text=label + ":").grid(row=row_idx, column=0, sticky=tk.W, pady=4, padx=4)
            show = "*" if key == "pg_pass" else ""
            var = tk.StringVar(value=str(cfg.get(key, "")))
            entry = ttk.Entry(frame, textvariable=var, width=38, show=show)
            entry.grid(row=row_idx, column=1, sticky=tk.EW, pady=4, padx=4)
            self._fields[key] = var

        self._auto_start_var = tk.BooleanVar(value=cfg.get("auto_start", True))
        ttk.Checkbutton(
            frame, text="Start service automatically with Windows",
            variable=self._auto_start_var
        ).grid(row=len(labels), column=0, columnspan=2, sticky=tk.W, pady=6, padx=4)

        # Buttons
        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="Test Connection", command=self._test_connection).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Save & Restart", command=self._save).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=6)

    def _test_connection(self):
        host = self._fields["pg_host"].get()
        port = self._fields["pg_port"].get()
        user = self._fields["pg_user"].get()
        password = self._fields["pg_pass"].get()
        try:
            import psycopg2
            conn = psycopg2.connect(host=host, port=int(port), user=user, password=password,
                                    dbname="postgres", connect_timeout=5)
            conn.close()
            messagebox.showinfo("Connection OK", f"✅ Successfully connected to PostgreSQL\n{user}@{host}:{port}", parent=self)
        except Exception as e:
            messagebox.showerror("Connection Failed", f"❌ Connection failed:\n{e}", parent=self)

    def _save(self):
        new_cfg = {key: var.get().strip() for key, var in self._fields.items()}
        new_cfg["auto_start"] = self._auto_start_var.get()

        if not new_cfg.get("pg_pass"):
            messagebox.showwarning(
                "Password Required",
                "⚠️ PostgreSQL password cannot be empty. Please enter your password.",
                parent=self
            )
            return

        save_config(new_cfg)
        self._on_save(new_cfg)
        self.destroy()


# ---------------------------------------------------------------------------
# Log Viewer Window (tkinter)
# ---------------------------------------------------------------------------
class LogViewerWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Sync Service — Live Logs")
        self.geometry("820x480")

        self._text = scrolledtext.ScrolledText(self, state=tk.DISABLED, font=("Consolas", 9), wrap=tk.NONE)
        self._text.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(pady=4)
        ttk.Button(btn_frame, text="Refresh", command=self._refresh).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Clear", command=self._clear).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_frame, text="Close", command=self.destroy).pack(side=tk.LEFT, padx=6)

        self._refresh()
        self._schedule_refresh()

    def _refresh(self):
        if log_memory_handler:
            lines = log_memory_handler.get_logs()
            self._text.configure(state=tk.NORMAL)
            self._text.delete("1.0", tk.END)
            self._text.insert(tk.END, "\n".join(lines))
            self._text.see(tk.END)
            self._text.configure(state=tk.DISABLED)

    def _clear(self):
        if log_memory_handler:
            log_memory_handler.records.clear()
        self._text.configure(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.configure(state=tk.DISABLED)

    def _schedule_refresh(self):
        if self.winfo_exists():
            self._refresh()
            self.after(3000, self._schedule_refresh)


# ---------------------------------------------------------------------------
# Main Application (TrayApp)
# ---------------------------------------------------------------------------
class TrayApp:
    """
    Manages the pystray system tray icon and coordinates the tkinter windows.
    All tkinter calls run on the main thread; pystray runs on a daemon thread.
    """

    def __init__(self):
        self.cfg = load_config()
        self.engine = SyncEngine()

        # Hidden tkinter root (never shown directly — keeps event loop alive)
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("PostMap Live")

        self._icon = None
        self._paused = False

    # ---- Tray icon helpers -------------------------------------------------

    def _make_icon_image(self, color: str = "#007ACC"):
        """Loads a larger, more visible tray icon depending on current state."""
        from PIL import Image, ImageDraw

        # Search locations for assets directory (local dev vs PyInstaller bundle)
        assets_candidates = [
            BASE_DIR / "assets",
            BASE_DIR.parent / "assets",
            Path(getattr(sys, "_MEIPASS", BASE_DIR)) / "assets",
            Path.cwd() / "assets",
        ]

        assets_dir = None
        for cand in assets_candidates:
            if cand.is_dir():
                assets_dir = cand
                break

        if self._paused:
            filename = "icon_paused.png"
        elif self.engine.is_running():
            filename = "icon_running.png"
        else:
            filename = "icon_stopped.png"

        if assets_dir:
            img_path = assets_dir / filename
            if img_path.is_file():
                try:
                    img = Image.open(img_path).convert("RGBA")
                    return img.resize((32, 32), Image.Resampling.LANCZOS)
                except Exception as exc:
                    logger.warning(f"Could not load icon {img_path}: {exc}")

        # Fallback if image file is not found
        try:
            img = Image.new("RGBA", (32, 32), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.ellipse([2, 2, 30, 30], fill=color, outline="white", width=2)
            return img
        except Exception:
            return Image.new("RGBA", (32, 32), color=color)

    def _build_menu(self):
        import pystray
        items = []

        if self.engine.is_running() and not self._paused:
            items.append(pystray.MenuItem("Status: 🟢 Active", None, enabled=False))
            items.append(pystray.Menu.SEPARATOR)
            items.append(pystray.MenuItem("⏸ Pause Sync",  lambda icon, item: self._pause_service()))
        elif self._paused:
            items.append(pystray.MenuItem("Status: 🟧 Paused", None, enabled=False))
            items.append(pystray.Menu.SEPARATOR)
            items.append(pystray.MenuItem("▶ Resume Sync", lambda icon, item: self._start_service()))
        else:
            items.append(pystray.MenuItem("Status: 🔴 Stopped", None, enabled=False))
            items.append(pystray.Menu.SEPARATOR)
            items.append(pystray.MenuItem("▶ Start Service", lambda icon, item: self._start_service()))

        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("⚙ Settings",    lambda icon, item: self._open_settings()))
        items.append(pystray.MenuItem("📋 View Logs",  lambda icon, item: self._open_logs()))
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("✖ Quit App",    lambda icon, item: self._exit()))

        return pystray.Menu(*items)

    def _update_icon_color(self):
        if self._icon is None:
            return
        if self._paused:
            color = "#FFA500"    # Orange = paused
        elif self.engine.is_running():
            color = "#28A745"    # Green  = running
        else:
            color = "#DC3545"    # Red    = stopped

        self._icon.icon = self._make_icon_image(color)
        self._icon.menu = self._build_menu()

    # ---- Actions called from tray menu (may be on pystray thread) ----------

    def _open_settings(self):
        self.root.after(0, self._show_settings_window)

    def _open_logs(self):
        self.root.after(0, self._show_log_window)

    def _start_service(self):
        self._paused = False
        self.engine.start(self.cfg)
        logger.info("Sync service started/resumed by user.")
        self._update_icon_color()

    def _pause_service(self):
        self._paused = True
        self.engine.stop()
        logger.info("Sync service paused by user.")
        self._update_icon_color()

    def _stop_service(self):
        # A true Stopped state must use the stopped/red tray icon, not the paused/orange one.
        self._paused = False
        self.engine.stop()
        logger.info("Sync service stopped by user.")
        self._update_icon_color()

    def _exit(self):
        logger.info("Exiting PostMap Live.")
        self.engine.stop()
        if self._icon:
            self._icon.stop()
        self.root.after(0, self.root.destroy)

    # ---- Tkinter window creators (must run on main thread) -----------------

    def _show_settings_window(self):
        def on_save(new_cfg):
            self.cfg = new_cfg
            self.engine.stop()
            threading.Timer(1.0, lambda: self.engine.start(new_cfg)).start()
            logger.info("Settings saved. Restarting sync engine.")
            self._update_icon_color()

        SettingsWindow(self.root, self.cfg, on_save)

    def _show_log_window(self):
        LogViewerWindow(self.root)

    # ---- Entry point -------------------------------------------------------

    def run(self):
        import pystray
        setup_logging()
        logger.info("PostMap Live starting...")

        # Auto-start sync if configured
        if self.cfg.get("auto_start", True):
            self.engine.start(self.cfg)

        icon_img = self._make_icon_image("#28A745" if self.engine.is_running() else "#DC3545")
        self._icon = pystray.Icon(
            name="PostMapLive",
            icon=icon_img,
            title="PostMap Live",
            menu=self._build_menu(),
        )

        # Run pystray on a background thread, tkinter on main thread
        tray_thread = threading.Thread(target=self._icon.run, daemon=True)
        tray_thread.start()

        # tkinter main loop (handles GUI windows)
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def ensure_single_instance():
    """Prevents multiple instances of the tray app from running at once."""
    mutex_name = "Global\\PostMapLiveSingleInstance"
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, mutex_name)
    if mutex is None or ctypes.windll.kernel32.GetLastError() == 183:
        return False
    return True


if __name__ == "__main__":
    if not ensure_single_instance():
        sys.exit(0)

    app = TrayApp()
    app.run()
