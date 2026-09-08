#Requires -Version 5.1
[CmdletBinding()]
param(
    [int]$SecretBytes = 48,
    [int]$PasswordBytes = 24
)

$ErrorActionPreference = "Stop"

function New-Base64UrlSecret([int]$Bytes) {
    $buffer = New-Object byte[] $Bytes
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $rng.GetBytes($buffer)
    } finally {
        $rng.Dispose()
    }
    return [Convert]::ToBase64String($buffer).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

Write-Host "Use these values once, then store them only in the hosting dashboards."
Write-Host ""
Write-Host "SECRET_KEY=$(New-Base64UrlSecret $SecretBytes)"
Write-Host "PAYMENT_WEBHOOK_SECRET=$(New-Base64UrlSecret $SecretBytes)"
Write-Host "WHATSAPP_WEBHOOK_VERIFY_TOKEN=$(New-Base64UrlSecret 24)"
Write-Host "WHATSAPP_WEBHOOK_APP_SECRET=$(New-Base64UrlSecret $SecretBytes)"
Write-Host "INITIAL_ADMIN_PASSWORD=$(New-Base64UrlSecret $PasswordBytes)"
