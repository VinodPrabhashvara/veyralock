$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$venvDir = Join-Path $projectRoot ".venv"
$venvPython = Join-Path $venvDir "Scripts\python.exe"
$venvActivate = Join-Path $venvDir "Scripts\Activate.ps1"

if (-not $env:PYTHONHASHSEED) {
    $env:PYTHONHASHSEED = "0"
}
if (-not $env:SOURCE_DATE_EPOCH) {
    $env:SOURCE_DATE_EPOCH = "1704067200"
}

$buildRoot = Join-Path $projectRoot ".pyinstaller"
$buildDir = Join-Path $buildRoot "build"
$specDir = Join-Path $buildRoot "spec"
$distDir = Join-Path $projectRoot "dist"
$iconPath = Join-Path $projectRoot "assets\veyralock.ico"

if (-not (Test-Path $venvPython)) {
    $bootstrapPython = if ($env:PYTHON) { $env:PYTHON } else { "python" }
    Write-Host "Creating virtual environment in .venv ..."
    & $bootstrapPython -m venv $venvDir
}

. $venvActivate
$python = $venvPython

Write-Host "Upgrading pip and installing build dependencies..."
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
& $python -m pip install -e .
& $python -m pip install pyinstaller pillow

Write-Host "Running test suite..."
& $python -m pytest

Write-Host "Running compile checks..."
& $python -m py_compile veyralock_entry.py veyralock\gui.py veyralock\cli.py veyralock\crypto.py

Write-Host "Preparing clean PyInstaller build directories..."
if (Test-Path $buildRoot) { Remove-Item -Recurse -Force $buildRoot }
if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }
if (Test-Path (Join-Path $projectRoot "build")) { Remove-Item -Recurse -Force (Join-Path $projectRoot "build") }

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
New-Item -ItemType Directory -Force -Path $specDir | Out-Null
New-Item -ItemType Directory -Force -Path $distDir | Out-Null

$pyInstallerHelp = & $python -m PyInstaller --help 2>&1 | Out-String
$supportsHideConsole = $pyInstallerHelp -match "--hide-console"

$basePyInstallerArgs = @(
    "--onefile"
    "--clean"
    "--name", "VeyraLock"
)

if (Test-Path $iconPath) {
    $basePyInstallerArgs += @("--icon", $iconPath)
    $basePyInstallerArgs += @("--add-data", "$iconPath;assets")
}
else {
    Write-Warning "Icon file not found at assets\veyralock.ico. Building without bundled icon."
}

$entryScript = "veyralock_entry.py"
$buildSucceeded = $false
$finalPyInstallerArgs = @()

if ($supportsHideConsole) {
    $preferredArgs = @(
        "--console"
        "--hide-console", "hide-early"
    ) + $basePyInstallerArgs + $entryScript

    Write-Host "Building combined GUI + CLI executable with hidden console support..."
    try {
        & $python -m PyInstaller `
            --noconfirm `
            --distpath $distDir `
            --workpath $buildDir `
            --specpath $specDir `
            @preferredArgs

        if ($LASTEXITCODE -eq 0) {
            $buildSucceeded = $true
            $finalPyInstallerArgs = $preferredArgs
        }
    }
    catch {
        Write-Warning "PyInstaller build with --hide-console failed. Falling back to a windowed build."
    }
}

if (-not $buildSucceeded) {
    if (-not $supportsHideConsole) {
        Write-Warning "Installed PyInstaller does not support --hide-console. Falling back to a windowed build so double-click GUI launch does not show a console."
    }

    if (Test-Path $buildRoot) { Remove-Item -Recurse -Force $buildRoot }
    if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }
    if (Test-Path (Join-Path $projectRoot "build")) { Remove-Item -Recurse -Force (Join-Path $projectRoot "build") }

    New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
    New-Item -ItemType Directory -Force -Path $specDir | Out-Null
    New-Item -ItemType Directory -Force -Path $distDir | Out-Null

    $fallbackArgs = @("--windowed") + $basePyInstallerArgs + $entryScript
    Write-Host "Building combined GUI-first executable without a console window..."
    & $python -m PyInstaller `
        --noconfirm `
        --distpath $distDir `
        --workpath $buildDir `
        --specpath $specDir `
        @fallbackArgs

    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed."
    }

    $buildSucceeded = $true
    $finalPyInstallerArgs = $fallbackArgs
}

Write-Host "Build complete. Combined executable is in dist/VeyraLock.exe"
Write-Host "Final PyInstaller arguments: $($finalPyInstallerArgs -join ' ')"
