"""Vanilla index: find which VPP contains a logical file, honoring precedence.

Precedence (verified from community-documented SRTT/SRIV loading):
loose files > patch_compressed.vpp_pc > patch_uncompressed.vpp_pc > base vpps.
"""
import os
import struct

from .receipts import ForgeError
from ..formats import vpp, vpp06


BASE_VPPS_SRTT = ["tables.vpp_pc", "misc.vpp_pc", "streams.vpp_pc"]
PATCHES = [("patch_compressed", True), ("patch_uncompressed", False)]


class GameIndex:
    def __init__(self, install_path, game):
        self.install = install_path
        self.game = game
        self._cache = {}  # logical name -> {vpp, order}
        self.scan()

    def scan(self):
        self.entries = []   # (logical_name, container_path, priority)
        PRIORITY_LOOSE, PRIORITY_PATCH, PRIORITY_BASE = 3, 2, 1
        # loose files: install root + packfiles/ (real installs keep VPPs there)
        for root, _dirs, files in os.walk(self.install):
            for f in files:
                self.entries.append((f.lower(), os.path.join(root, f),
                                     PRIORITY_LOOSE))
        ordered_vpps = []
        search_dirs = [self.install,
                       os.path.join(self.install, "packfiles"),
                       os.path.join(self.install, "packfiles", "pc"),
                       os.path.join(self.install, "packfiles", "pc", "cache")]
        for base in search_dirs:
            if not os.path.isdir(base):
                continue
            for pname, _c in PATCHES:
                p = os.path.join(base, pname + ".vpp_pc")
                if os.path.isfile(p):
                    ordered_vpps.append((p, PRIORITY_PATCH))
        for base in search_dirs:
            if not os.path.isdir(base):
                continue
            for f in sorted(os.listdir(base)):
                fp = os.path.join(base, f)
                if (f.lower().endswith(".vpp_pc") and not f.startswith("patch_")
                        and os.path.isfile(fp)):
                    ordered_vpps.append((fp, PRIORITY_BASE))
        skipped = []
        for vp, prio in ordered_vpps:
            try:
                with open(vp, "rb") as f:
                    head = f.read(8)
                if len(head) < 8 or head[:4] != b"\xce\x0a\x89\x51":
                    raise ValueError("not a Volition packfile")
                ver = struct.unpack_from("<I", head, 4)[0]
                if ver == 0x06:
                    names = [e.name for e in vpp06.Vpp06File.list_entries(vp)]
                elif ver == 0x0A:
                    names = [e.name for e in vpp.Packfile.list_entries(vp)]
                else:
                    raise ValueError(f"unsupported vpp version {ver:#x}")
            except Exception as e:
                # not every *.vpp_pc in an install dir is a v0x0A game archive
                # (launcher.vpp_pc etc.) - skip and surface via doctor
                skipped.append({"container": os.path.basename(vp), "error": str(e)})
                continue
            for nm in names:
                self.entries.append((nm.lower(), vp, prio))
        self.skipped_containers = skipped
        # resolve winner per logical name: highest priority wins
        winners = {}
        for name, cont, o in self.entries:
            cur = winners.get(name)
            if cur is None or o > cur[2]:
                winners[name] = (name, cont, o)
        self.resolved = winners

    def find(self, logical_name):
        hit = self.resolved.get(logical_name.lower())
        if not hit:
            raise ForgeError("SRF-IDX-001",
                             f"'{logical_name}' not found in any known vanilla container "
                             f"or loose file under {self.install}",
                             hint="run: srforge doctor --game srtt --json")
        return {"logical": hit[0], "container": hit[1], "precedence_order": hit[2],
                "kind": "loose" if hit[2] == -1 else "vpp"}

    def origin(self, logical_name):
        """All containers holding this name, best first."""
        hits = [e for e in self.entries if e[0] == logical_name.lower()]
        hits.sort(key=lambda e: -e[2])
        return [{"container": c, "precedence_order": o,
                 "wins": o == self.resolved[logical_name.lower()][2]} for n, c, o in hits]
