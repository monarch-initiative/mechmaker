"""Score each record for completeness, lowest first.

    python -m <slug>.compliance                 # every record, lowest score first
    python -m <slug>.compliance path/to/a.yaml  # what one record is missing
    python -m <slug>.compliance --json

The score is a rough guide to where curation effort pays. It counts what is
present, not whether it is right; review does that. Weights are in WEIGHTS;
change them to fit the domain.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .paths import IDENTITY_PREFIX, REPO_ROOT
from .validate import _evidence_items, iter_records, load

WEIGHTS = {
    "description": 10,
    "record_term": 15,
    "descriptors_bound": 25,
    "evidence_present": 20,
    "evidence_quoted": 20,
    "status": 10,
}


def _descriptors(obj):
    if isinstance(obj, dict):
        if "preferred_term" in obj:
            yield obj
        for v in obj.values():
            yield from _descriptors(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _descriptors(v)


def score(data: dict) -> tuple[float, list[str]]:
    missing: list[str] = []
    parts: dict[str, float] = {}
    if not data.get("description"):
        parts["description"] = 0.0
        missing.append("no description")
    elif not data.get("description_evidence"):
        parts["description"] = 0.5
        missing.append("description has no description_evidence")
    else:
        parts["description"] = 1.0
    # Only a record keyed by an identity-ontology term must name it in record_term.
    # A minted id may have no term to name, so it gets full credit here.
    keyed = bool(IDENTITY_PREFIX) and str(data.get("id", "")).startswith(f"{IDENTITY_PREFIX}:")
    parts["record_term"] = 1.0 if (not keyed or data.get("record_term")) else 0.0
    if not parts["record_term"]:
        missing.append("no record_term")
    descs = list(_descriptors(data))
    unbound = [d.get("preferred_term") for d in descs if not d.get("term")]
    parts["descriptors_bound"] = (1 - len(unbound) / len(descs)) if descs else 0.0
    if not descs:
        missing.append("no descriptors in any section")
    elif unbound:
        names = ", ".join(map(str, unbound[:5]))
        missing.append(f"{len(unbound)} of {len(descs)} descriptors unbound: {names}")
    items = [ev for _, ev in _evidence_items(data)]
    parts["evidence_present"] = min(1.0, len(items) / 3)
    if not items:
        missing.append("no evidence")
    quoted = [ev for ev in items if ev.get("snippet")]
    parts["evidence_quoted"] = (len(quoted) / len(items)) if items else 0.0
    if items and len(quoted) < len(items):
        missing.append(f"{len(items) - len(quoted)} of {len(items)} evidence items have no snippet")
    parts["status"] = 1.0 if data.get("status") in ("PROPOSED", "REVIEWED") else 0.0
    if not parts["status"]:
        missing.append(f"status is {data.get('status', 'unset')}")
    total = sum(WEIGHTS[k] * parts[k] for k in WEIGHTS)
    return round(total, 1), missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    rows = []
    for p in args.paths or iter_records():
        data = load(p) or {}
        if not isinstance(data, dict):  # not a record; just validate reports it
            continue
        s, missing = score(data)
        full = Path(p).resolve()
        shown = full.relative_to(REPO_ROOT) if full.is_relative_to(REPO_ROOT) else full
        rows.append({"path": str(shown), "score": s, "missing": missing})
    rows.sort(key=lambda r: (r["score"], r["path"]))
    if args.json:
        print(json.dumps(rows, indent=2))
    elif len(rows) == 1 and args.paths:
        r = rows[0]
        print(f"{r['path']}: {r['score']}/100")
        for m in r["missing"] or ["nothing obvious is missing"]:
            print(f"  - {m}")
    else:
        for r in rows:
            print(f"{r['score']:6.1f}  {r['path']}  ({'; '.join(r['missing'][:2]) or 'complete'})")
        print(f"{len(rows)} record(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
