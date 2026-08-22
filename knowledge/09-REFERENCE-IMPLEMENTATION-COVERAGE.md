# Reference Implementation Coverage

## ThomasJepp.SaintsRow

Useful external coverage to mine for tests/adapters:

- SRTT package files: read-oriented reference support
- SRTT ASM: read/write support in the reference library (historically noted as less tested than SRIV)
- SRIV packages: read/write
- SRIV ASM: read/write
- SRTT/SRIV language strings: read/write
- SRTT/SRIV streaming soundbank media: read/write
- Wwise soundbank structures: partial/read-oriented
- CPEG/CVBM: metadata-level support, not full texture-content conversion
- static mesh: metadata-level support, not full model conversion
- cloth simulation: read/write

This makes ThomasJepp especially useful for **cross-validation** and for expanding Forge's read-only introspection before native editing.

## SRZoneTools

Dedicated to SRTT/SRIV world-zone files and includes:
- zone library
- reader
- converter
- finder
- patch-related utility
- tests/examples

This should be the first external implementation consulted for a native `czn/gzn` parser.

## Gibbed.Volition

Use as an additional independent implementation/source of constants and binary structure ideas. It is valuable because agreement between multiple independently written parsers is stronger evidence than copying one implementation verbatim.
