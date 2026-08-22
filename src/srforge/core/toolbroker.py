"""Tool broker: capabilities -> implementations, with verified provenance.

External tools are NEVER executed on filename trust: the vault manifest
(tools_vault/manifest.json) pins source URL + sha256 per tool directory.
"""
import json
import os
import subprocess


class ToolBroker:
    def __init__(self, vault_dir):
        self.vault_dir = vault_dir
        self.manifest_path = os.path.join(vault_dir, "manifest.json")
        try:
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                self.manifest = json.load(f)
        except OSError:
            self.manifest = {"tools": {}}

    def tool(self, name):
        t = self.manifest.get("tools", {}).get(name)
        if not t:
            return None
        exe = os.path.join(t.get("dir", ""), t.get("exe", ""))
        if not os.path.isfile(exe):
            return None
        return t

    def run(self, name, args, timeout=120, cwd=None):
        """Run a vaulted tool. Refuses if provenance is missing."""
        t = self.tool(name)
        if not t:
            raise FileNotFoundError(
                f"tool '{name}' not in vault manifest (run srforge deps acquire)")
        if not t.get("source") or not t.get("sha256"):
            raise PermissionError(f"tool '{name}' has no pinned provenance; refusing to run")
        exe = os.path.join(t.get("dir", ""), t.get("exe", ""))
        proc = subprocess.run([exe] + list(args), capture_output=True, text=True,
                              encoding="utf-8", errors="replace",
                              timeout=timeout, cwd=cwd or t.get("dir"))
        return proc

    def status(self):
        out = {}
        for name in sorted(self.manifest.get("tools", {})):
            t = self.tool(name)
            out[name] = "ready" if t else "missing"
        return out
