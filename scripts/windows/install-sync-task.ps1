# Mindbase sync-agent autostart on Windows (Task Scheduler)
# Run from repo root: powershell -ExecutionPolicy Bypass -File scripts\windows\install-sync-task.ps1

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not (Test-Path "$RepoRoot\packages\sync-agent")) {
    $RepoRoot = Split-Path $PSScriptRoot -Parent | Split-Path -Parent
}

$Python = (Get-Command python -ErrorAction SilentlyContinue)?.Source
if (-not $Python) {
    $Python = (Get-Command python3 -ErrorAction SilentlyContinue)?.Source
}
if (-not $Python) {
    Write-Error "Python not found. Install from https://python.org and check 'Add to PATH'."
}

$MindbaseSync = & $Python -c "import shutil; print(shutil.which('mindbase-sync') or '')" 2>$null
if (-not $MindbaseSync) {
    Write-Host "Installing sync-agent..."
    & $Python -m pip install "$RepoRoot\packages\shared" "$RepoRoot\packages\sync-agent" -q
    $MindbaseSync = & $Python -c "import shutil; print(shutil.which('mindbase-sync') or '')"
}
if (-not $MindbaseSync) {
    # Fallback: run as module
    $MindbaseSync = "$Python -m mindbase_sync.cli"
    $UseModule = $true
} else {
    $UseModule = $false
}

$EnvFile = "$RepoRoot\.env"
if (-not (Test-Path $EnvFile)) {
    Write-Warning ".env not found at $EnvFile — copy .env.example and edit paths first."
}

$TaskName = "MindbaseSyncWatch"
$Action = if ($UseModule) {
    New-ScheduledTaskAction -Execute $Python -Argument "-m mindbase_sync.cli watch" -WorkingDirectory $RepoRoot
} else {
    New-ScheduledTaskAction -Execute $MindbaseSync -Argument "watch" -WorkingDirectory $RepoRoot
}

$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Mindbase Obsidian+iCloud sync agent" -Force

Write-Host "Task '$TaskName' registered. Starts at logon."
Write-Host "Test now: mindbase-sync status"
Write-Host "Logs: check Task Scheduler -> History, or run 'mindbase-sync watch' manually."
