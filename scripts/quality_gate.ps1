#Requires -Version 5.1
[CmdletBinding()]
param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$WithSmoke,
    [switch]$WithE2E,
    [int]$QualityBackendPort = 8010,
    [int]$QualityFrontendPort = 3010,
    [string]$LocalEnvFile = $env:LOCAL_ENV_FILE
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $Root "backend"
$FrontendRoot = Join-Path $Root "frontend"
$RuntimeRoot = Join-Path $Root ".dev"
$LogRoot = Join-Path $RuntimeRoot "logs"
$Python = Join-Path $BackendRoot "venv\Scripts\python.exe"
$QualityBackendUrl = "http://127.0.0.1:$QualityBackendPort"
$QualityBackendProcess = $null
$EnvSnapshot = @{}

function Invoke-Step([string]$Label, [scriptblock]$Command) {
    Write-Host ""
    Write-Host "== $Label =="
    & $Command
    Write-Host "OK $Label"
}

function Test-PortListening([int]$Port) {
    $connection = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return [bool]$connection
}

function Test-Command([string]$CommandName) {
    return [bool](Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Wait-HttpOk([string]$Url, [int]$TimeoutSeconds = 45) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 -Uri $Url
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 300) {
                return $true
            }
        } catch {
            Start-Sleep -Milliseconds 800
        }
    } while ((Get-Date) -lt $deadline)

    return $false
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

function Ensure-LocalDataServices {
    $postgresServer = $env:POSTGRES_SERVER
    $postgresPortValue = $env:POSTGRES_PORT
    if (-not $postgresPortValue) {
        $postgresPortValue = "5435"
    }
    $postgresPort = [int]$postgresPortValue
    $usesLocalPostgres = $postgresServer -in @("127.0.0.1", "localhost", "")

    if (-not $usesLocalPostgres -or (Test-PortListening $postgresPort)) {
        return
    }

    if (-not (Test-Command "docker")) {
        throw "Local Postgres is not listening on 127.0.0.1:$postgresPort, and Docker CLI was not found. Start the database before running the quality gate."
    }

    Write-Host "Local Postgres is not listening on 127.0.0.1:$postgresPort. Starting Docker data services..."
    Push-Location $Root
    try {
        docker compose up -d db redis
        if ($LASTEXITCODE -ne 0) {
            throw "Docker data services failed to start."
        }
    } finally {
        Pop-Location
    }

    $deadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortListening $postgresPort) {
            return
        }
        Start-Sleep -Milliseconds 800
    }
    throw "Local Postgres did not start on 127.0.0.1:$postgresPort within 45 seconds."
}

function Start-QualityBackend {
    if (-not (Test-Path $Python)) {
        throw "Backend virtual environment was not found at $Python."
    }
    if (Test-PortListening $QualityBackendPort) {
        throw "Quality backend port $QualityBackendPort is already in use."
    }

    New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
    $stdout = Join-Path $LogRoot "quality-backend.out.log"
    $stderr = Join-Path $LogRoot "quality-backend.err.log"
    $qualityCorsOrigins = @(
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:$QualityFrontendPort",
        "http://127.0.0.1:$QualityFrontendPort"
    )
    if ($env:BACKEND_CORS_ORIGINS) {
        $qualityCorsOrigins += $env:BACKEND_CORS_ORIGINS -split ","
    }
    $qualityCorsOrigins = $qualityCorsOrigins `
        | ForEach-Object { $_.Trim() } `
        | Where-Object { $_ } `
        | Select-Object -Unique

    Write-Host "Starting temporary backend at $QualityBackendUrl..."
    $previousCorsOrigins = $env:BACKEND_CORS_ORIGINS
    try {
        Set-ScopedEnv "BACKEND_CORS_ORIGINS" ($qualityCorsOrigins | ConvertTo-Json -Compress)
        $process = Start-Process `
            -FilePath $Python `
            -ArgumentList @(
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "$QualityBackendPort"
            ) `
            -WorkingDirectory $BackendRoot `
            -RedirectStandardOutput $stdout `
            -RedirectStandardError $stderr `
            -WindowStyle Hidden `
            -PassThru
    } finally {
        if ($null -eq $previousCorsOrigins) {
            Remove-Item Env:\BACKEND_CORS_ORIGINS -ErrorAction SilentlyContinue
        } else {
            $env:BACKEND_CORS_ORIGINS = $previousCorsOrigins
        }
    }

    if (-not (Wait-HttpOk "$QualityBackendUrl/health" 60)) {
        Write-Warning "Temporary backend did not become healthy."
        if (Test-Path $stderr) {
            Get-Content $stderr -Tail 40
        }
        taskkill /PID $process.Id /T /F | Out-Null
        throw "Temporary backend failed to start."
    }

    return $process
}

function Stop-QualityBackend {
    if ($null -eq $QualityBackendProcess) {
        return
    }
    $running = Get-Process -Id $QualityBackendProcess.Id -ErrorAction SilentlyContinue
    if ($running) {
        Write-Host ""
        Write-Host "Stopping temporary backend ($($QualityBackendProcess.Id))..."
        taskkill /PID $QualityBackendProcess.Id /T /F | Out-Null
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
    $SmokeAdminEmail = if ($env:INITIAL_ADMIN_EMAIL) { $env:INITIAL_ADMIN_EMAIL } else { "admin@cognivex.com" }
    $SmokeAdminPassword = if ($env:INITIAL_ADMIN_PASSWORD) { $env:INITIAL_ADMIN_PASSWORD } else { "adminpassword" }
    $SmokeOwnerEmail = if ($env:INITIAL_OWNER_EMAIL) { $env:INITIAL_OWNER_EMAIL } else { "owner@chickenspot.com" }
    $SmokeOwnerPassword = if ($env:INITIAL_OWNER_PASSWORD) { $env:INITIAL_OWNER_PASSWORD } else { "ownerpassword" }
    $SmokePaymentWebhookSecret = if ($env:PAYMENT_WEBHOOK_SECRET) { $env:PAYMENT_WEBHOOK_SECRET } else { "replace-this-payment-webhook-secret" }

    $needsBackendRuntime = (-not $SkipBackend) -or $WithSmoke -or ($WithE2E -and -not $SkipFrontend)
    if ($needsBackendRuntime -and -not (Test-Path $Python)) {
        throw "Backend virtual environment was not found at $Python."
    }

    if (-not $SkipBackend) {
        Ensure-LocalDataServices
        Invoke-Step "Backend quality gate" {
            Push-Location $BackendRoot
            try {
                & $Python scripts\quality_gate.py
                if ($LASTEXITCODE -ne 0) {
                    throw "Backend quality gate failed."
                }
            } finally {
                Pop-Location
            }
        }
    }

    if ($WithSmoke -or ($WithE2E -and -not $SkipFrontend)) {
        Ensure-LocalDataServices
        Invoke-Step "Local database migrations" {
            Push-Location $BackendRoot
            try {
                & $Python -m alembic upgrade head
                if ($LASTEXITCODE -ne 0) {
                    throw "Local database migrations failed."
                }
            } finally {
                Pop-Location
            }
        }
        $QualityBackendProcess = Start-QualityBackend
    }

    if ($WithSmoke) {
        Invoke-Step "Live API smoke test" {
            Push-Location $BackendRoot
            try {
                & $Python scripts\smoke_test_api.py `
                    --base-url $QualityBackendUrl `
                    --admin-email $SmokeAdminEmail `
                    --admin-password $SmokeAdminPassword `
                    --owner-email $SmokeOwnerEmail `
                    --owner-password $SmokeOwnerPassword `
                    --payment-webhook-secret $SmokePaymentWebhookSecret
                if ($LASTEXITCODE -ne 0) {
                    throw "Live API smoke test failed."
                }
            } finally {
                Pop-Location
            }
        }
    }

    if (-not $SkipFrontend) {
        Invoke-Step "Frontend dependency check" {
            Push-Location $FrontendRoot
            try {
                if (-not (Test-Path "node_modules")) {
                    npm install
                    if ($LASTEXITCODE -ne 0) {
                        throw "Frontend dependency install failed."
                    }
                }
            } finally {
                Pop-Location
            }
        }

        Invoke-Step "Frontend lint" {
            Push-Location $FrontendRoot
            try {
                npm run lint
                if ($LASTEXITCODE -ne 0) {
                    throw "Frontend lint failed."
                }
            } finally {
                Pop-Location
            }
        }

        Invoke-Step "Frontend build" {
            Push-Location $FrontendRoot
            try {
                npm run build
                if ($LASTEXITCODE -ne 0) {
                    throw "Frontend build failed."
                }
            } finally {
                Pop-Location
            }
        }

        if ($WithE2E) {
            Invoke-Step "Frontend end-to-end tests" {
                Push-Location $FrontendRoot
                $previousApiUrl = $env:VITE_API_BASE_URL
                $previousE2EPort = $env:E2E_FRONTEND_PORT
                $previousReuseServer = $env:E2E_REUSE_EXISTING_SERVER
                try {
                    if (Test-PortListening $QualityFrontendPort) {
                        throw "Quality frontend port $QualityFrontendPort is already in use. Stop the existing frontend dev server or rerun with -QualityFrontendPort <free-port>."
                    }
                    Set-ScopedEnv "VITE_API_BASE_URL" $QualityBackendUrl
                    Set-ScopedEnv "E2E_FRONTEND_PORT" "$QualityFrontendPort"
                    Set-ScopedEnv "E2E_REUSE_EXISTING_SERVER" "false"
                    npm run test:e2e
                    if ($LASTEXITCODE -ne 0) {
                        throw "Frontend end-to-end tests failed."
                    }
                } finally {
                    if ($null -eq $previousApiUrl) {
                        Remove-Item Env:\VITE_API_BASE_URL -ErrorAction SilentlyContinue
                    } else {
                        $env:VITE_API_BASE_URL = $previousApiUrl
                    }
                    if ($null -eq $previousE2EPort) {
                        Remove-Item Env:\E2E_FRONTEND_PORT -ErrorAction SilentlyContinue
                    } else {
                        $env:E2E_FRONTEND_PORT = $previousE2EPort
                    }
                    if ($null -eq $previousReuseServer) {
                        Remove-Item Env:\E2E_REUSE_EXISTING_SERVER -ErrorAction SilentlyContinue
                    } else {
                        $env:E2E_REUSE_EXISTING_SERVER = $previousReuseServer
                    }
                    Pop-Location
                }
            }
        }
    }

    Write-Host ""
    Write-Host "Quality gate passed."
} finally {
    Stop-QualityBackend
    Restore-ScopedEnv
}
