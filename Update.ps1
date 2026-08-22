# Saints Row Forge - updater. Re-copies code from the checkout, keeps data.
$ErrorActionPreference = "Stop"
$src = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$dst = Join-Path $env:LOCALAPPDATA "SaintsRowForge"

if (-not (Test-Path $dst)) {
    Write-Error "Not installed. Run Install.ps1 first."
    exit 1
}
foreach ($item in @("src", "mcp_server", "tests")) {
    Copy-Item -Recurse -Force (Join-Path $src $item) (Join-Path $dst $item)
}
Copy-Item (Join-Path $src "START-HERE.bat") -Destination $dst -Force
Write-Host "Updated code at $dst (Workspaces/Inbox/tools_vault untouched)."
& python (Join-Path $dst "src\srforge_cli.py") doctor
