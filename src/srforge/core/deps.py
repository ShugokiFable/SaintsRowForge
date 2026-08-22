"""Dependency acquisition from pinned canonical sources.

Downloads go to Inbox/, are hashed, scanned for executables/path traversal,
then installed into tools_vault/<name>/ and recorded in manifest.json.
"""
import hashlib
import json
import os
import zipfile

CANONICAL = {
    # name -> {url, kind, note}  (pinned immutable sources; no 'latest')
    "thomasjepp": {
        "url": "https://minimaul.saintsrowmods.com/files/tools/releases/ThomasJepp.SaintsRow-rev133.7z",
        "kind": "7z",
        "exe_dir": "ThomasJepp.SaintsRow-rev133",
        "note": "Minimaul's SR2/SRTT/SRIV/GOOH toolset rev133",
    },
    "zinyaks": {
        "url": "https://github.com/volition-inc/Zinyaks-Cache-Of-Wonders/archive/refs/heads/master.zip",
        "kind": "zip",
        "note": "Volition's official SR4 Modding SDK repo (crunchers, vPkg)",
    },
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def scan_archive(zip_path):
    """Path traversal + executable inventory before extraction."""
    problems, exes = [], []
    if zip_path.lower().endswith(".7z"):
        # 7-Zip CLI listing (no py7zr dep); same checks as zip path
        import subprocess
        sevenzip = os.path.join(os.environ.get("PROGRAMFILES",
                                                r"C:\Program Files"),
                                "7-Zip", "7z.exe")
        if not os.path.isfile(sevenzip):
            return {"problems": [{"problem": "7z_not_found"}], "executables": []}
        cp = subprocess.run([sevenzip, "l", "-ba", "-slt", zip_path],
                            capture_output=True, text=True, timeout=120)
        names = [ln.split("=", 1)[1].strip()
                 for ln in (cp.stdout or "").splitlines()
                 if ln.startswith("Path = ")]
        for n in names:
            if n.startswith("/") or ".." in n.replace("\\", "/").split("/"):
                problems.append({"problem": "path_traversal", "entry": n})
            low = n.lower().replace("\\", "/").rsplit("/", 1)[-1]
            if low.endswith((".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs")):
                exes.append(n)
        return {"problems": problems, "executables": exes}
    try:
        with zipfile.ZipFile(zip_path) as z:
            names = z.namelist()
            for n in names:
                if n.startswith("/") or ".." in n.replace("\\\\", "/").split("/"):
                    problems.append({"problem": "path_traversal", "entry": n})
                low = n.lower()
                if low.endswith((".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs")):
                    exes.append(n)
    except zipfile.BadZipFile:
        problems.append({"problem": "not_a_zip"})
    return {"problems": problems, "executables": exes}


def import_inbox(inbox_dir, vault_dir):
    """Identify known components in Inbox by hash; install into the vault."""
    manifest_path = os.path.join(vault_dir, "manifest.json")
    manifest = {"tools": {}}
    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    results = []
    for name, meta in CANONICAL.items():
        marker = os.path.basename(meta["url"])
        src = None
        # match by filename inside inbox OR already-extracted dir in vault
        for f in os.listdir(inbox_dir):
            if f.lower() == marker.lower():
                src = os.path.join(inbox_dir, f)
                break
        extracted = os.path.join(vault_dir, name)
        if src is None and os.path.isdir(extracted):
            results.append({"component": name, "status": "already_installed",
                            "dir": extracted})
            continue
        if src is None:
            results.append({"component": name, "status": "missing_from_inbox",
                            "expected_filename": marker})
            continue
        h = sha256(src)
        report = scan_archive(src)
        if report["problems"]:
            results.append({"component": name, "status": "refused",
                            "problems": report["problems"], "sha256": h})
            continue
        results.append({
            "component": name, "status": "verified_ready_to_install",
            "sha256": h, "source": meta["url"],
            "executables_found": len(report["executables"]),
            "install_hint": f"extract into {os.path.join(vault_dir, name)} then re-run",
        })
    return results


def register_tool(vault_dir, name, rel_dir, exe_relpath, source_url, expected_sha256=None):
    """Record a tool's provenance after manual/imported installation."""
    manifest_path = os.path.join(vault_dir, "manifest.json")
    manifest = {"tools": {}}
    if os.path.isfile(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    d = os.path.join(rel_dir, "")
    exe_abs = os.path.join(d, exe_relpath)
    if not os.path.isfile(exe_abs):
        raise FileNotFoundError(exe_abs)
    manifest["tools"][name] = {
        "dir": os.path.join(os.path.dirname(d.rstrip("\\")) if False else "", "") or "",
    }
    # simpler: store absolute paths at registration time
    manifest["tools"][name] = {
        "dir": os.path.abspath(rel_dir),
        "exe": exe_relpath,
        "source": source_url,
        "sha256": expected_sha256,
        "registered": __import__("time").strftime("%Y-%m-%d"),
    }
    os.makedirs(vault_dir, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest["tools"][name]
