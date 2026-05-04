$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Processes = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match "^python(\.exe)?$" -and
    $_.CommandLine -match "(^|\s)bot\.py(\s|$)"
}

if (-not $Processes) {
    Write-Host "Tidak ada proses bot.py lokal yang berjalan dari repo ini."
    exit 0
}

foreach ($Process in $Processes) {
    Write-Host "Stop bot lokal PID $($Process.ProcessId)"
    Stop-Process -Id $Process.ProcessId -Force
}
