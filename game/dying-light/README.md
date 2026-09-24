# Dying Light

《消逝的光芒》Steam 单机独立工具。

## 当前阶段

`v0.1` 为进程诊断版本：

- 自动查找 `DyingLightGame.exe`
- 获取 PID 和游戏路径
- 枚举关键模块
- 测试 `OpenProcess`
- 测试 `ReadProcessMemory`
- 读取主模块头部用于确认外部读取链路

当前版本**不会修改游戏内存**。

## 开发环境

- Windows 10/11
- .NET 8 SDK
- x64

## 运行

```text
build.bat
```

编译后运行：

```text
bin/Release/net8.0-windows/DyingLightAimTool.exe
```

## 下一阶段

根据实际 Steam 版本运行结果继续定位游戏模块和目标数据，再逐步实现独立工具的瞄准辅助功能。
