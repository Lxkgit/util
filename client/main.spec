# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all


def collect_vlc_runtime():
    # 优先使用 VLC_DIR 指定的安装目录
    candidates = []
    if os.environ.get("VLC_DIR"):
        candidates.append(Path(os.environ["VLC_DIR"]))

    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    candidates.extend([
        Path(program_files) / "VideoLAN" / "VLC",
        Path(program_files_x86) / "VideoLAN" / "VLC",
    ])

    vlc_root = next(
        (
            path for path in candidates
            if (path / "libvlc.dll").is_file()
            and (path / "libvlccore.dll").is_file()
            and (path / "plugins").is_dir()
        ),
        None,
    )

    if vlc_root is None:
        raise FileNotFoundError(
            "未找到 VLC 运行库。请先安装与 Python 位数一致的 VLC，"
            "或设置环境变量 VLC_DIR 指向 VLC 安装目录。"
        )

    binaries = []
    datas = []

    # 收集 VLC 根目录 DLL
    for file in vlc_root.glob("*.dll"):
        binaries.append((str(file), "vlc"))

    # 收集 VLC 插件及其资源文件
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


# 收集 PySide6 和第三方依赖
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
