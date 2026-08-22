"""Saints Row Forge - MCP server (dependency-free).

Speaks the MCP stdio wire protocol (newline-delimited JSON-RPC 2.0)
directly: initialize / tools/list / tools/call / ping. Works with any
MCP client (Hermes, Claude Desktop, Codex, ...):

    "srforge-mcp": {
        "command": "python",
        "args": ["<forge>/mcp_server/server.py"]
    }

Every tool wraps the SAME core the CLI uses; results are JSON text.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from srforge.core.receipts import ForgeError
from srforge.core import discovery, capabilities, modbuild
from srforge.core.workspace import new_workspace, load_workspace

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "saints-row-forge", "version": "1.0.0"}


# ---------------------------------------------------------------- helpers

def _index(game):
    from srforge.core.index import GameIndex
    extra = [os.environ.get(f"SRFORGE_GAME_{game.upper()}")]
    det = discovery.find_game(game, [e for e in extra if e])
    if not det:
        raise ForgeError("SRF-GAME-002", f"{game} installation not found",
                         hint="set SRFORGE_GAME_SRTT / SRFORGE_GAME_SRIV "
                              "or run srforge discover")
    return GameIndex(det["install_path"], game)


def _j(obj):
    return json.dumps(obj, indent=2, default=str)


def _game_of(workspace):
    meta = load_workspace(workspace)
    g = meta.get("game")
    if not g:
        raise ForgeError("SRF-WS-001", f"workspace has no game: {workspace}")
    return g


# ------------------------------------------------------------------ tools
# name -> (callable(args:dict) -> obj, json-schema, description)

TOOLS = {}


def tool(name, schema, desc):
    def deco(fn):
        TOOLS[name] = (fn, schema, desc)
        return fn
    return deco


@tool("sr_doctor", {"type": "object", "properties": {}},
      "Full health report: both games, asset indexes, capability statuses.")
def sr_doctor(a):
    out = {}
    for game in ("srtt", "sriv"):
        det = discovery.find_game(game, [os.environ.get(f"SRFORGE_GAME_{game.upper()}")]
                                  if os.environ.get(f"SRFORGE_GAME_{game.upper()}") else [])
        entry = {"found": bool(det)}
        if det:
            idx = _index(game)
            entry["install_path"] = det["install_path"]
            entry["indexed_files"] = len(idx.entries)
            entry["capabilities"] = capabilities.for_game(game)
        out[game] = entry
    return out


@tool("sr_game_detect",
      {"type": "object", "properties": {}},
      "Detect installed Saints Row games (Steam paths, overrides via env).")
def sr_game_detect(a):
    return {g: discovery.find_game(g, [os.environ.get(f"SRFORGE_GAME_{g.upper()}")]
                                   if os.environ.get(f"SRFORGE_GAME_{g.upper()}") else [])
            for g in ("srtt", "sriv")}


@tool("sr_capabilities",
      {"type": "object", "properties": {"game": {"type": "string",
       "enum": ["srtt", "sriv"]}}, "required": ["game"]},
      "Per-game capability matrix with honest statuses.")
def sr_capabilities(a):
    return capabilities.for_game(a["game"])


@tool("sr_knowledge_search",
      {"type": "object", "properties": {"query": {"type": "string"}},
       "required": ["query"]},
      "Search the additive knowledge/ layer (format notes, SDK recipes, "
      "upstream source map). Reference only - never proof of a capability.")
def sr_knowledge_search(a):
    script = Path(__file__).resolve().parents[1] / "scripts" / "KnowledgeSearch.py"
    r = subprocess.run([sys.executable, str(script), a["query"]],
                       capture_output=True, text=True, timeout=30)
    return {"results": (r.stdout + r.stderr)[-4000:]}


@tool("sr_asset_search",
      {"type": "object",
       "properties": {"game": {"type": "string"}, "pattern": {"type": "string"},
                      "limit": {"type": "integer"}},
       "required": ["game", "pattern"]},
      "Find assets by substring/regex across the indexed game archives.")
def sr_asset_search(a):
    idx = _index(a["game"])
    pat = a["pattern"].lower()
    lim = int(a.get("limit", 50))
    hits = [{"logical": n, "container": c, "precedence": p}
            for n, c, p in idx.entries if pat in n][:lim]
    return {"matches": hits, "total_shown": len(hits)}


@tool("sr_asset_origin",
      {"type": "object",
       "properties": {"game": {"type": "string"}, "name": {"type": "string"}},
       "required": ["game", "name"]},
      "Which archive wins for a logical file under load precedence.")
def sr_asset_origin(a):
    h = _index(a["game"]).find(a["name"])
    return h or {"error": "not found"}


@tool("sr_asset_extract",
      {"type": "object",
       "properties": {"game": {"type": "string"}, "name": {"type": "string"},
                      "dest": {"type": "string"}},
       "required": ["game", "name", "dest"]},
      "Extract one logical file to dest directory.")
def sr_asset_extract(a):
    return modbuild.extract_to(_index(a["game"]), a["name"], a["dest"])


@tool("sr_xtbl_query",
      {"type": "object",
       "properties": {"game": {"type": "string"}, "file": {"type": "string"},
                      "record": {"type": "string"}, "field": {"type": "string"}},
       "required": ["game", "file", "record"]},
      "Read a record (or single field) from an XTBL inside vanilla archives.")
def sr_xtbl_query(a):
    import tempfile
    from srforge.formats.xtbl import Xtbl
    with tempfile.TemporaryDirectory() as td:
        modbuild.extract_to(_index(a["game"]), a["file"], td)
        x = Xtbl(open(os.path.join(td, os.path.basename(a["file"])),
                      encoding="utf-8", errors="replace").read())
    r = x.find_record(a["record"])
    if r is None:
        raise ForgeError("SRF-XTBL-004", f"record not found: {a['record']}")
    if a.get("field"):
        el = r.find(".//" + a["field"])
        return {"record": a["record"], "field": a["field"],
                "value": None if el is None else (el.text or "").strip()}
    return {"record": a["record"],
            "fields": {c.tag: (c.text or "").strip()
                       for c in r if not len(c)}}


@tool("sr_project_new",
      {"type": "object",
       "properties": {"name": {"type": "string"}, "game": {"type": "string"}},
       "required": ["name", "game"]},
      "Create a mod workspace under %LOCALAPPDATA%/SaintsRowForge/Workspaces.")
def sr_project_new(a):
    root = os.path.join(os.environ.get("SRFORGE_HOME",
                        os.path.join(os.environ["LOCALAPPDATA"], "SaintsRowForge")),
                        "Workspaces")
    return {"workspace": new_workspace(root, a["name"], a["game"])}


@tool("sr_mod_patch",
      {"type": "object", "properties": {"workspace": {"type": "string"}},
       "required": ["workspace"]},
      "Apply source/jobs/*.json operations to extracted files -> working/.")
def sr_mod_patch(a):
    ws = a["workspace"]
    ops = modbuild.load_jobs(ws)
    res = modbuild.apply_ops(ops, os.path.join(ws, "extracted"),
                             os.path.join(ws, "working"))
    return {"patched": len(res), "results": res}


@tool("sr_mod_diff",
      {"type": "object", "properties": {"workspace": {"type": "string"}},
       "required": ["workspace"]},
      "Semantic diff extracted vs working + scope guard.")
def sr_mod_diff(a):
    ws = a["workspace"]
    changes = modbuild.semantic_diff_report(os.path.join(ws, "extracted"),
                                            os.path.join(ws, "working"))
    ops = modbuild.load_jobs(ws)
    modbuild.guard_scope(ops, changes)
    return {"changed_fields": len(changes), "changes": changes}


@tool("sr_mod_build",
      {"type": "object", "properties": {"workspace": {"type": "string"}},
       "required": ["workspace"]},
      "Build distributable package(s) + receipt; reopen-verifies output.")
def sr_mod_build(a):
    ws = a["workspace"]
    game = _game_of(ws)
    idx = _index(game)
    ops = modbuild.load_jobs(ws)
    files = sorted({op["file"] for op in ops if op.get("file")})
    for f in files:
        if not os.path.isfile(os.path.join(ws, "extracted", f)):
            modbuild.extract_to(idx, f, os.path.join(ws, "extracted"))
    modbuild.apply_ops(ops, os.path.join(ws, "extracted"),
                       os.path.join(ws, "working"))
    changes = modbuild.semantic_diff_report(os.path.join(ws, "extracted"),
                                            os.path.join(ws, "working"))
    modbuild.guard_scope(ops, changes)
    pkg_dir = os.path.join(ws, "package")
    os.makedirs(pkg_dir, exist_ok=True)
    built = []
    for f in files:
        src = os.path.join(ws, "working", f)
        out_vpp = os.path.join(pkg_dir, os.path.splitext(f)[0] + ".vpp_pc")
        built.append(modbuild.build_package(game, os.path.dirname(src),
                                            out_vpp))
    return {"status": "verified_static", "built": built,
            "changed_fields": len(changes)}


@tool("sr_conflicts",
      {"type": "object",
       "properties": {"workspace_a": {"type": "string"},
                      "workspace_b": {"type": "string"}},
       "required": ["workspace_a", "workspace_b"]},
      "Files two mods both touch (would conflict on install).")
def sr_conflicts(a):
    def touched(ws):
        try:
            return sorted({op["file"] for op in modbuild.load_jobs(ws)
                           if op.get("file")})
        except Exception:
            return []
    ta, tb = touched(a["workspace_a"]), touched(a["workspace_b"])
    return {"conflicts": sorted(set(ta) & set(tb))}


# ------------------------------------------------------------------ wire

def handle(req):
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": SERVER_INFO}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": [
            {"name": n, "description": d,
             "inputSchema": s} for n, (fn, s, d) in sorted(TOOLS.items())]}}
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        entry = TOOLS.get(name)
        if not entry:
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": f"unknown tool {name}"}],
                "isError": True}}
        fn, _schema, _desc = entry
        try:
            out = fn(args)
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": _j(out)}],
                "isError": False}}
        except ForgeError as e:
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text",
                             "text": _j({"error": e.code, "message": e.message,
                                         "hint": e.hint})}],
                "isError": True}}
        except Exception as e:  # noqa: BLE001 - wire errors must not kill server
            return {"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text",
                             "text": _j({"error": "SRF-INTERNAL",
                                         "message": str(e)})}],
                "isError": True}}
    if rid is None:
        return None  # notification (e.g. notifications/initialized)
    return {"jsonrpc": "2.0", "id": rid, "error":
            {"code": -32601, "message": f"method not found: {method}"}}


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError as e:
            sys.stdout.write(json.dumps(
                {"jsonrpc": "2.0", "id": None,
                 "error": {"code": -32700, "message": f"parse error: {e}"}}) + "\n")
            sys.stdout.flush()
            continue
        resp = handle(req)
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
