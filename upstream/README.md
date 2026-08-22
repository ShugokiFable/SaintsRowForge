# Upstream Reference Cache

This directory intentionally starts small. Run:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\Fetch-Upstream-References.ps1
```

to download current public source/reference repositories into `upstream/repos/` and write SHA-256 provenance to `upstream/fetched-manifest.json`.

The fetcher is intentionally separate from Forge's executable `tools_vault`: source references are **not trusted executables** and must never bypass `deps import` / provenance gates.
