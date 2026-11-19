# Windows 客户端自动安装依赖并打包
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "客户端依赖检查与打包" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查 Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "未找到 Python。请先安装 Python 3.11 x64，并将其加入 PATH。"
}

$PythonVersion = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$PythonBits = & python -c "import struct; print(struct.calcsize('P') * 8)"

if ($PythonVersion -ne "3.11") {
    throw "当前 Python 版本为 $PythonVersion，建议使用 Python 3.11。"
}

if ($PythonBits -ne "64") {
    throw "当前 Python 为 $PythonBits 位。请安装 Python 3.11 x64，VLC 也必须使用 64 位版本。"
}

# 创建独立虚拟环境，避免 Conda Base 与项目环境混用
$VenvDir = Join-Path $PSScriptRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "创建项目虚拟环境..."
    & python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        throw "创建虚拟环境失败。"
    }
}

# 自动安装或补齐 requirements.txt 中缺少的依赖
Write-Host "检查并安装 Python 依赖..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "升级 pip 失败。"
}

& $VenvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Python 依赖安装失败。"
}

# 检查 VLC 运行库
$VlcCandidates = @()

if ($env:VLC_DIR) {
    $VlcCandidates += $env:VLC_DIR
}

if ($env:ProgramFiles) {
    $VlcCandidates += (Join-Path $env:ProgramFiles "VideoLAN\VLC")
}

if ($env:ProgramFilesx86) {
    $VlcCandidates += (Join-Path $env:ProgramFilesx86 "VideoLAN\VLC")
}

$VlcDir = $null
foreach ($Candidate in $VlcCandidates) {
    if ((Test-Path (Join-Path $Candidate "libvlc.dll")) -and
        (Test-Path (Join-Path $Candidate "libvlccore.dll")) -and
        (Test-Path (Join-Path $Candidate "plugins"))) {
        $VlcDir = (Resolve-Path $Candidate).Path
        break
    }
}

if (-not $VlcDir) {
    $Winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($Winget) {
        $Answer = Read-Host "未检测到 VLC。是否通过 winget 安装 64 位 VLC？(Y/N)"
        if ($Answer -match "^(Y|YES)$") {
            & winget install --id VideoLAN.VLC --exact --silent --accept-package-agreements --accept-source-agreements
            if ($LASTEXITCODE -ne 0) {
                throw "VLC 安装失败。请手动安装 64 位 VLC 后重新执行脚本。"
            }

            $VlcCandidates = @()
            if ($env:ProgramFiles) {
                $VlcCandidates += (Join-Path $env:ProgramFiles "VideoLAN\VLC")
            }
            if ($env:ProgramFilesx86) {
                $VlcCandidates += (Join-Path $env:ProgramFilesx86 "VideoLAN\VLC")
            }

            foreach ($Candidate in $VlcCandidates) {
                if ((Test-Path (Join-Path $Candidate "libvlc.dll")) -and
                    (Test-Path (Join-Path $Candidate "libvlccore.dll")) -and
                    (Test-Path (Join-Path $Candidate "plugins"))) {
                    $VlcDir = (Resolve-Path $Candidate).Path
                    break
                }
            }
        }
    }
}

if (-not $VlcDir) {
    throw "未找到 VLC 运行库。请安装 64 位 VLC，或设置 VLC_DIR 环境变量指向 VLC 安装目录。"
}

$env:VLC_DIR = $VlcDir
Write-Host "VLC 运行库：$VlcDir" -ForegroundColor Green

# 检查关键模块能否导入
Write-Host "验证 Python 模块..."
& $VenvPython -c "import PySide6, cv2, vlc, requests, aiortc, av, mss, PIL; print('依赖检查通过')"
if ($LASTEXITCODE -ne 0) {
    throw "模块导入检查失败，请检查上方错误信息。"
}

# 清理旧构建并执行打包
Write-Host "清理旧构建文件..."
Remove-Item -Recurse -Force (Join-Path $PSScriptRoot "build"), (Join-Path $PSScriptRoot "dist") -ErrorAction SilentlyContinue

Write-Host "开始打包..."
& $VenvPython -m PyInstaller --noconfirm --clean main.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 打包失败。"
}

$ExePath = Join-Path $PSScriptRoot "dist\main\main.exe"
if (-not (Test-Path $ExePath)) {
    throw "打包命令已结束，但未找到输出文件：$ExePath"
}

Write-Host "========================================" -ForegroundColor Green
Write-Host "打包完成：$ExePath" -ForegroundColor Green
Write-Host "将整个 dist\main 文件夹复制到目标电脑，不要只复制 main.exe。" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
