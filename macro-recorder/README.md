# Macro Recorder

一个基于 Python + PySide6 + pynput 的 Windows 键盘鼠标宏录制 Demo。

## 功能

- 录制键盘按下/释放
- 录制鼠标移动、点击、滚轮
- 保留操作之间的时间间隔
- 保存/加载 JSON 宏文件
- 播放一次、指定次数或无限循环
- 全局快捷键：F8 开始/停止录制，F9 播放/暂停，F10 紧急停止
- 播放过程中显示当前进度

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

## 注意

录制功能会捕获当前用户主动录制期间的键盘和鼠标事件。不要在录制期间输入密码、私密信息或其他不希望保存的数据。
