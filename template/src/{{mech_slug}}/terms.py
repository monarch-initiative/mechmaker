"""Term lookups through the adapter conf/oak_config.yaml gives each prefix.

    python -m <slug>.terms ancestors VT:0011348          # is-a ancestors
    python -m <slug>.terms ancestors GO:0015979 --part-of
    python -m <slug>.terms check VT:0011348 --root VT:0000001
    python -m <slug>.terms adapter VT                    # the adapter VT uses

The term checks use the same adapters, so these answer the question the
checks ask. An ols: adapter goes through the OLS API (ols.py). Every other
adapter OAK accepts goes through oaklib: sqlite:obo:<name>, bioportal:<name>
(with BIOPORTAL_API_KEY set), or a file in the repository such as
simpleobo:ontologies/<file>.obo.
"""

from __future__ import annotations

import argparse
import sys

import yaml

from . import ols
from .paths import REPO_ROOT

OAK_CONFIG = REPO_ROOT / "conf" / "oak_config.yaml"


def adapter_for(prefix: str) -> str:
    """The full adapter string for a prefix, with the per-prefix shorthands filled in."""
    adapters = (yaml.safe_load(OAK_CONFIG.read_text()) or {}).get("ontology_adapters") or {}
    if prefix not in adapters:
        raise SystemExit(f"{prefix} is not in conf/oak_config.yaml. Add it, with its adapter, "
                         "or its terms are never checked.")
    value = str(adapters[prefix] or "").strip()
    if not value:
        raise SystemExit(f"{prefix} is skipped on purpose in conf/oak_config.yaml (adapter \"\").")
    if value in ("ols", "ols:"):
        return f"ols:{prefix.lower()}"
    if value == "sqlite:obo:":
        return f"sqlite:obo:{prefix.lower()}"
    return value


def ancestors(curie: str, part_of: bool = False) -> list[tuple[str, str | None]]:
    adapter = adapter_for(curie.split(":", 1)[0])
    if adapter.startswith("ols:"):
        return ols.ancestors(curie, adapter.removeprefix("ols:"), part_of)
    from oaklib import get_adapter
    from oaklib.datamodels.vocabulary import IS_A, PART_OF

    oak = get_adapter(adapter)
    predicates = [IS_A, PART_OF] if part_of else [IS_A]
    return [(a, oak.label(a)) for a in oak.ancestors(curie, predicates=predicates, reflexive=False)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ancestors", help="list ancestors of a term")
    a.add_argument("curie")
    a.add_argument("--part-of", action="store_true", help="include part-of ancestors")
    c = sub.add_parser("check", help="is ROOT an is-a ancestor of CURIE (or CURIE itself)?")
    c.add_argument("curie")
    c.add_argument("--root", required=True)
    d = sub.add_parser("adapter", help="print the adapter a prefix uses")
    d.add_argument("prefix")
    args = parser.parse_args(argv)

    if args.cmd == "adapter":
        print(adapter_for(args.prefix))
        return 0
    if args.cmd == "ancestors":
        for cid, label in sorted(ancestors(args.curie, args.part_of), key=lambda t: str(t[0])):
            print(f"{cid}\t{label or ''}")
        return 0
    found = args.curie == args.root or args.root in {cid for cid, _ in ancestors(args.curie)}
    print(f"{args.root} {'is' if found else 'is NOT'} an is-a ancestor of {args.curie}")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
