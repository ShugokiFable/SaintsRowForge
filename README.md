# Saints Row Forge

An AI-operable modding workbench for **Saints Row: The Third** (PC) and
**Saints Row IV** (PC). Deterministic Python core, honest capability
reporting, machine-readable receipts. Installable standalone; usable by any
MCP-capable agent (Hermes, Claude Desktop, Codex, ...) or directly via CLI.

## Status (what actually works — all verified on real game installs)

| Area | SRTT | SRIV |
|---|---|---|
| Game detection + asset index | ✅ 21k files | ✅ 23k files |
| VPP packfiles | ✅ native v06 reader/writer | ✅ native v0A reader/writer |
| XTBL parse/query/patch/diff | ✅ | ✅ |
| ASM inspect/update (str2 sizes) | ✅ | ✅ byte-perfect round-trip vs vanilla |
| le_strings extract/build | ✅ | ✅ |
| Lua static lint | ✅ | ✅ |
| PEG/CPEG textures | read-only inspect only | read-only inspect only |
| Meshes / audio / workshop packaging | manual | experimental |

Vanilla archives are **never written**; every build goes to a workspace.

## Quickstart

```
python src\srforge_cli.py discover                 # find installed games
python src\srforge_cli.py doctor                   # full health report
python src\srforge_cli.py asset find weapons.xtbl --game sriv --json
python src\srforge_cli.py xtbl query --file weapons.xtbl \
    --record Pistol-Revolver --field Ragdoll_Force_Shoot --game sriv
python src\srforge_cli.py mod new MyMod --game sriv
# ... edit %LOCALAPPDATA%\SaintsRowForge\Workspaces\MyMod\source\jobs\*.json ...
python src\srforge_cli.py mod patch --workspace <path> --json
python src\srforge_cli.py mod diff  --workspace <path> --json   # semantic diff + scope guard
python src\srforge_cli.py mod build --workspace <path>          # package + receipt
```

Exit codes: `0` ok · `1` generic · `2` validation · `3` not-found ·
`4` dependency · `5` refused. `--json` works on every command.

## Example job file (`source/jobs/weapons.json`)

```json
{"operations": [
  {"operation": "set", "file": "weapons.xtbl",
   "record": "Pistol-Revolver", "field": "Ragdoll_Force_Shoot", "value": 450},
  {"operation": "multiply", "file": "weapons.xtbl",
   "record": "SMG-Storm", "field": "Magazine_Size", "value": 1.25}
]}
```

## MCP server (no dependencies)

```
python mcp_server\server.py        # stdio JSON-RPC; register with your client
```

12 typed tools: `sr_doctor sr_game_detect sr_capabilities sr_asset_search
sr_asset_origin sr_asset_extract sr_xtbl_query sr_project_new sr_mod_patch
sr_mod_diff sr_mod_build sr_conflicts`.

## Third-party tools

Never redistributed by this repo. Drop downloads into `%LOCALAPPDATA%\SaintsRowForge\Inbox`
(or `inbox/` in a checkout) and run `deps import`. Provenance (source URL +
SHA-256) is pinned in `tools_vault/manifest.json`; execution refuses
unregistered binaries. See THIRD-PARTY-NOTICES.md.

## Tests

```
python tests\run_tests.py          # 17 checks, no pytest needed, no game assets needed
```

Real-install validation is separate: doctor + the E2E flow above were run
against live Steam installs of both games.
