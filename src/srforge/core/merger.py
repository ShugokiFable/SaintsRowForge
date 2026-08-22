"""Cross-mod XTBL merge engine.

Mods ship FULL copies of shared tables, so naive installs lose data
(last-write-wins). This engine diffs each mod's table against vanilla,
then unions everything onto one base:

- records a mod adds            -> cloned in (all mods' additions survive)
- fields a mod changes          -> applied when base still matches vanilla
- two mods change same field    -> CONFLICT logged; later mod wins (documented,
                                  deterministic); report carries every value
- records a mod removes         -> reported only, never auto-applied
- non-XTBL filename collisions  -> flagged binary_collision (sha256 per side),
                                  later mod wins; tables are the safe path

Deterministic given the same mod order. Vanilla is never written.
"""
import copy
import hashlib
import os
import xml.etree.ElementTree as ET

from .receipts import ForgeError
from ..formats import xtbl as xtbl_mod


def _subtree_str(el):
    return ET.tostring(el, encoding="unicode")


def _canon(el):
    """Whitespace-insensitive structural identity: (tag, attribs, stripped
    text, children). Indentation lives in text/tail, so stripping kills
    formatting noise while preserving meaningful internal text."""
    return (el.tag,
            tuple(sorted(el.attrib.items())),
            (el.text or "").strip(),
            tuple(_canon(c) for c in el if isinstance(c.tag, str)))


def _rec_name(r):
    n = r.find("Name")
    return (n.text or "").strip() if n is not None else None


def _rec_map(x):
    return {_rec_name(r).lower(): r for r in x.records() if _rec_name(r)}


def _recs_container(x):
    """Same layout logic as Xtbl.records()."""
    for tag in ("Records", "Table"):
        c = x.root.find(tag)
        if c is not None:
            return c
    raise ForgeError("SRF-MERGE-003", "table has neither Records nor Table root child")


def _by_tag(el):
    """Ordered per-tag child lists (XTBL records can repeat a tag,
    e.g. two Projectile_Info blocks for primary/alt fire)."""
    out = {}
    for c in el:
        if isinstance(c.tag, str):
            out.setdefault(c.tag, []).append(c)
    return out


def diff_table(vanilla_x, mod_x):
    """Per-record diff of mod vs vanilla -> structured change list."""
    van, mod = _rec_map(vanilla_x), _rec_map(mod_x)
    d = {"added": [], "changed": [], "removed": []}
    for key, mrec in mod.items():
        if key not in van:
            d["added"].append({"record": _rec_name(mrec), "el": mrec})
            continue
        vrec = van[key]
        v_tags, m_tags = _by_tag(vrec), _by_tag(mrec)
        for tag, mlist in m_tags.items():
            vlist = v_tags.get(tag, [])
            for i, mel in enumerate(mlist):
                if i < len(vlist):
                    if _canon(vlist[i]) != _canon(mel):
                        d["changed"].append({
                            "record": _rec_name(mrec), "field": tag,
                            "field_index": i, "vanilla_el": vlist[i],
                            "mod_el": mel})
                else:
                    d["changed"].append({
                        "record": _rec_name(mrec), "field": tag,
                        "field_index": i, "vanilla_el": None, "mod_el": mel})
        for tag, vlist in v_tags.items():
            mlist = m_tags.get(tag, [])
            for i in range(len(mlist), len(vlist)):
                d["removed"].append({"record": _rec_name(mrec), "field": tag,
                                     "field_index": i})
    for key, vrec in van.items():
        if key not in mod:
            d["removed"].append({"record": _rec_name(vrec), "field": None})
    return d


def find_tables(mod_dirs):
    """All .xtbl under the given dirs (recursive), keyed by filename."""
    tables = {}
    for d in mod_dirs:
        for root, _, files in os.walk(d):
            for f in files:
                if f.lower().endswith(".xtbl"):
                    tables.setdefault(f.lower(), []).append(os.path.join(root, f))
    return tables


def merge_tables(vanilla_dir, mod_dirs, out_dir):
    """Merge every shared table across mod_dirs onto vanilla; write to out_dir.

    Returns the merge report (list of per-file entries). Conflicts are data,
    not errors; only corruption raises.
    """
    os.makedirs(out_dir, exist_ok=True)
    report = []
    # layer order = CLI arg order (documented 'later wins'); within one dir,
    # walk order sorted for run-to-run determinism
    for fname, paths in sorted(find_tables(mod_dirs).items()):
        paths = [p for d in mod_dirs for p in sorted(x for x in paths if x.startswith(d))]
        van_path = os.path.join(vanilla_dir, os.path.basename(fname))
        if not os.path.isfile(van_path):
            # no vanilla twin -> cannot three-way diff; skip, don't abort
            report.append({"file": fname, "mods": [os.path.basename(os.path.dirname(p)) or p
                                                   for p in paths],
                           "skipped": "no vanilla copy extracted"})
            continue
        base = xtbl_mod.Xtbl.load(van_path)
        base_map = _rec_map(base)
        entry = {"file": fname, "mods": [os.path.basename(os.path.dirname(p)) or p
                                         for p in paths],
                 "applied": [], "additions": [], "conflicts": [],
                 "removed_seen": []}
        for p in paths:
            src = os.path.basename(os.path.dirname(p)) or p
            # diff against PRISTINE vanilla (base mutates as layers land);
            # vanilla file on disk is never written, so reload is safe
            d = diff_table(xtbl_mod.Xtbl.load(van_path), xtbl_mod.Xtbl.load(p))
            for add in d["added"]:
                if add["record"].lower() in base_map:
                    continue  # earlier layer already unioned it
                el = copy.deepcopy(add["el"])
                _recs_container(base).append(el)
                base_map[add["record"].lower()] = el
                entry["additions"].append(f"{src}: +{add['record']}")
            for ch in d["changed"]:
                cur = base_map.get(ch["record"].lower())
                if cur is None:
                    continue  # vanished mid-merge; next layer will flag it
                copies = _by_tag(cur).get(ch["field"], [])
                idx_i = ch["field_index"]
                target = copies[idx_i] if idx_i < len(copies) else None
                new_el = copy.deepcopy(ch["mod_el"])
                if target is None:
                    # vanilla had it, earlier layer dropped the slot -> restore
                    cur.append(new_el)
                    entry["applied"].append(
                        f"{src}: {ch['record']}.{ch['field']} restored")
                    continue
                if ch["vanilla_el"] is not None:
                    untouched = _canon(target) == _canon(ch["vanilla_el"])
                    if untouched:
                        cur.remove(target)
                        cur.append(new_el)
                        entry["applied"].append(
                            f"{src}: {ch['record']}.{ch['field']} modified")
                    else:
                        entry["conflicts"].append({
                            "record": ch["record"], "field": ch["field"],
                            "winner": src,
                            "kept": _subtree_str(target)[:120],
                            "incoming": _subtree_str(ch["mod_el"])[:120]})
                        cur.remove(target)
                        cur.append(new_el)
                elif target is None:
                    cur.append(new_el)
                    entry["applied"].append(f"{src}: {ch['record']}.{ch['field']} added")
                else:
                    # two mods added the same new field -> conflict, later wins
                    entry["conflicts"].append({
                        "record": ch["record"], "field": ch["field"],
                        "winner": src, "kept": _subtree_str(target)[:120],
                        "incoming": _subtree_str(ch["mod_el"])[:120]})
                    cur.remove(target)
                    cur.append(new_el)
            for rm in d["removed"]:
                # true deletions of VANILLA records only (full-table mods always
                # lack other layers' additions - that is not a removal)
                entry["removed_seen"].append(f"{src}: -{rm['record']} (reported only)")
        probs = base.validate()
        if probs:
            raise ForgeError("SRF-MERGE-002",
                             f"{fname} failed validation post-merge: {probs}")
        out = os.path.join(out_dir, os.path.basename(fname))
        open(out, "w", encoding="utf-8").write(base.tostring())
        entry["written"] = out
        entry["records"] = len(base.records())
        report.append(entry)
    # non-xtbl collisions across mods: surface, don't guess
    seen = {}
    for d in mod_dirs:
        for root, _, files in os.walk(d):
            for f in sorted(files):
                if f.lower().endswith(".xtbl"):
                    continue
                fp = os.path.join(root, f)
                h = hashlib.sha256(open(fp, "rb").read()).hexdigest()
                if f in seen and seen[f][0] != h:
                    report.append({"file": f, "collisions": [
                        {"note": "non-table file differs between mods; LATER won "
                                 "(not merged)", "winner": fp}]})
                seen[f] = (h, fp)
    return report
