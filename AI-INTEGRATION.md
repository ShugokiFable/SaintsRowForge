# AI-INTEGRATION.md

How an AI agent drives Saints Row Forge end-to-end. Every operation is
deterministic, receipted, and safe-by-construction (vanilla never written).

## Principles the agent can rely on

1. **No silent success.** Builds reopen their own output before claiming
   victory; receipts record SHA-256 of inputs and outputs plus what was and
   wasn't verified.
2. **Capability statuses are honest.** Query `sr_capabilities` before
   attempting anything; statuses are `native`, `external_verified`,
   `adapter`, `experimental`, `read_only`, `manual`, `unsupported`.
   Never assume a status; ask.
3. **Scope guard.** After patching, a semantic diff must match the requested
   operations exactly. Collateral changes abort the build (`SRF-DIFF-*`).
4. **Provenance gate.** External tools execute only if registered in
   `tools_vault/manifest.json` with source URL + SHA-256.

## Canonical workflow (MCP or CLI - both wrap the same core)

```
sr_doctor / sr_game_detect          # where are the games?
sr_capabilities game=sriv           # what CAN I do?
sr_asset_search game=sriv pattern=weapons.xtbl
sr_xtbl_query game=sriv file=weapons.xtbl record=Pistol-Revolver
sr_project_new name=MyMod game=sriv
# write operations into <ws>/source/jobs/*.json:
#   {"operation":"set"|"multiply","file","record","field","value"}
sr_mod_patch workspace=<ws>
sr_mod_diff workspace=<ws>          # verify EXACTLY the intended changes
sr_mod_build workspace=<ws>         # package + receipt (reopen-verified)
sr_conflicts workspace_a=<a> workspace_b=<b>
```

CLI mirrors: `srforge doctor|asset|xtbl|project|mod|deps` with `--json`.

## Receipts

Every build writes `receipts/mod-build-<ts>.json`: game, workspace,
input/output SHA-256 hashes, per-op old→new values recorded from the actual
patched files, verification level (`verified_static` = reopened + semantic
diff clean; it does NOT claim in-game testing).

## Error contract

Errors are structured: `{code, message, hint}` with codes like
`SRF-GAME-002` (game not found), `SRF-JOB-001` (malformed job),
`SRF-DIFF-002` (scope guard), `SRF-PKG-*` (package failures).
Exit codes mirror severity (see README).

## Known limits (do not claim more)

- No PEG/CPEG, texture, mesh, or workshop code exists in this build; the
  capability matrix reports these as `unsupported` on purpose.
- Textures/meshes/audio conversion requires external tools (SRIV SDK
  crunchers) which must be imported first — and adapters are not written yet.
- ASM updates cover container size fields for rebuilt str2s; exotic
  containers (stubs, aux data) are preserved verbatim.
