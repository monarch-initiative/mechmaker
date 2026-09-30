"""Corpus statistics, counted from the records themselves.

    python -m <slug>.report [--json]

Quote numbers from this, never from prose.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from .paths import MECH_NAME, RECORDS_DIR, REPO_ROOT
from .validate import iter_records, load


def _walk(obj, counts: Counter) -> None:
    if isinstance(obj, dict):
        if "reference" in obj and "supports" in obj:
            counts["evidence_items"] += 1
            if obj.get("snippet"):
                counts["evidence_with_snippet"] += 1
        if "preferred_term" in obj:
            counts["descriptors"] += 1
            if obj.get("term"):
                counts["descriptors_bound"] += 1
        for v in obj.values():
            _walk(v, counts)
    elif isinstance(obj, list):
        for v in obj:
            _walk(v, counts)


def compute() -> dict:
    paths = iter_records()
    status: Counter = Counter()
    counts: Counter = Counter()
    for p in paths:
        data = load(p) or {}
        status[data.get("status", "UNSET")] += 1
        counts["mechanism_nodes"] += len(data.get("mechanisms") or [])
        counts["discussions"] += len(data.get("discussions") or [])
        _walk(data, counts)
    return {
        "mech": MECH_NAME,
        "records_dir": str(RECORDS_DIR.relative_to(REPO_ROOT)),
        "records": len(paths),
        "by_status": dict(sorted(status.items())),
        **{k: counts[k] for k in sorted(counts)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    stats = compute()
    if args.json:
        print(json.dumps(stats, indent=2))
    else:
        for k, v in stats.items():
            print(f"{k:24} {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
