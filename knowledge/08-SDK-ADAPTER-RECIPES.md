# SRIV SDK Adapter Recipes (from the SDK already in your Forge)

These are **adapter design notes**, not a claim that SaintsRowForge currently exposes the operations.

## Volition cruncher convention

The SRIV SDK crunchers consume a **rule file**. The SDK documentation's general shape is:

```text
<cruncher.exe> [-p <packfile_path>] ... <rule_file>
```

Example pattern:

```text
mesh_crunch_wd.exe -p shaders.vpp_pc my_mesh.rule
```

The material-library and mesh crunchers need shader parameter data; the SDK ships `shaders.vpp_pc` for that purpose.

### Cruncher ownership

- `texture_crunch_wd.exe`: source texture -> platform-specific VBM
- `peg_assemble_wd.exe`: VBM(s) -> platform-specific PEG
- `rig_cruncher_wd.exe`: `.rigx` -> platform rig
- `material_library_crunch_wd.exe`: `.matlibx` -> `.matlib_pc`
- `mesh_crunch_wd.exe`: `.cmeshx` -> game mesh

## FBX converter

The SDK converter produces XML-ish intermediate assets/rule data used by the crunchers.

Important historical requirements from the supplied SDK docs:
- Python 2.6.x era runtime
- wxPython matching Python 2.6
- Autodesk FBX Python SDK 2014-era bindings
- FBX export units: inches
- Up axis: Y-up

Because those dependencies are ancient, a Forge adapter should **detect and report them**, not silently install unsafe/abandoned runtimes system-wide.

A better modern architecture is:
1. accept FBX exported in the documented coordinate/unit convention;
2. run the legacy converter inside a clearly isolated/portable environment if possible;
3. capture stdout/stderr + produced files;
4. validate rule paths (the SDK warns old converter output may contain absolute paths);
5. rewrite only paths that are proven safe;
6. run the cruncher;
7. reopen/inspect produced assets;
8. record hashes and tool provenance.

## VPKG command surface

The SDK's `vpkg_wd.exe` supports operations including:

```text
-output_dir <dirname>
-list_allocators
-list_container_types
-extract_asm <asm filename>
-build_asm <asm filename>
-build_str2 <str2 filename>
-build_packfile <packfile filename> <filename ...>
-extract_packfile <filename>
-update_str2 <str2 filename> <asm filename> <filename ...>
```

Forge already has native package/ASM work, so VPKG is most useful as an **independent oracle** for differential tests, not as the default path.

## Differential-test idea

For every native writer:

```text
same vanilla fixture
  -> Forge writer
  -> official/reference writer where applicable
  -> reopen both
  -> compare semantic content, order, alignment and hashes where byte identity is expected
```

A difference is evidence to investigate, not automatically a Forge bug: official tools may normalize/reorder content differently.
