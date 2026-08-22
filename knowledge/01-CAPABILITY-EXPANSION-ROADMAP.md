# Capability Expansion Roadmap

## 1. PEG / CPEG / CVBM / GPEG textures

Current Forge status: unsupported.

Best evidence sources:
- Existing local Zinyak SDK: `tools_vault/zinyaks/.../texture_crunch_wd.exe`, `peg_assemble_wd.exe`, converter templates and rule examples.
- ThomasJepp library: useful metadata structures for CPEG/CVBM but not a complete texture-content converter.
- SaintsRowMods texture tutorials: practical DDS -> PEG workflows and Workshop packaging expectations.

Recommended implementation order:
1. Add a **verified external adapter** around Volition's crunchers before attempting a native encoder.
2. Create deterministic fixture inputs and compare resulting PEG headers/entries against known-good SDK output.
3. Parse the produced CPEG/GPEG and verify dimensions, format, mip counts and asset names before reporting success.
4. Only mark `external_verified`; native support should come later.

## 2. Mesh / rig / customization assets

Current Forge status: unsupported.

Useful existing SDK binaries in the Forge:
- `mesh_crunch_wd.exe`
- `rig_cruncher_wd.exe`
- `material_library_crunch_wd.exe`
- `SaintsRow_FBX_Converter.py` / FBX conversion workflow

Recommended adapter pipeline:
FBX/source -> converter/rule generation -> Volition cruncher -> STR2/ASM packaging -> reopen/inspect -> optional in-game smoke test.

Do not mark mesh support native merely because a cruncher can produce files.

## 3. Zone files (CZN/GZN)

Best references:
- Volition Kinzie file-format notes document the zone/world header and chunked section identifiers.
- `clarosa/SRZoneTools` contains C# zone library, reader, converter, finder, patch helper and tests for SRTT/SRIV.

This is a strong candidate for a future read-only/native parser because the structure is documented and an independent reference implementation exists.

Suggested first milestone:
`sr_zone_inspect` -> identify header/version/sections/file references without modifying anything.

## 4. Lua/script actions

Best references:
- Kinzie's Toy Box includes a very large generated `script_actions` reference/index for SRTT.
- Many calls remain similar in SRIV, but SRIV differences must be tested rather than assumed.
- Community notes specifically call out the SRIV player constants `LOCAL_PLAYER` / `REMOTE_PLAYER` replacing older player placeholders in many examples.
- SaintExec is useful only as an **optional Re-Elected research reference**; it is not proof of legacy SRIV behavior.

Suggested Forge feature:
index Lua function names/parameters from official docs and extracted vanilla scripts, then expose local search/lint assistance without executing arbitrary scripts.

## 5. Audio

ThomasJepp is particularly useful here:
- streaming `*_media.bnk_pc`: read/write support in the reference library
- Wwise `.bnk_pc`: partial/read-oriented support

Possible first Forge milestone:
read-only inventory of soundbank metadata + hashes/offsets, then round-trip tests before write support.

## 6. Workshop packaging (SRIV)

Workshop-era SRIV changed mod composition significantly compared with old loose-root-only workflows. Prefer small mod-specific tables/assets instead of overwriting entire vanilla tables when the Workshop patch supports additions.

Forge packaging should keep these modes distinct:
- SRTT loose/root testing
- SRIV loose/root legacy testing
- SRIV `mods` folder/offline Workshop-style package
- Steam Workshop upload (external/manual boundary unless an official supported API/tool is intentionally integrated)
