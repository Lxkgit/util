# Macro Recorder

一个基于 Python + PySide6 + pynput 的 Windows 键盘鼠标宏录制 Demo。

## 功能

- 录制键盘按下/释放
- 录制鼠标移动、点击、滚轮
- 保留操作之间的时间间隔
- 鼠标移动事件自动限流，减少录制时的界面卡顿
- 保存/加载 JSON 宏文件
- 播放一次、指定次数或无限循环
- 全局快捷键：录制快捷键可在设置中修改，默认 F8
- F9 播放/暂停
- F10 紧急停止
- 快捷键设置自动保存，下次启动继续使用
- 录制快捷键不会被写入宏操作

## 环境

建议 Python 3.10+。

```bash
cd macro-recorder
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Linux/macOS 也可以尝试运行，但 Demo 主要面向 Windows。

## 快捷键设置

点击窗口右上角的「设置」，可以修改「录制快捷键」。

当前版本为了避免录制控制与宏操作互相干扰，录制快捷键只支持单键，例如 F6、F7、F8、F11、Pause 等；F9 和 F10 保留给播放/暂停及紧急停止。

设置会使用 Qt 的应用配置自动保存，不需要手动维护配置文件。

## 注意

录制功能会捕获当前用户主动录制期间的键盘和鼠标事件。不要在录制期间输入密码、私密信息或其他不希望保存的数据。
