#Requires -Version 5.1
[CmdletBinding()]
param(
    [string]$BackendUrl = $env:STAGING_BACKEND_URL,
    [string]$FrontendUrl = $env:STAGING_FRONTEND_URL,
    [string]$AdminEmail = $env:STAGING_ADMIN_EMAIL,
    [string]$AdminPassword = $env:STAGING_ADMIN_PASSWORD,
    [string]$OwnerEmail = $env:STAGING_OWNER_EMAIL,
    [string]$OwnerPassword = $env:STAGING_OWNER_PASSWORD,
    [string]$PaymentWebhookSecret = $env:STAGING_PAYMENT_WEBHOOK_SECRET,
    [string]$EnvFile = $env:STAGING_ENV_FILE,
    [switch]$SkipE2E
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$BackendRoot = Join-Path $Root "backend"
$FrontendRoot = Join-Path $Root "frontend"
$Python = Join-Path $BackendRoot "venv\Scripts\python.exe"
$EnvSnapshot = @{}

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

try {
    if (-not $EnvFile) {
        $EnvFile = Join-Path $Root ".env.staging"
    } elseif (-not [System.IO.Path]::IsPathRooted($EnvFile)) {
        $EnvFile = Join-Path $Root $EnvFile
    }
    Import-DotEnv $EnvFile

    if (-not $BackendUrl) {
        $BackendUrl = $env:VITE_API_BASE_URL
    }
    if (-not $FrontendUrl -and $env:FRONTEND_PORT) {
        $FrontendUrl = "http://127.0.0.1:$($env:FRONTEND_PORT)"
    }
    if (-not $AdminEmail) {
        $AdminEmail = $env:INITIAL_ADMIN_EMAIL
    }
    if (-not $AdminPassword) {
        $AdminPassword = $env:INITIAL_ADMIN_PASSWORD
    }
    if (-not $OwnerEmail) {
        $OwnerEmail = $env:INITIAL_OWNER_EMAIL
    }
    if (-not $OwnerPassword) {
        $OwnerPassword = $env:INITIAL_OWNER_PASSWORD
    }
    if (-not $PaymentWebhookSecret) {
        $PaymentWebhookSecret = $env:PAYMENT_WEBHOOK_SECRET
    }

    if (-not $BackendUrl) {
        throw "BackendUrl is required. Pass -BackendUrl or set STAGING_BACKEND_URL."
    }
    if (-not $AdminEmail -or -not $AdminPassword -or -not $OwnerEmail -or -not $OwnerPassword) {
        throw "Staging smoke credentials are required. Pass them as parameters or STAGING_* environment variables."
    }
    if (-not $PaymentWebhookSecret) {
        throw "Payment webhook secret is required. Pass -PaymentWebhookSecret or set STAGING_PAYMENT_WEBHOOK_SECRET."
    }
    if (-not (Test-Path $Python)) {
        throw "Backend virtual environment was not found at $Python."
    }

    Write-Host "== Staging API smoke test =="
    Push-Location $BackendRoot
    try {
        & $Python scripts\smoke_test_api.py `
            --base-url $BackendUrl `
            --admin-email $AdminEmail `
            --admin-password $AdminPassword `
            --owner-email $OwnerEmail `
            --owner-password $OwnerPassword `
            --payment-webhook-secret $PaymentWebhookSecret
        if ($LASTEXITCODE -ne 0) {
            throw "Staging API smoke test failed."
        }
    } finally {
        Pop-Location
    }

    if (-not $SkipE2E) {
        if (-not $FrontendUrl) {
            throw "FrontendUrl is required for E2E. Pass -FrontendUrl, set STAGING_FRONTEND_URL, or use -SkipE2E."
        }

        Write-Host ""
        Write-Host "== Staging frontend E2E test =="
        Push-Location $FrontendRoot
        try {
            Set-ScopedEnv "VITE_API_BASE_URL" $BackendUrl
            Set-ScopedEnv "E2E_FRONTEND_URL" $FrontendUrl
            Set-ScopedEnv "E2E_OWNER_EMAIL" $OwnerEmail
            Set-ScopedEnv "E2E_OWNER_PASSWORD" $OwnerPassword
            npm run test:e2e -- --config=playwright.config.ts
            if ($LASTEXITCODE -ne 0) {
                throw "Staging frontend E2E test failed."
            }
        } finally {
            Pop-Location
        }
    }

    Write-Host ""
    Write-Host "Staging smoke checks passed."
} finally {
    Restore-ScopedEnv
}
