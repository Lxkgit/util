# Windows 客户端依赖检查与自动打包脚本
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "客户端依赖检查与自动打包" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查 Python 环境
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCommand) {
    throw "未找到 Python。请安装 Python 3.11 64 位版本，并将其添加到 PATH。"
}

$PythonVersion = (& python --version 2>&1 | Out-String).Trim()
if ($PythonVersion -notmatch "^Python 3\.11\.") {
    throw "要求使用 Python 3.11 64 位版本，当前检测结果：$PythonVersion"
}

$PythonBitsOutput = & python -c 'import struct; print(struct.calcsize(chr(80)) * 8)' 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "检测 Python 位数失败：$PythonBitsOutput"
}
$PythonBits = ($PythonBitsOutput | Out-String).Trim()
if ($PythonBits -ne "64") {
    throw "要求使用 64 位 Python，当前检测到 $PythonBits 位。"
}

# 如果项目虚拟环境不存在，则自动创建
$VenvDir = Join-Path $PSScriptRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "正在创建项目虚拟环境..."
    & python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        throw "创建 Python 虚拟环境失败。"
    }
}

# 安装或补齐项目依赖
Write-Host "正在检查并安装 Python 依赖..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "升级 pip 失败。"
}

& $VenvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "安装 Python 项目依赖失败。"
}

# 下载 VLC 官方便携版运行库，不需要在电脑上安装 VLC
$VlcVersion = "3.0.24"
$VlcFileName = "vlc-$VlcVersion-win64.zip"
$VlcBaseUrl = "https://download.videolan.org/pub/videolan/vlc/last/win64"
$VlcCacheDir = Join-Path $PSScriptRoot ".build-cache\vlc-$VlcVersion"
$VlcArchive = Join-Path $VlcCacheDir $VlcFileName
$VlcChecksumFile = Join-Path $VlcCacheDir "$VlcFileName.sha256"
$VlcExtractDir = Join-Path $VlcCacheDir "extracted"

New-Item -ItemType Directory -Force -Path $VlcCacheDir | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$VlcDownloadUrl = "$VlcBaseUrl/$VlcFileName"
$VlcChecksumUrl = "$VlcDownloadUrl.sha256"

if (-not (Test-Path $VlcArchive)) {
    Write-Host "正在从 VideoLAN 官方站点下载 VLC $VlcVersion 便携版..."
    Invoke-WebRequest -Uri $VlcDownloadUrl -OutFile $VlcArchive -UseBasicParsing
}

if (-not (Test-Path $VlcChecksumFile)) {
    Write-Host "正在下载 VLC SHA256 校验文件..."
    Invoke-WebRequest -Uri $VlcChecksumUrl -OutFile $VlcChecksumFile -UseBasicParsing
}

$ExpectedHash = ([regex]::Match((Get-Content -Raw $VlcChecksumFile), "^[0-9a-fA-F]{64}")).Value.ToLowerInvariant()
if (-not $ExpectedHash) {
    throw "无法读取 VLC 官方 SHA256 校验值。"
}

$ActualHash = (Get-FileHash -Path $VlcArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualHash -ne $ExpectedHash) {
    Remove-Item -Force $VlcArchive, $VlcChecksumFile -ErrorAction SilentlyContinue
    throw "VLC 压缩包 SHA256 校验失败，已删除损坏文件，请重新运行脚本。"
}

$VlcDll = $null
if (Test-Path $VlcExtractDir) {
    $VlcDll = Get-ChildItem -Path $VlcExtractDir -Filter "libvlc.dll" -File -Recurse | Select-Object -First 1
}

if (-not $VlcDll) {
    Write-Host "正在解压 VLC 运行库..."
    Remove-Item -Recurse -Force $VlcExtractDir -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $VlcExtractDir | Out-Null
    Expand-Archive -Path $VlcArchive -DestinationPath $VlcExtractDir -Force
    $VlcDll = Get-ChildItem -Path $VlcExtractDir -Filter "libvlc.dll" -File -Recurse | Select-Object -First 1
}

if (-not $VlcDll) {
    throw "下载的 VLC 压缩包中没有找到 libvlc.dll。"
}

$VlcDir = $VlcDll.Directory.FullName
if (-not (Test-Path (Join-Path $VlcDir "libvlccore.dll")) -or
    -not (Test-Path (Join-Path $VlcDir "plugins"))) {
    throw "VLC 运行库文件不完整：$VlcDir"
}

$env:VLC_DIR = $VlcDir
$env:VLC_PLUGIN_PATH = Join-Path $VlcDir "plugins"
$env:PATH = "$VlcDir;$env:PATH"
Write-Host "VLC 运行库准备完成：$VlcDir" -ForegroundColor Green

# 打包前检查 Python 模块是否可以正常导入
Write-Host "正在检查 Python 模块..."
& $VenvPython -c "import PySide6, cv2, vlc, requests, aiortc, av, mss, PIL"
if ($LASTEXITCODE -ne 0) {
    throw "Python 模块检查失败，请检查上方错误信息。"
}
Write-Host "所有必需模块均已成功导入。" -ForegroundColor Green

# 清理旧的打包结果并执行 PyInstaller
Write-Host "正在清理上一次的构建文件..."
Remove-Item -Recurse -Force (Join-Path $PSScriptRoot "build"), (Join-Path $PSScriptRoot "dist") -ErrorAction SilentlyContinue

Write-Host "正在执行程序打包，请稍候..."
& $VenvPython -m PyInstaller --noconfirm --clean main.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller 打包失败，请检查上方错误信息。"
}

$ExePath = Join-Path $PSScriptRoot "dist\main\main.exe"
if (-not (Test-Path $ExePath)) {
    throw "打包命令已结束，但没有找到程序文件：$ExePath"
}

Write-Host "========================================" -ForegroundColor Green
Write-Host "打包完成：$ExePath" -ForegroundColor Green
Write-Host "请将整个 dist\main 文件夹复制到目标电脑。" -ForegroundColor Yellow
Write-Host "不能只复制 main.exe。" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
