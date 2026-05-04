param(
    [Parameter(Mandatory = $true)]
    [string]$WorkerUrl,

    [string]$SecretToken = "",

    [string]$WebhookPath = "/telegram/webhook"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
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

$BotToken = Get-DotEnvValue "BOT_TOKEN"
if (-not $BotToken) {
    throw "BOT_TOKEN tidak ditemukan di .env. Isi token bot dulu."
}

$CleanWorkerUrl = $WorkerUrl.TrimEnd("/")
$WebhookUrl = "$CleanWorkerUrl$WebhookPath"

$Payload = [ordered]@{
    url = $WebhookUrl
    drop_pending_updates = $true
    allowed_updates = @("message", "callback_query")
}

if ($SecretToken) {
    $Payload.secret_token = $SecretToken
}

$PayloadJson = $Payload | ConvertTo-Json -Depth 5

$SetWebhookUrl = "https://api.telegram.org/bot$BotToken/setWebhook"
$Result = Invoke-RestMethod -Method Post -Uri $SetWebhookUrl -ContentType "application/json" -Body $PayloadJson

if (-not $Result.ok) {
    throw "Telegram setWebhook gagal: $($Result | ConvertTo-Json -Depth 5)"
}

$Info = Invoke-RestMethod -Method Get -Uri "https://api.telegram.org/bot$BotToken/getWebhookInfo"

Write-Host "Webhook aktif:"
Write-Host $Info.result.url
Write-Host "Pending update:" $Info.result.pending_update_count
