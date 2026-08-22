"""Capability registry: what each game adapter can actually do.

Statuses: native | external_verified | adapter | experimental |
read_only | manual | unsupported
Never claim a capability without evidence; doctor reads from here.
"""
from .receipts import ForgeError

# capability -> per-game status
MATRIX = {
    "srtt": {
        "vpp.read":          {"status": "native"},
        "vpp.write":         {"status": "native", "note": "v0x0A writer, cross-checked vs ThomasJepp reader"},
        "str2.read":         {"status": "native"},
        "str2.write":        {"status": "native"},
        "asm.read":          {"status": "native"},
        "asm.update":        {"status": "native", "note": "0x0B layout ported from reference implementation"},
        "asm.update.external": {"status": "external_verified", "requires": ["thomasjepp"], "note": "Stream2.exe update"},
        "xtbl.parse":        {"status": "native"},
        "xtbl.patch":        {"status": "native"},
        "xtbl.diff":         {"status": "native"},
        "lua.inspect":       {"status": "native", "note": "SR Lua dialect: static checks only"},
        "strings.read":      {"status": "native"},
        "strings.write":     {"status": "native"},
        "peg.read":          {"status": "unsupported",
                               "note": "no PEG/CPEG parser in this build yet"},
        "mesh.export":       {"status": "manual", "requires": ["sriv-sdk-legacy"]},
        "game.detect":       {"status": "native"},
    },
    "sriv": {
        "vpp.read":          {"status": "native"},
        "vpp.write":         {"status": "native"},
        "str2.read":         {"status": "native"},
        "str2.write":        {"status": "native", "note": "condensed+compressed like reference builder"},
        "asm.read":          {"status": "native"},
        "asm.update":        {"status": "native"},
        "asm.update.external": {"status": "external_verified", "requires": ["thomasjepp"]},
        "xtbl.parse":        {"status": "native"},
        "xtbl.patch":        {"status": "native"},
        "xtbl.diff":         {"status": "native"},
        "lua.inspect":       {"status": "native", "note": "static checks only; runtime behavior unproven"},
        "strings.read":      {"status": "native"},
        "strings.write":     {"status": "native"},
        "peg.read":          {"status": "unsupported",
                               "note": "no PEG/CPEG parser in this build yet"},
        "texture.convert":   {"status": "unsupported",
                               "note": "no texture converter in this build yet"},
        "mesh.export":       {"status": "manual", "requires": ["zinyaks-crunchers"],
                               "note": "SDK crunchers exist; FBX->xml step needs legacy Python 2.6 chain; no adapter coded"},
        "workshop.package":  {"status": "unsupported",
                               "note": "partial-table merge designed but not implemented"},
        "game.detect":       {"status": "native"},
    },
}

EVIDENCE_LEVELS = [
    "generated", "syntax_validated", "reopened", "tool_validated",
    "cross_tool_validated", "installed", "game_launched",
    "runtime_smoke_tested", "human_visual_verified",
]


def get(game, cap):
    m = MATRIX.get(game)
    if not m:
        raise ForgeError("SRF-GAME-001", f"unknown game {game!r} (use srtt|sriv)")
    return m.get(cap)


def for_game(game):
    """Whole per-game matrix (used by doctor + sr_capabilities)."""
    if game not in MATRIX:
        raise ForgeError("SRF-GAME-001", f"unknown game {game!r} (use srtt|sriv)")
    import copy
    return copy.deepcopy(MATRIX[game])


def require(game, cap):
    c = get(game, cap)
    if not c or c["status"] in ("unsupported", None):
        raise ForgeError("SRF-CAP-001",
                         f"{game}.{cap} is not supported by this build",
                         hint="run: srforge doctor --json")
    return c


def snapshot():
    import copy
    return copy.deepcopy(MATRIX)
