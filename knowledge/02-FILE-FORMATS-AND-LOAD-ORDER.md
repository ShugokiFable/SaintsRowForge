# File Formats + Load/Override Rules

## VPP_PC

General top-level archive used by Saints Row PC games. Treat version/flags/alignment as game-specific; do not reuse SRIV writer assumptions for SRTT without fixtures.

## STR2_PC

Streaming package/container. Changes usually interact with an accompanying ASM asset-assembler file. Rebuilding the STR2 without correctly updating the controlling ASM can produce silent non-loading or crashes.

## ASM_PC

Asset Assembler metadata describing streaming containers/assets. A successful binary write is not enough: validate the referenced container size/layout and reopen after packaging.

## XTBL

XML-like table data. Highest compatibility risk is **shared-table collision**. The Forge's three-way semantic merger is preferable to last-file-wins installation.

## PEG families

Common texture-related pairs include CPEG/GPEG and CVBM/GVBM forms. Use Volition crunchers for a verified adapter path before writing native texture encoders.

## Zone files

CZN/GZN pair CPU/GPU world-zone data. Volition's public notes describe a file-reference header followed by chunked world sections; SRZoneTools provides an independent implementation for SRTT/SRIV.

## SRTT override rule worth preserving

For original Saints Row: The Third PC, practical modding documentation describes the effective precedence as:

1. normal cache VPP archives
2. patch VPP archives
3. loose files beside the game executable

Therefore, when extracting a base for an edit, check patched archives before assuming the copy in a normal VPP is current.

## SRIV / Workshop

SRIV Workshop-era behavior adds subscribed Workshop content and mod packages to the picture. Do not reduce it to the SRTT rule. For each asset, determine the actual winner using the installed game/build and the SaintsRowMods file index where possible.
