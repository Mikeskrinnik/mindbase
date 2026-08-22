# First-time Mindbase setup on Windows 10 (iMac 2012 home lab)
# Run: powershell -ExecutionPolicy Bypass -File scripts\windows\setup.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path } else { Get-Location }

Write-Host "Mindbase Windows setup" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

# Python
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    Write-Host "Install Python 3.11+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Check 'Add python.exe to PATH' during install."
    exit 1
}

Write-Host "Python: $($Python.Source)"

# iCloud path
$IcloudCandidates = @(
    "$env:USERPROFILE\iCloudDrive",
    "$env:USERPROFILE\Apple iCloud\iCloudDrive"
)
$IcloudRoot = $null
foreach ($p in $IcloudCandidates) {
    if (Test-Path $p) {
        $IcloudRoot = $p
        break
    }
}

if ($IcloudRoot) {
    Write-Host "iCloud Drive: $IcloudRoot" -ForegroundColor Green
} else {
    Write-Host "iCloud Drive not found. Install 'iCloud' from Microsoft Store and enable iCloud Drive." -ForegroundColor Yellow
    $IcloudRoot = "$env:USERPROFILE\iCloudDrive"
}

# .env
$EnvPath = Join-Path $RepoRoot ".env"
if (-not (Test-Path $EnvPath)) {
    Copy-Item (Join-Path $RepoRoot ".env.example") $EnvPath
    Write-Host "Created .env — edit paths before watch."
}

# Install packages
Write-Host "Installing sync-agent..."
& python -m pip install (Join-Path $RepoRoot "packages\shared") (Join-Path $RepoRoot "packages\sync-agent") -q

# Init iCloud folder
$MindbasePath = Join-Path $IcloudRoot "Mindbase"
& python -m mindbase_sync.cli init --icloud $MindbasePath

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Edit $EnvPath"
Write-Host "   ICLOUD_MINDBASE_PATH=$MindbasePath"
Write-Host "   OBSIDIAN_VAULT_PATH=$IcloudRoot\Obsidian\MyVault"
Write-Host "   MINDBASE_API_URL=http://localhost:8080  (or Tailscale IP of API host)"
Write-Host "2. Optional API on this PC: docker compose -f docker-compose.light.yml up -d"
Write-Host "3. Autostart: powershell -ExecutionPolicy Bypass -File scripts\windows\install-sync-task.ps1"
Write-Host "4. Test: python -m mindbase_sync.cli status"
