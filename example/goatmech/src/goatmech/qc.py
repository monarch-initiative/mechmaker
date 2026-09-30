"""The one executable definition of green.

    python -m <slug>.qc            # offline gates; what CI blocks on
    python -m <slug>.qc --network  # plus term and reference checks for every record

A passing local run and a passing CI run mean the same thing, because CI runs
this script and nothing else.
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from .paths import PACKAGE_DIR, REPO_ROOT

OFFLINE = [
    ("lint", ["just", "lint"]),
    ("records: closed schema", ["just", "validate-all"]),
    ("history", ["just", "validate-history"]),
    ("tests", ["just", "test", "-q"]),
]
NETWORK = [
    ("records: ontology terms", ["just", "validate-terms-all"]),
    ("records: verbatim quotes", ["just", "validate-references-all"]),
]


def case_collisions() -> list[str]:
    """Tracked paths that differ only by case break checkouts on macOS and Windows."""
    out = subprocess.run(["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True)
    seen: dict[str, str] = {}
    clashes = []
    for path in out.stdout.splitlines():
        key = path.lower()
        if key in seen and seen[key] != path:
            clashes.append(f"{seen[key]} <-> {path}")
        seen.setdefault(key, path)
    return clashes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--network", action="store_true", help="also run the network gates")
    args = parser.parse_args(argv)

    steps = list(OFFLINE)
    if (PACKAGE_DIR / "render.py").exists():
        steps.append(("site is current", ["just", "render-check"]))
    steps.append(("docs build", ["just", "docs-build"]))
    if args.network:
        steps += NETWORK

    failed = []
    clashes = case_collisions()
    print("\n=== paths differ by more than case", flush=True)
    for c in clashes:
        print(f"ERROR case-only difference: {c}")
    if clashes:
        failed.append("path case")
    for label, cmd in steps:
        print(f"\n=== {label}: {' '.join(cmd)}", flush=True)
        if subprocess.run(cmd, cwd=REPO_ROOT).returncode != 0:
            failed.append(label)
    print()
    if failed:
        print("QC FAILED: " + ", ".join(failed))
        return 1
    print(f"QC passed: {len(steps)} gate(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
