# 在导入 python-vlc 前配置随程序打包的 VLC 运行库

import os
import sys
from pathlib import Path


if getattr(sys, "frozen", False):
    bundle_dir = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    vlc_dir = bundle_dir / "vlc"

    if vlc_dir.is_dir():
        # 让 Windows 能找到 VLC 核心 DLL 及其依赖
        os.environ["PATH"] = str(vlc_dir) + os.pathsep + os.environ.get("PATH", "")

        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(str(vlc_dir))

        # 指定 VLC 插件目录，确保解码器和输出模块可以加载
        plugin_dir = vlc_dir / "plugins"
        if plugin_dir.is_dir():
            os.environ["VLC_PLUGIN_PATH"] = str(plugin_dir)
