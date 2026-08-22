"""Game discovery: Steam libraries, registry, common paths. No hardcoded users."""
import json
import os
import re


def _steam_libraries():
    libs = []
    drives = []
    for c in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        p = f"{c}:\\"
        if os.path.isdir(p):
            drives.append(p)
    candidates = []
    for d in drives:
        candidates += [
            os.path.join(d, "Program Files (x86)", "Steam", "config", "libraryfolders.vdf"),
            os.path.join(d, "Program Files", "Steam", "config", "libraryfolders.vdf"),
            os.path.join(d, "Steam", "config", "libraryfolders.vdf"),
        ]
    # env override
    for env in ("STEAM_PATH", "STEAM_LIBRARY"):
        v = os.environ.get(env)
        if v and os.path.isdir(v):
            libs.append(v)
    for cand in candidates:
        try:
            text = open(cand, "r", encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        root = os.path.dirname(os.path.dirname(cand))  # .../Steam
        libs.append(root)
        for m in re.finditer(r'"path"\s+"([^"]+)"', text):
            libs.append(m.group(1).replace("\\\\", "\\"))
    seen, out = set(), []
    for l in libs:
        k = os.path.normcase(os.path.normpath(l))
        if k not in seen and os.path.isdir(l):
            seen.add(k)
            out.append(l)
    return out


GAME_IDS = {
    "srtt": ("55230", ["Saints Row The Third", "SaintsRowTheThird"]),
    "sriv": ("206420", ["Saints Row IV"])
}


def find_game(game_key, extra_paths=None):
    """Returns dict {game, install_path, source} or None."""
    appid = GAME_IDS[game_key][0]
    names = GAME_IDS[game_key][1]
    for lib in _steam_libraries():
        base = os.path.join(lib, "steamapps", "common")
        for name in names:
            path = os.path.join(base, name)
            if os.path.isdir(path):
                return {"game": game_key, "install_path": path, "source": "steam"}
    if extra_paths:
        for p in extra_paths:
            if os.path.isdir(p):
                return {"game": game_key, "install_path": p, "source": "configured"}
    return None


def detect_games(extra_paths=None):
    out = {}
    for g in GAME_IDS:
        r = find_game(g, extra_paths)
        if r:
            out[g] = r
    return out
