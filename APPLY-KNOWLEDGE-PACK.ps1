$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Ai = Join-Path $Root 'AI-INTEGRATION.md'
$Marker = '<!-- SRFORGE-KNOWLEDGE-PACK -->'
if (-not (Test-Path $Ai)) {
    Write-Warning "AI-INTEGRATION.md not found at $Ai. Files are still usable; nothing modified."
    exit 0
}
$text = Get-Content -Raw $Ai
if ($text -like "*$Marker*") {
    Write-Host 'Knowledge hook already installed.'
    exit 0
}
$block = @"

$Marker
## External knowledge layer

Before guessing about unsupported formats, load order, SDK behavior, Lua calls, textures, meshes, zones, audio, or Workshop packaging, search the additive `knowledge/` layer first:

```powershell
python scripts\KnowledgeSearch.py "<topic>"
```

`knowledge/SOURCES.json` is the machine-readable upstream map. Runtime evidence and the Forge capability matrix still outrank documentation. External source/tool availability does **not** mean the Forge implements that capability.
<!-- /SRFORGE-KNOWLEDGE-PACK -->
"@
Add-Content -Encoding UTF8 -Path $Ai -Value $block
Write-Host 'Added knowledge-layer hook to AI-INTEGRATION.md.'
