#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$KeepDocker
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RuntimeRoot = Join-Path $Root ".dev"
$PidFile = Join-Path $RuntimeRoot "processes.json"

function Stop-TrackedProcess([object]$TrackedProcess) {
    $processId = [int]$TrackedProcess.pid
    $running = Get-Process -Id $processId -ErrorAction SilentlyContinue
    if (-not $running) {
        Write-Host "$($TrackedProcess.name) is not running ($processId)."
        return
    }

    Write-Host "Stopping $($TrackedProcess.name) ($processId)..."
    taskkill /PID $processId /T /F | Out-Null
}

if (Test-Path $PidFile) {
    $state = Get-Content $PidFile -Raw | ConvertFrom-Json
    foreach ($process in $state.processes) {
        Stop-TrackedProcess $process
    }
    Remove-Item -LiteralPath $PidFile -Force
} else {
    Write-Warning "No tracked dev process file found at $PidFile."
}

if (-not $KeepDocker -and (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Stopping Docker services..."
    Push-Location $Root
    try {
        docker compose stop
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Docker compose stop did not complete. Check Docker Desktop if database/cache containers are still running."
        }
    } finally {
        Pop-Location
    }
}

Write-Host "Dev services stopped."
