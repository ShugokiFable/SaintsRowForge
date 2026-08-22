"""Mod build engine: extract -> structured patch -> validate -> rebuild ->
ASM update -> reopen-verify -> semantic vanilla diff -> receipt.

Transactional: any failed check aborts before release artifacts are made,
and vanilla sources are never written.
"""
import json
import os
import shutil
import time

from .receipts import ForgeError, new_receipt, sha256_file
from ..formats import vpp, xtbl as xtbl_mod


def load_jobs(ws):
    """jobs/*.json - each a list of operations (see docs/CLI.md)."""
    jobs_dir = os.path.join(ws, "source", "jobs")
    if not os.path.isdir(jobs_dir):
        return []
    out = []
    for f in sorted(os.listdir(jobs_dir)):
        if f.endswith(".json"):
            with open(os.path.join(jobs_dir, f), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, list):
                out.extend([{"__jobfile": f, **op} if isinstance(op, dict) else op for op in data])
            elif isinstance(data, dict) and isinstance(data.get("operations"), list):
                out.extend([{"__jobfile": f, **op} for op in data["operations"]])
            elif isinstance(data, dict):
                out.append({"__jobfile": f, **data})
    return out


def _resolve_vanilla(index, logical):
    return index.find(logical)


def extract_to(index, logical, dest_dir):
    """Extract one logical file from its winning container into dest_dir."""
    hit = index.find(logical)
    os.makedirs(dest_dir, exist_ok=True)
    dst = os.path.join(dest_dir, hit["logical"])
    if hit["kind"] == "loose":
        shutil.copy2(hit["container"], dst)
        return {"logical": hit["logical"], "source": "loose", "path": dst}
    pf = vpp.Packfile.from_file(hit["container"])
    entry = pf.get(hit["logical"])
    with open(dst, "wb") as f:
        f.write(entry)
    return {"logical": hit["logical"], "source": os.path.basename(hit["container"]),
            "precedence_order": hit["precedence_order"], "path": dst}


def apply_ops(ops, extracted_dir, working_dir):
    """Apply XTBL ops to extracted files; returns per-op results."""
    os.makedirs(working_dir, exist_ok=True)
    results = []
    # group ops by file
    by_file = {}
    for op in ops:
        fname = op.get("file")
        if not fname:
            raise ForgeError("SRF-JOB-001", f"job missing 'file': {op}")
        by_file.setdefault(fname.lower(), []).append(op)
    for fname, fops in by_file.items():
        src = os.path.join(extracted_dir, fname)
        if not os.path.isfile(src):
            raise ForgeError("SRF-JOB-002",
                             f"'{fname}' was not extracted; add an extract step or check spelling")
        dst = os.path.join(working_dir, fname)
        shutil.copy2(src, dst)  # patch on top of vanilla copy
        x = xtbl_mod.Xtbl.load(dst)
        for op in fops:
            kind = op.get("operation", "").lower()
            rec = op.get("record")
            field = op.get("field")
            try:
                old = None
                if field and op.get("operation") not in ("clone_record",):
                    try:
                        old = x.get_field(rec, field).text if rec else None
                    except KeyError:
                        pass
                if kind == "multiply":
                    x.multiply_field(rec, field, float(op["value"]))
                    results.append({"op": op, "old": str(old),
                                    "new": x.get_field(rec, field).text})
                elif kind == "set":
                    x.set_field(rec, field, op["value"])
                    results.append({"op": op, "old": old,
                                    "new": x.get_field(rec, field).text})
                elif kind == "add":
                    cur = float(x.get_field(rec, field).text)
                    x.set_field(rec, field, cur + float(op["value"]))
                    results.append({"op": op, "old": str(cur),
                                    "new": x.get_field(rec, field).text})
                elif kind == "clone_record":
                    ok = x.clone_record(rec, op["value"] if isinstance(op["value"], str) else op.get("new_name"))
                    if not ok:
                        raise ForgeError("SRF-JOB-003",
                                         f"cannot clone '{rec}' -> '{op['value']}': target exists")
                    results.append({"op": op, "old": None, "new": op["value"]})
                else:
                    raise ForgeError("SRF-JOB-004", f"unknown operation {kind!r}")
            except KeyError as e:
                raise ForgeError("SRF-JOB-005", f"{fname}: {e}", hint=json.dumps(op))
            except ValueError as e:
                raise ForgeError("SRF-JOB-006", f"{fname}: {e}", hint=json.dumps(op))
        probs = x.validate()
        if probs:
            raise ForgeError("SRF-XTBL-E99", f"{fname} failed validation after patch: {probs}",
                             hint="no files were changed outside the workspace")
        open(dst, "w", encoding="utf-8").write(x.tostring())
    return results


def build_package(game, working_dir, out_path, asm_update=None, extra_files=None):
    """Build vpp/str2 via native writer; optionally update an ASM.

    Returns receipt-check info. Reopens the result to verify.
    """
    files = {}
    for root, _dirs, fs in os.walk(working_dir):
        for f in fs:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, working_dir)
            with open(full, "rb") as fh:
                files[rel.replace("\\\\", "\\")] = fh.read()
    if extra_files:
        for rel, full in extra_files.items():
            files[rel] = full
    is_str2 = out_path.lower().endswith(".str2_pc")
    vpp.write_packfile(out_path, files, condensed=is_str2, compressed=is_str2)

    asm_note = None
    if is_str2 and asm_update:
        from ..formats import asm as asm_mod
        af = asm_mod.AsmFile.parse(open(asm_update, "rb").read())
        ok = af.update_container_sizes(out_path)
        if not ok:
            raise ForgeError(
                "SRF-ASM-004",
                f"Cannot rebuild package: '{os.path.basename(asm_update)}' has no "
                f"container named '{os.path.splitext(os.path.basename(out_path))[0]}'",
                hint="check which asm_pc owns this str2 (srforge asset related)")
        open(asm_update, "wb").write(af.to_bytes())
        asm_note = "updated"

    # reopen verify - a zero exit code is NOT proof of success
    pf = vpp.Packfile.from_file(out_path)
    names = sorted(e.name for e in pf.files())
    expected = sorted(files.keys())
    if names != expected:
        raise ForgeError("SRF-PKG-002",
                         f"rebuilt package contents mismatch: {names} != {expected}")
    return {"entries": names, "asm": asm_note,
            "sha256": sha256_file(out_path), "size": os.path.getsize(out_path)}


def semantic_diff_report(extracted_dir, working_dir):
    """Compare every patched file against its vanilla twin."""
    changes = []
    for root, _dirs, fs in os.walk(working_dir):
        for f in fs:
            work = os.path.join(root, f)
            van = os.path.join(extracted_dir, f)
            if not os.path.isfile(van):
                changes.append({"type": "file_added", "file": f})
                continue
            if f.lower().endswith(".xtbl"):
                a = xtbl_mod.Xtbl.load(van)
                b = xtbl_mod.Xtbl.load(work)
                changes.extend(xtbl_mod.semantic_diff(a, b))
            else:
                if sha256_file(van) != sha256_file(work):
                    changes.append({"type": "file_changed_binary", "file": f})
    return changes


def guard_scope(ops, changes):
    """Fail the build if more RECORDS changed than jobs requested."""
    want_records = set()
    for op in ops:
        if op.get("operation") == "clone_record":
            want_records.add(str(op.get("value", "")).lower())
        elif op.get("record"):
            want_records.add(str(op["record"]).lower())
    got_records = {c["record"].lower() for c in changes if c.get("type", "").startswith("record_")}
    got_records |= {c["record"].lower() for c in changes if c.get("type") == "field_changed"}
    unexpected = got_records - want_records
    if unexpected:
        raise ForgeError(
            "SRF-DIFF-001",
            f"unexpected records changed: {sorted(unexpected)[:10]} "
            f"({len(got_records)} touched vs {len(want_records)} requested)",
            hint="this usually means a job targeted the wrong file; build aborted")
    return True
