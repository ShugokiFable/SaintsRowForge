# Saints Row Forge - installer. No admin required.
# Installs the forge core to %LOCALAPPDATA%\SaintsRowForge and verifies it.
$ErrorActionPreference = "Stop"

$src = $PSScriptRoot
if (-not $src) { $src = (Get-Location).Path }
$dst = Join-Path $env:LOCALAPPDATA "SaintsRowForge"

Write-Host "== Saints Row Forge install =="
Write-Host "source: $src"
Write-Host "target: $dst"

New-Item -ItemType Directory -Force -Path $dst | Out-Null
foreach ($d in @("Workspaces", "Inbox", "logs")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $dst $d) | Out-Null
}

# core (code only - never game files, never third-party binaries)
foreach ($item in @("src", "mcp_server", "tests", "knowledge", "scripts",
                    "README.md", "AI-INTEGRATION.md", "THIRD-PARTY-NOTICES.md")) {
    $from = Join-Path $src $item
    if (Test-Path $from) {
        if ((Get-Item $from).PSIsContainer) {
            robocopy $from (Join-Path $dst $item) /MIR /NFL /NDL /NJH | Out-Null
            if ($LASTEXITCODE -ge 8) { Write-Error "robocopy failed on $item"; exit 1 }
        } else {
            Copy-Item -Force $from (Join-Path $dst $item)
        }
    }
}

# launcher
Copy-Item (Join-Path $src "START-HERE.bat") -Destination $dst -Force

# third-party tools stay OUT of the repo/installer: import them instead
Write-Host ""
Write-Host "Third-party tools (ThomasJepp, SRIV SDK) are NOT bundled."
Write-Host "Drop downloads into: $dst\Inbox   then run:"
Write-Host "    python src\srforge_cli.py deps import"
Write-Host ""

# verify
$py = "python"
& $py (Join-Path $dst "src\srforge_cli.py") doctor
if ($LASTEXITCODE -ne 0) { Write-Warning "doctor reported problems (see above)" }

Write-Host ""
Write-Host "Done. Double-click START-HERE.bat, or wire the MCP server:"
Write-Host "    python $dst\mcp_server\server.py"
