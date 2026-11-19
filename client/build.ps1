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

# Locate the 64-bit VLC installation
$VlcCandidates = @()
if ($env:VLC_DIR) {
    $VlcCandidates += $env:VLC_DIR
}
if ($env:ProgramFiles) {
    $VlcCandidates += (Join-Path $env:ProgramFiles "VideoLAN\VLC")
}
$ProgramFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
if ($ProgramFilesX86) {
    $VlcCandidates += (Join-Path $ProgramFilesX86 "VideoLAN\VLC")
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

# Offer to install VLC with winget if it is missing
if (-not $VlcDir) {
    $Winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($Winget) {
        $Answer = Read-Host "VLC was not found. Install 64-bit VLC using winget? (Y/N)"
        if ($Answer -match "^(Y|YES)$") {
            & winget install --id VideoLAN.VLC --exact --silent --accept-package-agreements --accept-source-agreements
            if ($LASTEXITCODE -ne 0) {
                throw "VLC installation failed. Install 64-bit VLC manually and run this script again."
            }

            $VlcCandidates = @()
            if ($env:ProgramFiles) {
                $VlcCandidates += (Join-Path $env:ProgramFiles "VideoLAN\VLC")
            }
            if ($ProgramFilesX86) {
                $VlcCandidates += (Join-Path $ProgramFilesX86 "VideoLAN\VLC")
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
    throw "VLC runtime was not found. Install 64-bit VLC or set VLC_DIR to its installation folder."
}

$env:VLC_DIR = $VlcDir
Write-Host "VLC runtime: $VlcDir" -ForegroundColor Green

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
