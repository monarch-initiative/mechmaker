"""Term lookups through the adapter conf/oak_config.yaml gives each prefix.

    python -m <slug>.terms ancestors VT:0011348          # is-a ancestors
    python -m <slug>.terms ancestors GO:0015979 --part-of
    python -m <slug>.terms check VT:0011348 --root VT:0000001
    python -m <slug>.terms parents VBO:0009093           # direct is-a parents
    python -m <slug>.terms check-identity [FILE ...]     # record ids, by the identity enum's rule
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
from pathlib import Path

import yaml

from . import ols
from .oak_compat import patch
from .paths import REPO_ROOT

OAK_CONFIG = REPO_ROOT / "conf" / "oak_config.yaml"


def adapter_for(prefix: str) -> str:
    """The full adapter string for a prefix, with the per-prefix shorthands filled in."""
    adapters = (yaml.safe_load(OAK_CONFIG.read_text(encoding="utf-8")) or {}).get("ontology_adapters") or {}
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

    patch()  # BioPortal: see oak_compat
    oak = get_adapter(adapter)
    if part_of and adapter.startswith("bioportal:"):
        print("BioPortal gives is-a ancestors only; part-of is not available.", file=sys.stderr)
    predicates = [IS_A, PART_OF] if part_of else [IS_A]
    return [(a, oak.label(a)) for a in oak.ancestors(curie, predicates=predicates, reflexive=False)]


def parents(curie: str) -> list[tuple[str, str | None]]:
    """Direct is-a parents."""
    adapter = adapter_for(curie.split(":", 1)[0])
    if adapter.startswith("ols:"):
        return ols.parents(curie, adapter.removeprefix("ols:"))
    from oaklib import get_adapter
    from oaklib.datamodels.vocabulary import IS_A

    patch()
    oak = get_adapter(adapter)
    return [(o, oak.label(o)) for _, _, o in oak.relationships([curie], predicates=[IS_A]) if o != curie]


# The enum that keys records. linkml-term-validator checks that an id is
# under its root, and honors include_self, but ignores is_direct; this checks
# both from the schema, so an edit to the enum changes what is checked.
IDENTITY_ENUM = "IdentityTerm"


def identity_rule() -> tuple[str, bool, bool] | None:
    """(root, is_direct, include_self) of the identity enum, or None if records mint their ids."""
    from .paths import SCHEMA_PATH

    schema = yaml.safe_load(SCHEMA_PATH.read_text(encoding="utf-8")) or {}
    enum = (schema.get("enums") or {}).get(IDENTITY_ENUM) or {}
    query = enum.get("reachable_from") or {}
    roots = query.get("source_nodes") or []
    if len(roots) != 1:
        return None
    return str(roots[0]), bool(query.get("is_direct")), bool(query.get("include_self", True))


def check_identity(paths: list) -> int:
    from .validate import iter_records, load

    rule = identity_rule()
    if rule is None:
        print(f"No {IDENTITY_ENUM} enum with one root: nothing to check.")
        return 0
    root, direct, include_self = rule
    if not direct and include_self:
        print(f"{IDENTITY_ENUM} admits {root} and everything under it; the term check covers that.")
        return 0
    prefix = root.split(":", 1)[0] + ":"
    bad = checked = 0
    for path in [Path(p) for p in paths] or list(iter_records()):
        rid = str((load(path) or {}).get("id", ""))
        if not rid.startswith(prefix):
            continue  # a minted id: no term to check
        checked += 1
        if rid == root and not include_self:
            bad += 1
            print(f"ERROR {path}: {rid} is the root itself; a record is a term under it")
            continue
        if direct:
            try:
                found = parents(rid)
            except OSError as exc:  # an outage, not a wrong id: exit 2, as the term check does
                print(f"The ontology service did not answer for {rid}: {exc}", file=sys.stderr)
                return 2
            if root not in {cid for cid, _ in found}:
                bad += 1
                shown = ", ".join(f"{cid} {label or ''}".strip() for cid, label in found) or "none"
                print(f"ERROR {path}: {rid} is not a direct child of {root}; its parents: {shown}")
    kind = "a direct child of" if direct else "under, and not,"
    print(f"Identity: {checked} record id(s) checked, {bad} not {kind} {root}.")
    return 1 if bad else 0


def main(argv: list[str] | None = None) -> int:
    from .termcheck import Masked

    # A failed BioPortal request prints its URL, which holds the API key.
    sys.stdout, sys.stderr = Masked(sys.stdout), Masked(sys.stderr)
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
    p = sub.add_parser("parents", help="list direct is-a parents of a term")
    p.add_argument("curie")
    i = sub.add_parser("check-identity", help="check record ids against the identity enum's rule")
    i.add_argument("files", nargs="*")
    args = parser.parse_args(argv)

    if args.cmd == "check-identity":
        return check_identity(args.files)
    if args.cmd == "parents":
        for cid, label in parents(args.curie):
            print(f"{cid}\t{label or ''}")
        return 0
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
