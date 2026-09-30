"""Ontology lookups over the EBI OLS4 API, for the things `runoak -i ols:` cannot do.

    python -m <slug>.ols ancestors GO:0015979     # is-a and part-of ancestors
    python -m <slug>.ols ancestors ENVO:00000051 --ontology envo
    python -m <slug>.ols check GO:0015979 --root GO:0008150

Use `ancestors` when a term fails a dynamic enum: it shows which branch the
term really sits under. The ontology defaults to the lowercased prefix.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request

OLS = "https://www.ebi.ac.uk/ols4/api"


def _iri(curie: str) -> str:
    prefix, local = curie.split(":", 1)
    return f"http://purl.obolibrary.org/obo/{prefix}_{local}"


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)


def ancestors(curie: str, ontology: str | None = None, hierarchical: bool = False) -> list[tuple[str, str]]:
    ontology = ontology or curie.split(":", 1)[0].lower()
    iri = urllib.parse.quote(urllib.parse.quote(_iri(curie), safe=""), safe="")
    kind = "hierarchicalAncestors" if hierarchical else "ancestors"
    out: list[tuple[str, str]] = []
    url = f"{OLS}/ontologies/{ontology}/terms/{iri}/{kind}?size=500"
    while url:
        data = _get(url)
        for t in data.get("_embedded", {}).get("terms", []):
            out.append((t.get("obo_id") or t.get("iri"), t.get("label")))
        url = data.get("_links", {}).get("next", {}).get("href")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("ancestors", help="list ancestors of a term")
    a.add_argument("curie")
    a.add_argument("--ontology", help="OLS ontology id (default: lowercased prefix)")
    a.add_argument("--part-of", action="store_true", help="include part-of ancestors")
    c = sub.add_parser("check", help="is ROOT an ancestor of CURIE (or CURIE itself)?")
    c.add_argument("curie")
    c.add_argument("--root", required=True)
    c.add_argument("--ontology")
    args = parser.parse_args(argv)

    if args.cmd == "ancestors":
        for cid, label in sorted(ancestors(args.curie, args.ontology, args.part_of)):
            print(f"{cid}\t{label}")
        return 0
    found = args.curie == args.root or args.root in {cid for cid, _ in ancestors(args.curie, args.ontology)}
    print(f"{args.root} {'is' if found else 'is NOT'} an is-a ancestor of {args.curie}")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
