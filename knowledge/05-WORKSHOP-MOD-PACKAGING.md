# SRIV Workshop / Packaging Knowledge

## Key practical differences

Workshop-era SRIV supports adding mod-specific content in ways that reduce the old need to replace complete shared files. This matters for compatibility and should influence Forge packaging/merge decisions.

## Useful workflows preserved by community documentation

- Extract VPP/STR2 assets to identify the real source container.
- Use the current/patched vanilla file as the merge base.
- Package new weapon/customization files into mod-specific archives.
- For offline testing, community SDK tutorials commonly save a Workshop-style VPP into a `mods` folder under the SRIV root before publishing.
- Localization and inventory/store tables are frequent dependencies for new customization/weapons.

## Forge recommendation

Add a packaging planner that can output:

- required tables
- streaming packages
- controlling ASM files
- localization dependencies
- expected output layout

before touching anything. This is ideal for deterministic AI operation because it turns a long tutorial into a machine-readable plan.
