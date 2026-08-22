"""Workspace + transaction helpers. Vanilla game dirs are NEVER written."""
import json
import os

from .receipts import ForgeError, sha256_file


WORKSPACE_DIRS = ["source", "extracted", "working", "generated",
                  "package", "logs", "receipts", "tests", "release"]


def new_workspace(root, name, game):
    ws = os.path.abspath(os.path.join(root, name))
    if os.path.exists(ws):
        raise ForgeError("SRF-WS-001", f"workspace '{name}' already exists at {ws}")
    os.makedirs(ws)
    for d in WORKSPACE_DIRS:
        os.makedirs(os.path.join(ws, d))
    project = {
        "name": name,
        "game": game,
        "created": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"),
        "operations": [],
        "status": "new",
    }
    with open(os.path.join(ws, "project.json"), "w", encoding="utf-8") as f:
        json.dump(project, f, indent=2)
    return ws


def load_workspace(path):
    pj = os.path.join(path, "project.json")
    if not os.path.isfile(pj):
        raise ForgeError("SRF-WS-002", f"no project.json under {path}",
                         hint="run: srforge project new <name> --game sriv")
    with open(pj, "r", encoding="utf-8") as f:
        return json.load(f)


def save_workspace_meta(path, meta):
    meta["modified"] = __import__("time").strftime("%Y-%m-%dT%H:%M:%S")
    with open(os.path.join(path, "project.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)


def snapshot_files(paths, snap_dir):
    """Hash + copy originals into workspace before any write. Returns manifest."""
    import shutil
    os.makedirs(snap_dir, exist_ok=True)
    entries = {}
    for src in paths:
        h = sha256_file(src)
        dst = os.path.join(snap_dir, os.path.basename(src))
        if not os.path.exists(dst):  # first snapshot wins; never overwrite
            shutil.copy2(src, dst)
        entries[src] = {"sha256": h, "snapshot": dst}
    return entries


def verify_unchanged(manifest):
    """Every snapshotted file must still hash identically."""
    changed = [p for p, e in manifest.items() if sha256_file(p) != e["sha256"]]
    return changed
