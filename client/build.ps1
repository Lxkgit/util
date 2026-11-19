# Windows client dependency check and packaging script
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Client dependency check and packaging" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check the Python interpreter
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCommand) {
    throw "Python was not found. Install Python 3.11 x64 and add it to PATH."
}

$PythonVersion = (& python --version 2>&1 | Out-String).Trim()
if ($PythonVersion -notmatch "^Python 3\.11\.") {
    throw "Expected Python 3.11 x64, found: $PythonVersion"
}

$PythonBitsOutput = & python -c 'import struct; print(struct.calcsize(chr(80)) * 8)' 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Failed to detect Python architecture: $PythonBitsOutput"
}
$PythonBits = ($PythonBitsOutput | Out-String).Trim()
if ($PythonBits -ne "64") {
    throw "Expected 64-bit Python, found $PythonBits-bit Python."
}

# Create a project virtual environment if it does not exist
$VenvDir = Join-Path $PSScriptRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..."
    & python -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the virtual environment."
    }
}

# Install or repair all declared Python dependencies
Write-Host "Installing/checking Python dependencies..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "Failed to upgrade pip."
}

& $VenvPython -m pip install -r (Join-Path $PSScriptRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) {
    throw "Failed to install Python dependencies."
}

# Download the official portable VLC package without installing VLC
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
    Write-Host "Downloading official VLC $VlcVersion portable package..."
    Invoke-WebRequest -Uri $VlcDownloadUrl -OutFile $VlcArchive -UseBasicParsing
}

if (-not (Test-Path $VlcChecksumFile)) {
    Write-Host "Downloading VLC SHA256 checksum..."
    Invoke-WebRequest -Uri $VlcChecksumUrl -OutFile $VlcChecksumFile -UseBasicParsing
}

$ExpectedHash = ([regex]::Match((Get-Content -Raw $VlcChecksumFile), "^[0-9a-fA-F]{64}")).Value.ToLowerInvariant()
if (-not $ExpectedHash) {
    throw "Could not read the official VLC SHA256 checksum."
}

$ActualHash = (Get-FileHash -Path $VlcArchive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ActualHash -ne $ExpectedHash) {
    Remove-Item -Force $VlcArchive, $VlcChecksumFile -ErrorAction SilentlyContinue
    throw "VLC archive SHA256 verification failed. The invalid download was removed; run the script again."
}

$VlcDll = $null
if (Test-Path $VlcExtractDir) {
    $VlcDll = Get-ChildItem -Path $VlcExtractDir -Filter "libvlc.dll" -File -Recurse | Select-Object -First 1
}

if (-not $VlcDll) {
    Write-Host "Extracting VLC runtime..."
    Remove-Item -Recurse -Force $VlcExtractDir -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $VlcExtractDir | Out-Null
    Expand-Archive -Path $VlcArchive -DestinationPath $VlcExtractDir -Force
    $VlcDll = Get-ChildItem -Path $VlcExtractDir -Filter "libvlc.dll" -File -Recurse | Select-Object -First 1
}

if (-not $VlcDll) {
    throw "The downloaded VLC package does not contain libvlc.dll."
}

$VlcDir = $VlcDll.Directory.FullName
if (-not (Test-Path (Join-Path $VlcDir "libvlccore.dll")) -or
    -not (Test-Path (Join-Path $VlcDir "plugins"))) {
    throw "The extracted VLC runtime is incomplete: $VlcDir"
}

$env:VLC_DIR = $VlcDir
$env:VLC_PLUGIN_PATH = Join-Path $VlcDir "plugins"
$env:PATH = "$VlcDir;$env:PATH"
Write-Host "VLC runtime ready: $VlcDir" -ForegroundColor Green

# Verify imports before building
Write-Host "Verifying Python modules..."
& $VenvPython -c 'import PySide6, cv2, vlc, requests, aiortc, av, mss, PIL; print("All required modules imported successfully.")'
if ($LASTEXITCODE -ne 0) {
    throw "Python module verification failed."
}

# Remove old output and build with the project spec
Write-Host "Removing previous build output..."
Remove-Item -Recurse -Force (Join-Path $PSScriptRoot "build"), (Join-Path $PSScriptRoot "dist") -ErrorAction SilentlyContinue

Write-Host "Building application..."
& $VenvPython -m PyInstaller --noconfirm --clean main.spec
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$ExePath = Join-Path $PSScriptRoot "dist\main\main.exe"
if (-not (Test-Path $ExePath)) {
    throw "Build finished but executable was not found: $ExePath"
}

Write-Host "========================================" -ForegroundColor Green
Write-Host "Build completed: $ExePath" -ForegroundColor Green
Write-Host "Copy the entire dist\main folder to the target computer." -ForegroundColor Yellow
Write-Host "Do not copy main.exe alone." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green
