param(
    [switch]$IncludeFutureEditionRefs,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
$ForgeRoot = Split-Path -Parent $PSScriptRoot
$Dest = Join-Path $ForgeRoot 'upstream\repos'
$Cache = Join-Path $ForgeRoot 'upstream\cache'
New-Item -ItemType Directory -Force -Path $Dest,$Cache | Out-Null

$repos = @(
    @{ Name='Kinzies-Toy-Box'; Owner='volition-inc'; Branch='master'; Purpose='Official SR3 formats + script actions'; License='Upstream has no GitHub license metadata; local research checkout only' },
    @{ Name='Zinyaks-Cache-Of-Wonders'; Owner='volition-inc'; Branch='master'; Purpose='Official SRIV SDK reference (already bundled in current Forge)'; License='Local research/update mirror only' },
    @{ Name='SRZoneTools'; Owner='clarosa'; Branch='master'; Purpose='SRTT/SRIV zone parser/converter/finder reference'; License='Custom redistribution license in repo' },
    @{ Name='Gibbed.Volition'; Owner='gibbed'; Branch='master'; Purpose='Volition file-format/tool cross-reference'; License='zlib' },
    @{ Name='ThomasJepp.SaintsRow'; Owner='saintsrowmods2'; Branch='master'; Purpose='Reference library: packages/ASM/strings/audio/cloth/etc'; License='license.txt in repo' }
)
if ($IncludeFutureEditionRefs) {
    $repos += @{ Name='SaintExec'; Owner='Nathnefo'; Branch='main'; Purpose='SRIV Re-Elected Lua research ONLY'; License='GPL-3.0' }
    $repos += @{ Name='SR.MixFix'; Owner='Clippy95'; Branch='master'; Purpose='SRTT/SRTTR/SRIV-RE hook/loose-file future research'; License='See upstream' }
}

$records = @()
foreach ($r in $repos) {
    $target = Join-Path $Dest $r.Name
    if ((Test-Path $target) -and -not $Force) {
        Write-Host "[SKIP] $($r.Name) already exists (use -Force to refresh)"
        continue
    }
    $zip = Join-Path $Cache ($r.Name + '.zip')
    $url = "https://github.com/$($r.Owner)/$($r.Name)/archive/refs/heads/$($r.Branch).zip"
    Write-Host "[GET ] $($r.Name) - $($r.Purpose)"
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $zip
        $hash = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLowerInvariant()
        $tmp = Join-Path $Cache ($r.Name + '-extract')
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $tmp
        Expand-Archive -Path $zip -DestinationPath $tmp -Force
        $inner = Get-ChildItem -Directory $tmp | Select-Object -First 1
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue $target
        Move-Item $inner.FullName $target
        Remove-Item -Recurse -Force $tmp
        $records += [pscustomobject]@{
            name=$r.Name; source=$url; sha256=$hash; fetched=(Get-Date).ToString('o'); purpose=$r.Purpose; license_note=$r.License
        }
        Write-Host "[ OK ] $($r.Name) sha256=$hash"
    } catch {
        Write-Warning "Failed $($r.Name): $($_.Exception.Message)"
    }
}
$manifest = Join-Path $ForgeRoot 'upstream\fetched-manifest.json'
$records | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 $manifest
Write-Host "Manifest: $manifest"
