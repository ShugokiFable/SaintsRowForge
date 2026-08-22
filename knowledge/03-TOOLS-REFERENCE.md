# Tool / Source Reference

## Already in the current Forge

### ThomasJepp / Minimaul toolchain
Useful for package extraction/building, ASM work, strings and reference source. Keep the known CustomizationItemClone revision caveat in mind: community documentation reports regressions in versions newer than rev121 for some items, with rev133 workarounds.

### Zinyak's Cache of Wonders (Volition SRIV SDK)
The current Forge already includes the high-value SDK payload, including:
- FBX converters
- mesh / rig / material crunchers
- texture cruncher / PEG assembler
- VPKG tool
- weapon/customization templates
- official tutorial PDFs

The missing piece is **Forge adapters + verification**, not more copies of the binaries.

## Recommended upstream references to fetch

### volition-inc/Kinzies-Toy-Box
Official SR3 alpha material. Especially valuable for:
- `file_formats.md`
- `script_actions/` generated Lua/API docs
- SR3 tools context

### clarosa/SRZoneTools
SRTT/SRIV zone file library + reader/converter/finder + tests.

### gibbed/Gibbed.Volition
Permissively licensed reference code covering Volition-developed game formats/tools. Useful as a second implementation when validating binary structures.

### Nathnefo/SaintExec
GPL-3.0 Lua executor for **SRIV Re-Elected**. Research-only for this Forge unless Re-Elected becomes a supported target. Do not conflate with legacy SRIV.

### Clippy95/SR.MixFix
Modern SRTT/SRTTR/SRIV-RE hooking/fix project. Useful future research for loose-file behavior and remaster/Re-Elected compatibility, but outside the current Forge's declared legacy SRTT/SRIV support.
