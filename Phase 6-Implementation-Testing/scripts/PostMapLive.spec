# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:/Users/pc/Desktop/Autocad map 3d-PostgreSQL-Connector/Phase 6-Implementation-Testing/scripts/gui_tray_app.py'],
    pathex=[],
    binaries=[],
    datas=[('C:/Users/pc/Desktop/Autocad map 3d-PostgreSQL-Connector/Phase 6-Implementation-Testing/scripts/watch_and_sync.py', '.'), ('C:/Users/pc/Desktop/Autocad map 3d-PostgreSQL-Connector/Phase 6-Implementation-Testing/scripts/convert_autodesk_to_postgis.py', '.'), ('C:/Users/pc/Desktop/Autocad map 3d-PostgreSQL-Connector/Phase 6-Implementation-Testing/assets', 'assets')],
    hiddenimports=['pystray', 'PIL', 'PIL._tkinter_finder', 'psycopg2', 'watchdog', 'watchdog.observers', 'watchdog.events', 'watchdog.observers.polling', 'tkinter', 'tkinter.ttk', 'tkinter.scrolledtext'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PostMapLive',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:/Users/pc/Desktop/Autocad map 3d-PostgreSQL-Connector/Phase 6-Implementation-Testing/assets/app_logo.ico'],
)
