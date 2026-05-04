param(
    [string]$WorkerUrl = "",
    [switch]$SkipWebhook
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$WorkerDir = Join-Path $RepoRoot "cloudflare-worker"
$EnvPath = Join-Path $RepoRoot ".env"

function Get-DotEnvValue {
    param([string]$Name)

    if (-not (Test-Path $EnvPath)) {
        return ""
    }

    $line = Get-Content $EnvPath | Where-Object {
        $_ -match "^\s*$([regex]::Escape($Name))\s*="
    } | Select-Object -First 1

    if (-not $line) {
        return ""
    }

    return (($line -split "=", 2)[1]).Trim().Trim('"').Trim("'")
}

function New-WebhookSecret {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

$BotToken = Get-DotEnvValue "BOT_TOKEN"
if (-not $BotToken) {
    throw "BOT_TOKEN tidak ditemukan di .env. Isi token bot dulu."
}

$WebhookSecret = Get-DotEnvValue "WEBHOOK_SECRET"
if (-not $WebhookSecret) {
    $WebhookSecret = New-WebhookSecret
    Add-Content -Path $EnvPath -Value "WEBHOOK_SECRET=$WebhookSecret"
    Write-Host "WEBHOOK_SECRET baru ditambahkan ke .env."
}

Push-Location $WorkerDir
try {
    $WhoAmI = & npx wrangler whoami 2>&1
    if ($LASTEXITCODE -ne 0 -or ($WhoAmI -join "`n") -match "not authenticated") {
        Write-Host "Wrangler belum login. Browser Cloudflare akan dibuka untuk login."
        & npx wrangler login
        if ($LASTEXITCODE -ne 0) {
            throw "Login Cloudflare gagal atau dibatalkan."
        }
    }

    $DeployOutput = & npx wrangler deploy 2>&1
    $DeployOutput | ForEach-Object { Write-Host $_ }
    if ($LASTEXITCODE -ne 0) {
        throw "Deploy Cloudflare Worker gagal."
    }

    if (-not $WorkerUrl) {
        $DeployText = $DeployOutput -join "`n"
        $match = [regex]::Match($DeployText, "https://[^\s]+\.workers\.dev")
        if ($match.Success) {
            $WorkerUrl = $match.Value
        }
    }

    $TempSecrets = New-TemporaryFile
    @{
        BOT_TOKEN = $BotToken
        WEBHOOK_SECRET = $WebhookSecret
    } | ConvertTo-Json -Compress | Set-Content -Encoding utf8 -Path $TempSecrets

    try {
        & npx wrangler secret bulk $TempSecrets
        if ($LASTEXITCODE -ne 0) {
            throw "Upload secret ke Cloudflare gagal."
        }
    } finally {
        Remove-Item -Force $TempSecrets -ErrorAction SilentlyContinue
    }
} finally {
    Pop-Location
}

if ($SkipWebhook) {
    Write-Host "Deploy selesai. Set webhook dilewati."
    if ($WorkerUrl) {
        Write-Host "Worker URL:" $WorkerUrl
    }
    exit 0
}

if (-not $WorkerUrl) {
    throw "Worker URL tidak berhasil dibaca dari output deploy. Jalankan ulang dengan -WorkerUrl https://nama-worker.subdomain.workers.dev"
}

& (Join-Path $PSScriptRoot "set-cloudflare-webhook.ps1") -WorkerUrl $WorkerUrl -SecretToken $WebhookSecret
