# -*- mode: python ; coding: utf-8 -*-
import os

ICON = os.path.join(SPECPATH, '..', 'assets', 'icon.icns')

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
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
    [],
    exclude_binaries=True,
    name='ACCF-SDHC-Patcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ACCF-SDHC-Patcher',
)
app = BUNDLE(
    coll,
    name='ACCF-SDHC-Patcher.app',
    icon=ICON,
    bundle_identifier='net.quatric.accf-sdhc-patcher',
)
