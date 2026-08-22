# Saints Row Forge — External Knowledge Layer

This folder is an **evidence/reference layer**, not a claim that the Forge implements every format listed here.

Before implementing or debugging Saints Row: The Third / Saints Row IV behavior:

1. Query the Forge's actual capability matrix first (`sr_capabilities` / `srforge doctor`).
2. Search `knowledge/` for format/load-order/tool notes.
3. Use `knowledge/SOURCES.json` to find the strongest upstream source for the question.
4. Prefer runtime evidence and vanilla-file round trips over prose documentation when they disagree.
5. Never report a format as supported merely because an external tool/source can handle it. Add an adapter + tests + receipt first.
6. Never execute a downloaded third-party binary until it passes the Forge provenance/import gate.

Fast local search:

```powershell
python scripts\KnowledgeSearch.py "cpeg texture cruncher"
python scripts\KnowledgeSearch.py "zone czn gzn"
python scripts\KnowledgeSearch.py "lua LOCAL_PLAYER"
```

Optional upstream checkout:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\Fetch-Upstream-References.ps1
```
