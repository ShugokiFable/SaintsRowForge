"""Core types: errors, receipts, evidence levels."""
import json
import os
import time


class ForgeError(Exception):
    def __init__(self, code, message, hint=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint


class ExitCode:
    OK = 0
    GENERIC = 1
    VALIDATION = 2
    NOT_FOUND = 3
    DEPENDENCY = 4
    REFUSED = 5


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def new_receipt(game, operation, workspace=None):
    return {
        "game": game,
        "operation": operation,
        "workspace": str(workspace) if workspace else None,
        "timestamp": now_iso(),
        "inputs": [],
        "tools": [],
        "tool_versions": {},
        "input_hashes": {},
        "outputs": [],
        "output_hashes": {},
        "checks": [],
        "warnings": [],
        "requires_runtime_test": True,
        "status": "generated",
    }


def finish_receipt(receipt, status):
    receipt["status"] = status
    return receipt


def save_receipt(receipt, receipts_dir):
    os.makedirs(receipts_dir, exist_ok=True)
    name = f"{receipt['operation'].replace('.', '-').replace('/', '-')}-{time.strftime('%Y%m%d-%H%M%S')}.json"
    path = os.path.join(receipts_dir, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(receipt, f, indent=2)
    return path


def check(receipt, name, ok, detail="", evidence=None):
    receipt["checks"].append({
        "check": name,
        "result": "pass" if ok else "fail",
        "detail": detail,
        "evidence": evidence or ("reopened" if ok else None),
    })
    return ok
