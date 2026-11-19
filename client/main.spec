# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


def collect_vlc_runtime():
    vlc_dir_value = os.environ.get("VLC_DIR")
    if not vlc_dir_value:
        raise EnvironmentError(
            "VLC_DIR is not set. Run build.ps1 to download and prepare the VLC runtime."
        )

    vlc_root = Path(vlc_dir_value)
    if not (
        (vlc_root / "libvlc.dll").is_file()
        and (vlc_root / "libvlccore.dll").is_file()
        and (vlc_root / "plugins").is_dir()
    ):
        raise FileNotFoundError(
            "The VLC runtime directory is incomplete: " + str(vlc_root)
        )

    binaries = []
    datas = []

    # Collect VLC core DLL files
    for file in vlc_root.glob("*.dll"):
        binaries.append((str(file), "vlc"))

    # Collect VLC plugins and their resource files
    plugins_dir = vlc_root / "plugins"
    for file in plugins_dir.rglob("*"):
        if not file.is_file():
            continue

        relative_parent = file.relative_to(plugins_dir).parent
        destination = str(Path("vlc") / "plugins" / relative_parent)
        item = (str(file), destination)

        if file.suffix.lower() == ".dll":
            binaries.append(item)
        else:
            datas.append(item)

    return binaries, datas


# Collect PySide6 and third-party dependencies
pyside6_datas, pyside6_binaries, pyside6_hiddenimports = collect_all("PySide6")
aiortc_datas, aiortc_binaries, aiortc_hiddenimports = collect_all("aiortc")
av_datas, av_binaries, av_hiddenimports = collect_all("av")
mss_datas, mss_binaries, mss_hiddenimports = collect_all("mss")
pillow_datas, pillow_binaries, pillow_hiddenimports = collect_all("PIL")

vlc_binaries, vlc_datas = collect_vlc_runtime()

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=(
        pyside6_binaries
        + aiortc_binaries
        + av_binaries
        + mss_binaries
        + pillow_binaries
        + vlc_binaries
    ),
    datas=(
        pyside6_datas
        + aiortc_datas
        + av_datas
        + mss_datas
        + pillow_datas
        + vlc_datas
    ),
    hiddenimports=(
        pyside6_hiddenimports
        + aiortc_hiddenimports
        + av_hiddenimports
        + mss_hiddenimports
        + pillow_hiddenimports
        + ["vlc"]
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["rthook_vlc.py"],
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
    name="main",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
    upx=False,
    upx_exclude=[],
    name="main",
)
