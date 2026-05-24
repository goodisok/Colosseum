#Requires -Version 5.1
<#
.SYNOPSIS
  Build, launch Colosseum BlocksV2 in Multirotor mode, and run automated quadrotor tests.

.EXAMPLE
  .\scripts\run_quadrotor_test.ps1

.EXAMPLE
  .\scripts\run_quadrotor_test.ps1 -SkipBuild -SkipLaunch
  # UE already running with Multirotor settings
#>
param(
    [switch]$SkipBuild,
    [switch]$SkipLaunch,
    [switch]$Headless,
    [string]$UeEditorPath = "",
    [string]$ProjectPath = "",
    [string]$SettingsPath = "",
    [int]$ConnectTimeoutSec = 300,
    [int]$TestTimeoutSec = 180
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
if (-not $ProjectPath) {
    $ProjectPath = Join-Path $RepoRoot "Unreal\Environments\BlocksV2\BlocksV2.uproject"
}
if (-not $SettingsPath) {
    $SettingsPath = Join-Path $RepoRoot "scripts\settings\multirotor_simpleflight.json"
}
$TestScript = Join-Path $RepoRoot "PythonClient\multirotor\auto_verify_quadrotor.py"
$BuildScript = Join-Path $RepoRoot "build.cmd"
$LogDir = Join-Path $RepoRoot "scripts\logs"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$UeLog = Join-Path $LogDir ("ue_$Timestamp.log")

function Resolve-UeEditorPath {
    if ($UeEditorPath -and (Test-Path $UeEditorPath)) {
        return $UeEditorPath
    }
    if ($env:UE_EDITOR) {
        return $env:UE_EDITOR
    }
    $candidates = @(
        "D:\Program Files\EpicGames\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe",
        "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe",
        "C:\Program Files\EpicGames\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe",
        "C:\Program Files\Epic Games\UE_5.6\Engine\Binaries\Win64\UnrealEditor.exe"
    )
    foreach ($path in $candidates) {
        if (Test-Path $path) { return $path }
    }
    throw "UnrealEditor.exe not found. Pass -UeEditorPath or set `$env:UE_EDITOR."
}

function Stop-UeProcess {
    param([System.Diagnostics.Process]$Process)
    if ($null -eq $Process) { return }
    if ($Process.HasExited) { return }
    Write-Host "[run_quadrotor_test] Stopping UE (pid $($Process.Id))..."
    Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
}

function Wait-ForRpc {
    param([int]$TimeoutSec)
    $pyDir = Join-Path $RepoRoot "PythonClient\multirotor"
    $pyCheck = @"
import sys, os, time
sys.path.insert(0, r"$pyDir")
import setup_path
import airsim
deadline = time.time() + $TimeoutSec
while time.time() < deadline:
    try:
        c = airsim.MultirotorClient(timeout_value=3)
        c.ping()
        sys.exit(0)
    except Exception:
        time.sleep(2)
sys.exit(1)
"@
    $pyFile = Join-Path $env:TEMP "colosseum_rpc_check.py"
    Set-Content -Path $pyFile -Value $pyCheck -Encoding UTF8
    Push-Location $pyDir
    & python $pyFile
    $ready = ($LASTEXITCODE -eq 0)
    Pop-Location
    Remove-Item $pyFile -ErrorAction SilentlyContinue
    if ($ready) {
        Write-Host "[run_quadrotor_test] RPC server responded to ping"
    }
    return $ready
}

if (-not (Test-Path $ProjectPath)) {
    throw "Project not found: $ProjectPath"
}
if (-not (Test-Path $SettingsPath)) {
    throw "Settings not found: $SettingsPath"
}
if (-not (Test-Path $TestScript)) {
    throw "Test script not found: $TestScript"
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$ueProcess = $null
$exitCode = 1

try {
    if (-not $SkipBuild) {
        Write-Host "[run_quadrotor_test] Building Colosseum plugin..."
        Push-Location $RepoRoot
        & cmd /c "$BuildScript"
        if ($LASTEXITCODE -ne 0) { throw "build.cmd failed with exit code $LASTEXITCODE" }
        Pop-Location
    }

    if (-not $SkipLaunch) {
        $editor = Resolve-UeEditorPath
        $launchArgs = "`"$ProjectPath`" -game -log -settings=`"$SettingsPath`""
        if ($Headless) {
            $launchArgs += " -RenderOffScreen"
        }

        Write-Host "[run_quadrotor_test] Launching UE: $editor"
        Write-Host "[run_quadrotor_test] UE log: $UeLog"
        $ueProcess = Start-Process -FilePath $editor -ArgumentList $launchArgs -PassThru `
            -RedirectStandardOutput $UeLog -RedirectStandardError "${UeLog}.err"

        if (-not (Wait-ForRpc -TimeoutSec $ConnectTimeoutSec)) {
            throw "Colosseum RPC not ready within ${ConnectTimeoutSec}s. See $UeLog and Saved/logs/BlocksV2.log"
        }
        Write-Host "[run_quadrotor_test] Waiting 10s for simulation warmup..."
        Start-Sleep -Seconds 10
    }

    Write-Host "[run_quadrotor_test] Running Python verification..."
    Push-Location (Join-Path $RepoRoot "PythonClient\multirotor")
    $pyArgs = @(
        "auto_verify_quadrotor.py",
        "--connect-timeout", $ConnectTimeoutSec
    )
    $pyJob = Start-Process -FilePath "python" -ArgumentList $pyArgs -NoNewWindow -PassThru -Wait
    $exitCode = $pyJob.ExitCode
    Pop-Location

    if ($exitCode -eq 0) {
        Write-Host "[run_quadrotor_test] PASS"
    } else {
        Write-Host "[run_quadrotor_test] FAIL (exit code $exitCode)"
    }
}
finally {
    Stop-UeProcess -Process $ueProcess
}

exit $exitCode
