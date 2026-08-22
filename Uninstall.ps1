# Saints Row Forge - uninstaller.
# Removes the installed copy. Workspaces are backed up, not deleted, unless -PurgeData.
param([switch]$PurgeData)
$dst = Join-Path $env:LOCALAPPDATA "SaintsRowForge"
if (-not (Test-Path $dst)) { Write-Host "Nothing to uninstall."; exit 0 }

if (-not $PurgeData) {
    $keep = Join-Path $env:LOCALAPPDATA "SaintsRowForge-backup"
    New-Item -ItemType Directory -Force -Path $keep | Out-Null
    foreach ($d in @("Workspaces", "Inbox", "tools_vault")) {
        $p = Join-Path $dst $d
        if (Test-Path $p) { Copy-Item -Recurse -Force $p (Join-Path $keep $d) }
    }
    Write-Host "Kept your data: $keep"
    Remove-Item -Recurse -Force $dst
} else {
    Remove-Item -Recurse -Force $dst
    Write-Host "Purged everything."
}
Write-Host "Uninstalled."
