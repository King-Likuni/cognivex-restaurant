#Requires -Version 5.1
[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $Root ".dev\processes.json"

function Test-Http([string]$Name, [string]$Url) {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri $Url
        Write-Host "$Name OK ($($response.StatusCode)): $Url"
    } catch {
        Write-Warning "$Name not responding: $Url"
    }
}

Write-Host "Project: $Root"
Write-Host ""

if (Test-Path $PidFile) {
    Write-Host "Tracked processes:"
    $state = Get-Content $PidFile -Raw | ConvertFrom-Json
    foreach ($process in $state.processes) {
        $running = Get-Process -Id ([int]$process.pid) -ErrorAction SilentlyContinue
        $status = if ($running) { "running" } else { "stopped" }
        Write-Host "- $($process.name) pid=$($process.pid) $status"
    }
} else {
    Write-Warning "No tracked process file found."
}

Write-Host ""
Write-Host "Port listeners:"
Get-NetTCPConnection -LocalPort $BackendPort, $FrontendPort -State Listen -ErrorAction SilentlyContinue |
    Select-Object LocalAddress, LocalPort, OwningProcess |
    Format-Table -AutoSize

Write-Host ""
Test-Http "Backend health" "http://127.0.0.1:$BackendPort/health"
Test-Http "Backend readiness" "http://127.0.0.1:$BackendPort/ready"
Test-Http "Frontend" "http://127.0.0.1:$FrontendPort/"

if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Host ""
    Write-Host "Docker compose:"
    Push-Location $Root
    try {
        docker compose ps
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Docker status is unavailable. Docker Desktop may be closed or access may be blocked."
        }
    } finally {
        Pop-Location
    }
}
