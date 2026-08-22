# Saints Row Forge

An AI-operable modding workbench for **Saints Row: The Third** (PC) and
**Saints Row IV** (PC). Deterministic Python core, honest capability
reporting, machine-readable receipts. [![tests](https://github.com/ShugokiFable/SaintsRowForge/actions/workflows/tests.yml/badge.svg)](https://github.com/ShugokiFable/SaintsRowForge/actions/workflows/tests.yml) Installable standalone; usable by any
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
| Cross-mod table **merge** (mod manager) | ✅ | ✅ |
| PEG/CPEG textures / meshes / audio / workshop | ❌ not implemented (reported `unsupported`) | ❌ not implemented (reported `unsupported`) |

### Merging mods (`srforge merge`)

Saints Row mods ship full copies of shared tables; installing two mods that
touch the same table normally means last-one-wins data loss. The forge
three-way merges every `.xtbl` against vanilla instead:

```bash
srforge merge --game sriv "path/to/ModA" "path/to/ModB"
```

- records added by either mod -> both survive
- distinct edits to different fields -> all applied
- two mods editing the same field -> **conflict logged** in
  `merge-report.json` (later-listed mod wins; every value is kept in the report)
- non-table file collisions (`.str2_pc`, `.asm_pc`, ...) -> flagged, later wins

Vanilla archives are **never written**; every build goes to a workspace.
The capability matrix (`srforge doctor`, `sr_capabilities`) is the source of
truth — statuses there always reflect what this build actually contains.

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

13 typed tools: `sr_doctor sr_game_detect sr_capabilities sr_knowledge_search
sr_asset_search sr_asset_origin sr_asset_extract sr_xtbl_query sr_project_new
sr_mod_patch sr_mod_diff sr_mod_build sr_conflicts`.

`sr_knowledge_search` queries the additive `knowledge/` reference layer
(format notes, SDK adapter recipes, upstream source map with provenance).
It is evidence for research, never proof of a capability - the capability
matrix stays authoritative.

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
