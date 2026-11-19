# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all

aiortc_datas, aiortc_binaries, aiortc_hiddenimports = collect_all('aiortc')
av_datas, av_binaries, av_hiddenimports = collect_all('av')
mss_datas, mss_binaries, mss_hiddenimports = collect_all('mss')
pillow_datas, pillow_binaries, pillow_hiddenimports = collect_all('PIL')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=(
        aiortc_binaries + av_binaries + mss_binaries + pillow_binaries
    ),
    datas=(
        aiortc_datas + av_datas + mss_datas + pillow_datas
    ),
    hiddenimports=(
        aiortc_hiddenimports + av_hiddenimports
        + mss_hiddenimports + pillow_hiddenimports
    ),
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
    name='main',
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
    name='main',
)
