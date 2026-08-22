#!/usr/bin/env python3
"""Zero-dependency local search over SaintsRowForge/knowledge."""
from pathlib import Path
import json, re, sys

ROOT = Path(__file__).resolve().parents[1]
KNOW = ROOT / "knowledge"
q = " ".join(sys.argv[1:]).strip().lower()
if not q:
    print("Usage: python scripts\\KnowledgeSearch.py <query>")
    raise SystemExit(2)
terms = [t for t in re.findall(r"[a-z0-9_+.-]+", q) if len(t) > 1]
rows = []
for p in KNOW.glob("*.md"):
    text = p.read_text(encoding="utf-8", errors="replace")
    low = text.lower()
    score = sum(low.count(t) * (4 if t in p.name.lower() else 1) for t in terms)
    if score:
        snippets = []
        for line in text.splitlines():
            ll = line.lower()
            if any(t in ll for t in terms):
                snippets.append(line.strip())
            if len(snippets) >= 4:
                break
        rows.append((score, p.name, snippets))

src = KNOW / "SOURCES.json"
if src.exists():
    data = json.loads(src.read_text(encoding="utf-8"))
    for s in data.get("sources", []):
        blob = json.dumps(s).lower()
        score = sum(blob.count(t) for t in terms)
        if score:
            rows.append((score, "SOURCE:" + s.get("id", "?"), [s.get("url", ""), ", ".join(s.get("use_for", []))]))

for score, name, snippets in sorted(rows, reverse=True)[:20]:
    print(f"[{score:3}] {name}")
    for s in snippets:
        print("      " + s[:300])
if not rows:
    print("No local knowledge hit. Use knowledge/SOURCES.json for upstream research.")
