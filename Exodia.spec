# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['desktop_app/exodia_desktop.py'],
    pathex=[],
    binaries=[],
    datas=[('desktop_app/index.html', 'desktop_app'), ('desktop_app/logo.ico', 'desktop_app'), ('config', 'config')],
    hiddenimports=['PIL', 'networkx', 'matplotlib', 'neo4j', 'pywebview'],
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
    name='Exodia',
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
    icon=['desktop_app/logo.ico'],
)
