# 键盘鼠标宏录制器

基于 Python + PySide6 + pynput 的桌面宏录制 Demo。

## 功能

- **全部录制**：同时记录键盘和鼠标。
- **仅键盘**：只记录键盘按下、释放。
- **仅鼠标**：只记录鼠标移动、点击、滚轮。
- 保留操作之间的时间间隔。
- 鼠标移动自动采样，减少事件数量和界面压力。
- 保存 / 加载 JSON 宏文件。
- 播放一次、指定次数或无限循环。
- F9 播放 / 暂停，F10 紧急停止。
- F8 默认控制录制，也可以在设置中修改，并支持开始/结束独立快捷键。

## 项目结构

```text
macro-recorder/
├─ app/                 # 应用启动
├─ core/                # 核心数据模型、宏播放
├─ recording/           # 键盘/鼠标录制
├─ services/            # 全局快捷键等应用服务
├─ ui/                  # PySide6 界面
├─ main.py              # 启动入口
└─ requirements.txt
```

## 运行

```bash
cd macro-recorder
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## 使用

启动后先在主页面选择「全部录制」「仅键盘」或「仅鼠标」，再点击开始录制。选择录制类型不会改变已有宏，录制过程中不能切换类型。

> 录制会捕获当前用户主动录制期间的键盘和鼠标事件，请勿在录制期间输入密码、私密信息或其他不希望保存的数据。
