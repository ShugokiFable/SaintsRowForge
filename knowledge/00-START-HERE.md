# Saints Row Forge External Knowledge Index

This directory consolidates the highest-value surviving public references for **Saints Row: The Third (legacy PC)** and **Saints Row IV (legacy PC / Workshop-era)** modding.

## Highest-value sources

- **Volition — Kinzie's Toy Box**: official SR3 alpha SDK material; file-format notes and generated Lua/script-action documentation.
- **Volition — Zinyak's Cache of Wonders**: official SRIV alpha SDK; your Forge already contains this, including crunchers, FBX conversion material, templates and tutorial PDFs.
- **ThomasJepp / Minimaul tools**: broad package, ASM, strings, audio, cloth, texture-metadata and mesh-metadata reference implementations.
- **SRZoneTools**: SRTT/SRIV zone-file reader/converter/finder source.
- **Gibbed.Volition**: additional Volition-engine file-format and tooling code under a permissive license.
- **SaintsRowMods File Search**: current searchable map of vanilla files -> packages/ASM containers.
- **SaintsRowMods tutorials**: practical load order, Workshop, textures, weapons, customization and scripting workflows.

## How an AI should use this

Use these references to answer questions like:

- Which VPP/STR2/ASM contains this asset?
- Which external cruncher should an adapter call for a PEG or mesh?
- Is this operation SRTT-only, SRIV-only, Workshop-only, or Re-Elected-only?
- Is a failure caused by the wrong base file/load order?
- What format should be reverse engineered next?

Do **not** infer implementation from documentation. The Forge's capability matrix is authoritative for what this build can actually execute.
