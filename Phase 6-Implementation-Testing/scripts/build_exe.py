#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
PROJECT : Autocad-map-3d-PostgreSQL-Connector
MODULE  : PyInstaller Build Script
PHASE   : Phase 6 -- Deployment & Industrialization
===============================================================================

DESCRIPTION:
    Compiles gui_tray_app.py into a standalone Windows executable using
    PyInstaller. The resulting .exe bundles Python + all dependencies.
    No Python installation is required on the end-user machine.

USAGE:
    cd Phase 6-Implementation-Testing/scripts
    python build_exe.py

OUTPUT:
    dist/PostMapLive.exe   (single-file executable)
===============================================================================
"""

import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent
DIST_DIR    = SCRIPTS_DIR.parent / "dist"
BUILD_DIR   = SCRIPTS_DIR.parent / "build"


def main():
    print("=" * 65)
    print("  Building PostMapLive.exe with PyInstaller")
    print("=" * 65)

    ASSETS_DIR  = SCRIPTS_DIR.parent / "assets"
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                                # Single .exe
        "--noconsole",                              # No terminal window (GUI mode)
        "--name", "PostMapLive",
        "--icon", str(ASSETS_DIR / "app_logo.ico"), # App logo for .exe
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--add-data", f"{SCRIPTS_DIR / 'watch_and_sync.py'};.",
        "--add-data", f"{SCRIPTS_DIR / 'convert_autodesk_to_postgis.py'};.",
        "--add-data", f"{ASSETS_DIR};assets",
        # Hidden imports needed at runtime
        "--hidden-import", "pystray",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL._tkinter_finder",
        "--hidden-import", "psycopg2",
        "--hidden-import", "watchdog",
        "--hidden-import", "watchdog.observers",
        "--hidden-import", "watchdog.events",
        "--hidden-import", "watchdog.observers.polling",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.scrolledtext",
        str(SCRIPTS_DIR / "gui_tray_app.py"),
    ]

    exe_path = DIST_DIR / "PostMapLive.exe"
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    if exe_path.exists():
        try:
            exe_path.unlink()
            print(f"Removed previous executable: {exe_path}")
        except PermissionError:
            print(f"Could not remove existing executable (it may be running): {exe_path}")
            print("Please close the program and retry.")
            sys.exit(1)

    print(f"\nRunning: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(SCRIPTS_DIR))

    if result.returncode == 0:
        print("\n" + "=" * 65)
        print("  ✅ Build successful!")
        print(f"  Output: {exe_path}")
        print("=" * 65)
    else:
        print("\n❌ Build failed. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
