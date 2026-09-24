@echo off
setlocal

dotnet --info
if errorlevel 1 (
    echo.
    echo 未检测到 .NET 8 SDK。
    echo 请安装 .NET 8 SDK 后再次运行。
    pause
    exit /b 1
)

dotnet build -c Release
if errorlevel 1 (
    echo.
    echo 编译失败。
    pause
    exit /b 1
)

echo.
echo 编译完成：
echo bin\Release\net8.0-windows\DyingLightAimTool.exe
pause
