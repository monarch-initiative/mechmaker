"""Ontology lookups over the EBI OLS4 API, for the things `runoak -i ols:` cannot do.

    python -m <slug>.ols ancestors GO:0015979     # is-a ancestors (--part-of adds part-of)
    python -m <slug>.ols ancestors ENVO:00000051 --ontology envo
    python -m <slug>.ols check GO:0015979 --root GO:0008150

Use `ancestors` when a term fails a dynamic enum: it shows which branch the
term really sits under. The ontology defaults to the lowercased prefix.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

OLS = "https://www.ebi.ac.uk/ols4/api"


def _get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)


def _term_url(curie: str, ontology: str) -> str:
    """The OLS URL of a term. IRIs differ by ontology (EFO's are not OBO PURLs),
    so the term is found by its CURIE and its URL built from the IRI OLS gives."""
    q = urllib.parse.urlencode({"obo_id": curie})
    try:
        terms = _get(f"{OLS}/ontologies/{ontology}/terms?{q}").get("_embedded", {}).get("terms", [])
    except urllib.error.HTTPError as exc:
        if exc.code != 404:  # OLS answers an unknown term with 404
            raise
        terms = []
    if not terms:
        raise LookupError(f"{curie} is not in the OLS ontology {ontology}")
    iri = urllib.parse.quote(urllib.parse.quote(terms[0]["iri"], safe=""), safe="")
    return f"{OLS}/ontologies/{ontology}/terms/{iri}"


def ancestors(curie: str, ontology: str | None = None, hierarchical: bool = False) -> list[tuple[str, str]]:
    ontology = ontology or curie.split(":", 1)[0].lower()
    kind = "hierarchicalAncestors" if hierarchical else "ancestors"
    out: list[tuple[str, str]] = []
    url = f"{_term_url(curie, ontology)}/{kind}?size=500"
    while url:
        data = _get(url)
        for t in data.get("_embedded", {}).get("terms", []):
            out.append((t.get("obo_id") or t.get("iri"), t.get("label")))
        url = data.get("_links", {}).get("next", {}).get("href")
    return out


def parents(curie: str, ontology: str | None = None) -> list[tuple[str, str]]:
    """Direct is-a parents."""
    ontology = ontology or curie.split(":", 1)[0].lower()
    data = _get(f"{_term_url(curie, ontology)}/parents?size=500")
    found = data.get("_embedded", {}).get("terms", [])
    return [(t.get("obo_id") or t.get("iri"), t.get("label")) for t in found]


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
