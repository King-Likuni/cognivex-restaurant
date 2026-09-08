#Requires -Version 5.1
[CmdletBinding()]
param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [switch]$SkipDocker,
    [switch]$SkipMigrations,
    [switch]$SkipSeed,
    [switch]$ServicesOnly,
    [string]$LocalEnvFile = $env:LOCAL_ENV_FILE
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $Root "backend"
$FrontendRoot = Join-Path $Root "frontend"
$RuntimeRoot = Join-Path $Root ".dev"
$LogRoot = Join-Path $RuntimeRoot "logs"
$PidFile = Join-Path $RuntimeRoot "processes.json"
$EnvSnapshot = @{}

function Write-Step([string]$Message) {
    Write-Host "== $Message =="
}

function Test-Command([string]$CommandName) {
    return [bool](Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Test-PortListening([int]$Port) {
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return [bool]$connection
}

function Set-ScopedEnv([string]$Name, [string]$Value) {
    if (-not $EnvSnapshot.ContainsKey($Name)) {
        $existing = Get-Item -Path "Env:$Name" -ErrorAction SilentlyContinue
        $EnvSnapshot[$Name] = if ($existing) { $existing.Value } else { $null }
    }
    Set-Item -Path "Env:$Name" -Value $Value
}

function Restore-ScopedEnv {
    foreach ($name in $EnvSnapshot.Keys) {
        if ($null -eq $EnvSnapshot[$name]) {
            Remove-Item -Path "Env:$name" -ErrorAction SilentlyContinue
        } else {
            Set-Item -Path "Env:$name" -Value $EnvSnapshot[$name]
        }
    }
}

function Import-DotEnv([string]$Path) {
    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $parts = $line -split "=", 2
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-ScopedEnv $name $value
    }
}

function Wait-HttpOk([string]$Url, [int]$TimeoutSeconds = 30) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 -Uri $Url
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds 800
        }
    } while ((Get-Date) -lt $deadline)
    return $false
}

function Start-LoggedProcess(
    [string]$Name,
    [string]$WorkingDirectory,
    [string]$Command,
    [string]$StdoutPath,
    [string]$StderrPath
) {
    $escapedDirectory = $WorkingDirectory.Replace("'", "''")
    $process = Start-Process `
        -FilePath "powershell.exe" `
        -ArgumentList @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-Command",
            "Set-Location -LiteralPath '$escapedDirectory'; $Command"
        ) `
        -RedirectStandardOutput $StdoutPath `
        -RedirectStandardError $StderrPath `
        -WindowStyle Hidden `
        -PassThru

    [pscustomobject]@{
        name = $Name
        pid = $process.Id
        started_at = (Get-Date).ToString("o")
        cwd = $WorkingDirectory
        stdout = $StdoutPath
        stderr = $StderrPath
    }
}

try {
    $DefaultEnvFile = Join-Path $Root ".env.example"
    if (-not $LocalEnvFile) {
        $LocalEnvFile = Join-Path $Root ".env"
    } elseif (-not [System.IO.Path]::IsPathRooted($LocalEnvFile)) {
        $LocalEnvFile = Join-Path $Root $LocalEnvFile
    }
    Import-DotEnv $DefaultEnvFile
    Import-DotEnv $LocalEnvFile

    New-Item -ItemType Directory -Force -Path $RuntimeRoot, $LogRoot | Out-Null

    if (Test-Path $PidFile) {
        Write-Warning "A previous dev process file exists at $PidFile. Run .\scripts\dev_status.ps1 or .\scripts\dev_stop.ps1 before starting again."
    }

    if (-not $SkipDocker) {
        if (Test-Command "docker") {
            Write-Step "Starting Docker services"
            Push-Location $Root
            try {
                docker compose up -d
                if ($LASTEXITCODE -ne 0) {
                    Write-Warning "Docker compose did not start cleanly. Continue only if Postgres and Redis are already running."
                }
            } finally {
                Pop-Location
            }
        } else {
            Write-Warning "Docker CLI was not found. Skipping database/cache startup."
        }
    }

    $Python = Join-Path $BackendRoot "venv\Scripts\python.exe"
    if (-not (Test-Path $Python)) {
        throw "Backend virtual environment was not found at $Python. Create it and install backend dependencies first."
    }

    if (-not $SkipMigrations) {
        Write-Step "Running database migrations"
        Push-Location $BackendRoot
        try {
            & $Python -m alembic upgrade head
            if ($LASTEXITCODE -ne 0) {
                throw "Database migration failed."
            }
        } finally {
            Pop-Location
        }
    }

    if (-not $SkipSeed) {
        Write-Step "Seeding local data"
        Push-Location $BackendRoot
        try {
            & $Python -m app.initial_data
            if ($LASTEXITCODE -ne 0) {
                throw "Local data seed failed."
            }
        } finally {
            Pop-Location
        }
    }

    if (-not (Test-Path (Join-Path $FrontendRoot "node_modules"))) {
        Write-Step "Installing frontend dependencies"
        Push-Location $FrontendRoot
        try {
            npm install
            if ($LASTEXITCODE -ne 0) {
                throw "Frontend dependency install failed."
            }
        } finally {
            Pop-Location
        }
    }

    if ($ServicesOnly) {
        Write-Host ""
        Write-Host "Local data services are ready."
        Write-Host "Postgres: 127.0.0.1:$($env:POSTGRES_PORT)"
        Write-Host "Redis:    $($env:REDIS_URL)"
        return
    }

    if (Test-PortListening $BackendPort) {
        throw "Port $BackendPort is already in use. Stop the existing backend or run .\scripts\dev_stop.ps1."
    }
    if (Test-PortListening $FrontendPort) {
        throw "Port $FrontendPort is already in use. Stop the existing frontend or use -FrontendPort with another port."
    }

    Write-Step "Starting backend"
    $backendCommand = "& '$Python' -m uvicorn app.main:app --reload --host 127.0.0.1 --port $BackendPort"
    $backendProcess = Start-LoggedProcess `
        -Name "backend" `
        -WorkingDirectory $BackendRoot `
        -Command $backendCommand `
        -StdoutPath (Join-Path $LogRoot "backend.out.log") `
        -StderrPath (Join-Path $LogRoot "backend.err.log")

    Write-Step "Starting frontend"
    $frontendCommand = "`$env:VITE_API_BASE_URL='http://127.0.0.1:$BackendPort'; npm run dev -- --port $FrontendPort"
    $frontendProcess = Start-LoggedProcess `
        -Name "frontend" `
        -WorkingDirectory $FrontendRoot `
        -Command $frontendCommand `
        -StdoutPath (Join-Path $LogRoot "frontend.out.log") `
        -StderrPath (Join-Path $LogRoot "frontend.err.log")

    $state = [pscustomobject]@{
        root = $Root
        started_at = (Get-Date).ToString("o")
        backend_url = "http://127.0.0.1:$BackendPort"
        frontend_url = "http://127.0.0.1:$FrontendPort"
        processes = @($backendProcess, $frontendProcess)
    }
    $state | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -Path $PidFile

    Write-Step "Waiting for services"
    $backendReady = Wait-HttpOk "http://127.0.0.1:$BackendPort/health" 45
    $frontendReady = Wait-HttpOk "http://127.0.0.1:$FrontendPort/" 45

    if (-not $backendReady) {
        Write-Warning "Backend did not answer /health yet. Check $($backendProcess.stderr) and $($backendProcess.stdout)."
    }
    if (-not $frontendReady) {
        Write-Warning "Frontend did not answer yet. Check $($frontendProcess.stderr) and $($frontendProcess.stdout)."
    }

    Write-Host ""
    Write-Host "Backend:  http://127.0.0.1:$BackendPort"
    Write-Host "Docs:     http://127.0.0.1:$BackendPort/docs"
    Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
    Write-Host "Logs:     $LogRoot"
} finally {
    Restore-ScopedEnv
}
