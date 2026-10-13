#!/usr/bin/env python3
"""Look up prefixes, CURIEs and IRIs in the Bioregistry (https://bioregistry.io/). Standard library only.

    bioregistry.py search "growth medium"              # prefixes whose resource matches every word
    bioregistry.py search microbial strain --any       # ranked by how many words match
    bioregistry.py show mondo NCBITaxon EC             # a prefix in full, by prefix or synonym
    bioregistry.py curie MONDO:0005015 chebi:15377     # is each CURIE well formed? its standard form
    bioregistry.py iri http://purl.obolibrary.org/obo/ENVO_00002001   # an IRI as a CURIE

A word or "quoted phrase" matches a prefix, its synonyms, its name, its
keywords, its description, or its id in another registry (OBO Foundry,
OLS, BioPortal, FAIRsharing, Wikidata ...), at the start of a word and
ignoring a plural or ending. Every word must match; --any ranks by how many
do. A match in the prefix, a synonym or the name ranks above one in the
description. Deprecated prefixes are left out unless --deprecated.

`show` gives a prefix's name, description, homepage, license, the pattern
its local ids follow, an example, its URI prefix (what a CURIE expands to),
download links, its ids in other registries, and its relations: what it
is part of, provides for, depends on, and appears in.

`curie` takes the prefix in any case or as any synonym, checks the local id
against the pattern, and prints the standard CURIE and its URI. Exit 1 if
any prefix is unknown or any id breaks its pattern.

`iri` finds the prefix with the longest URI format that fits the IRI: its
own, its RDF form, its providers', identifiers.org's, and bioregistry.io's.

The registry is one file (exports/registry/registry.json in the
Bioregistry's repository), downloaded once and kept for a week in
$XDG_CACHE_HOME/mechmaker (~/.cache/mechmaker); --refresh downloads it
again. If the download fails, an older copy is used, with a warning.

Add --json to any command for output a program reads.

Exit status: 0 found, 1 nothing matched, a prefix is unknown or an id is
malformed, 2 the registry could not be downloaded and no copy is kept, 64
a usage error.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://raw.githubusercontent.com/biopragmatics/bioregistry/main/exports/registry/registry.json"
PAGE = "https://bioregistry.io/{prefix}"
USER_AGENT = "mechmaker-bioregistry/0.1 (+https://github.com/monarch-initiative/mechmaker)"
MAX_AGE = 7 * 24 * 3600
WEIGHTS = (("prefix", 6), ("synonyms", 5), ("mappings", 5), ("name", 4), ("keywords", 3),
           ("description", 1))
RELATIONS = ("part_of", "has_canonical", "provides", "depends_on", "appears_in")
REGISTRIES = ("obofoundry", "ols", "bioportal", "miriam", "fairsharing", "wikidata.property")


class Unreachable(Exception):
    pass


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "mechmaker"


def download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return body
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Unreachable(f"{url}: {e}") from e


def load(refresh: bool = False, path: Path | None = None) -> dict[str, dict]:
    """The registry, prefix -> record, from the cached copy when it is fresh."""
    path = path or cache_dir() / "bioregistry.json"
    fresh = path.exists() and time.time() - path.stat().st_mtime < MAX_AGE
    if refresh or not fresh:
        try:
            body = download(URL)
            json.loads(body)  # never cache a broken file
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".part")
            tmp.write_bytes(body)
            tmp.replace(path)
        except (Unreachable, ValueError) as e:
            if not path.exists():
                raise Unreachable(str(e)) from e
            age = (time.time() - path.stat().st_mtime) / 86400
            print(f"warning: could not download the Bioregistry ({e}); using a copy {age:.0f} days old",
                  file=sys.stderr)
    return json.loads(path.read_text())


def resolve(registry: dict[str, dict], prefix: str) -> str | None:
    """The Bioregistry prefix for a prefix written any way: itself, its preferred form, or a synonym."""
    key = prefix.strip().lower()
    if key in registry:
        return key
    for name, rec in registry.items():
        synonyms = {s.lower() for s in rec.get("synonyms") or []}
        if key == rec.get("preferred_prefix", "").lower() or key in synonyms:
            return name
    return None


def uri_prefix(rec: dict) -> str:
    """What a CURIE's prefix expands to: the uri_format up to its $1, when $1 ends it."""
    fmt = rec.get("uri_format") or ""
    return fmt[:-2] if fmt.endswith("$1") else ""


def stem(term: str) -> str:
    """A word cut back to its root, so that microbe finds microbial and microbes."""
    term = term.lower()
    if " " in term or len(term) < 5:
        return term[:-1] if term.endswith("s") and len(term) > 3 and " " not in term else term
    return re.sub(r"(ies|es|s|e|y)$", "", term)


def fields(prefix: str, rec: dict) -> dict[str, list[str]]:
    return {"prefix": [prefix, rec.get("preferred_prefix", "").lower()],
            "synonyms": [s.lower() for s in rec.get("synonyms") or []],
            "mappings": [str(v).lower() for v in (rec.get("mappings") or {}).values()],
            "name": [rec.get("name", "").lower()],
            "keywords": [k.lower() for k in rec.get("keywords") or []],
            "description": [rec.get("description", "").lower()]}


def term_score(term: str, texts: dict[str, list[str]]) -> int:
    pattern = re.compile(r"(?<![a-z0-9])" + re.escape(stem(term)))
    best = 0
    for name, weight in WEIGHTS:
        values = texts[name]
        if name in ("prefix", "synonyms", "mappings") and term.lower() in values:
            weight += 5  # the term is the prefix itself
        if any(pattern.search(v) for v in values):
            best = max(best, weight)
    return best


def search(registry: dict[str, dict], terms: list[str], limit: int = 25, any_term: bool = False,
           deprecated: bool = False) -> list[tuple[int, str]]:
    hits = []
    for prefix, rec in registry.items():
        if rec.get("deprecated") and not deprecated:
            continue
        texts = fields(prefix, rec)
        scores = [term_score(t, texts) for t in terms]
        if all(scores) or (any_term and any(scores)):
            hits.append((sum(1 for n in scores if n), sum(scores), prefix))
    hits.sort(key=lambda h: (-h[0], -h[1], h[2]))
    out = [(score, prefix) for _, score, prefix in hits]
    return out[:limit] if limit else out


def summary(prefix: str, rec: dict) -> dict:
    return {"prefix": prefix, "preferred_prefix": rec.get("preferred_prefix", prefix),
            "name": rec.get("name", ""), "deprecated": bool(rec.get("deprecated")),
            "page": PAGE.format(prefix=prefix)}


def detail(prefix: str, rec: dict) -> dict:
    example = rec.get("example", "")
    return {
        **summary(prefix, rec),
        "description": rec.get("description", ""),
        "homepage": rec.get("homepage", ""),
        "license": rec.get("license", ""),
        "pattern": rec.get("pattern", ""),
        "example": f"{rec.get('preferred_prefix', prefix)}:{example}" if example else "",
        "uri_prefix": uri_prefix(rec),
        "uri_format": rec.get("uri_format", ""),
        "synonyms": rec.get("synonyms") or [],
        "keywords": rec.get("keywords") or [],
        "repository": rec.get("repository", ""),
        "downloads": {k[len("download_"):]: v for k, v in rec.items() if k.startswith("download_")},
        "mappings": rec.get("mappings") or {},
        **{rel: ([rec[rel]] if isinstance(rec.get(rel), str) else rec.get(rel) or []) for rel in RELATIONS},
    }


def check_curie(registry: dict[str, dict], curie: str) -> dict:
    """A CURIE checked: its standard form and URI, or the reason it fails."""
    out = {"curie": curie, "ok": False}
    if ":" not in curie:
        return {**out, "error": "no colon: a CURIE is prefix:local_id"}
    given, local = curie.split(":", 1)
    prefix = resolve(registry, given)
    if prefix is None:
        return {**out, "error": f"unknown prefix {given!r} (try `search {given}`)"}
    rec = registry[prefix]
    banana = rec.get("banana")
    if banana and local.startswith(banana + rec.get("banana_peel", ":")):
        local = local[len(banana + rec.get("banana_peel", ":")):]  # go:GO:0008150 -> 0008150
    preferred = rec.get("preferred_prefix", prefix)
    out.update(prefix=prefix, preferred_prefix=preferred, local_id=local, standard=f"{preferred}:{local}",
               uri=rec["uri_format"].replace("$1", local) if rec.get("uri_format") else "")
    if rec.get("deprecated"):
        canonical = rec.get("has_canonical")
        out["warning"] = "deprecated prefix" + (f"; use {canonical}" if canonical else "")
    pattern = rec.get("pattern")
    if pattern and not re.match(pattern, local):
        return {**out, "error": f"{local!r} does not match {preferred}'s pattern {pattern}"}
    if given != preferred:
        out["note"] = f"written {given}; the preferred prefix is {preferred}"
    return {**out, "ok": True}


def iri_formats(prefix: str, rec: dict) -> list[str]:
    """Every URI format the prefix's ids are written in, each with one $1."""
    fmts = [rec.get("uri_format"), rec.get("rdf_uri_format"), f"https://bioregistry.io/{prefix}:$1"]
    fmts += [p.get("uri_format") for p in rec.get("providers") or []]
    miriam = (rec.get("mappings") or {}).get("miriam")
    if miriam:
        fmts += [f"{scheme}://identifiers.org/{miriam}{sep}$1"
                 for scheme in ("http", "https") for sep in ":/"]
    return [f for f in fmts if f and f.count("$1") == 1]


def parse_iri(registry: dict[str, dict], iri: str) -> dict:
    """The CURIE for an IRI: the prefix with the longest URI format that fits it."""
    best = ("", "", 0)
    for prefix, rec in registry.items():
        if rec.get("deprecated"):
            continue
        for fmt in iri_formats(prefix, rec):
            head, tail = fmt.split("$1")
            # A resolver taking a CURIE (identifiers.org/CHEBI:15377) takes its prefix in any case.
            starts = iri.lower().startswith(head.lower()) if head.endswith(":") else iri.startswith(head)
            fits = starts and iri.endswith(tail) and len(iri) > len(head) + len(tail)
            if fits and len(head) + len(tail) > best[2]:
                best = (prefix, iri[len(head):len(iri) - len(tail)], len(head) + len(tail))
    if not best[0]:
        return {"iri": iri, "ok": False, "error": "no prefix's URI format fits it"}
    result = check_curie(registry, f"{best[0]}:{best[1]}")
    result.pop("note", None)  # the prefix was found, not written
    return {"iri": iri, **result}


def print_detail(d: dict) -> None:
    flag = "  [deprecated]" if d["deprecated"] else ""
    print(f"{d['preferred_prefix']}: {d['name']}{flag}")
    for label, key in (("page", "page"), ("homepage", "homepage"), ("license", "license"),
                       ("pattern", "pattern"), ("example", "example"), ("uri prefix", "uri_prefix"),
                       ("repository", "repository")):
        if d[key]:
            print(f"  {label}: {d[key]}")
    if d["uri_format"] and not d["uri_prefix"]:
        print(f"  uri format: {d['uri_format']}")
    for label, key in (("synonyms", "synonyms"), ("keywords", "keywords")):
        if d[key]:
            print(f"  {label}: {', '.join(d[key])}")
    for kind, url in sorted(d["downloads"].items()):
        print(f"  download ({kind}): {url}")
    known = {k: v for k, v in d["mappings"].items() if k in REGISTRIES}
    if known:
        print("  in other registries: " + ", ".join(f"{k}={v}" for k, v in sorted(known.items())))
    if len(d["mappings"]) > len(known):
        print(f"  ... and {len(d['mappings']) - len(known)} more (--json lists them)")
    for rel in RELATIONS:
        if d[rel]:
            print(f"  {rel.replace('_', ' ')}: {', '.join(d[rel])}")
    if d["description"]:
        first = d["description"].strip().split("\n\n")[0]
        more = "  (more: --json)" if first != d["description"].strip() else ""
        print(f"  description: {first}{more}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="download the registry again")
    sub = parser.add_subparsers(dest="command", required=True)
    s = sub.add_parser("search", help="prefixes matching every word")
    s.add_argument("terms", nargs="+", help='words or "quoted phrases"')
    s.add_argument("--any", action="store_true", help="match any word, not every word")
    s.add_argument("--deprecated", action="store_true", help="include deprecated prefixes")
    s.add_argument("--limit", type=int, default=25, help="at most this many (0: all)")
    s.add_argument("--json", action="store_true")
    for name, help_, arg in (("show", "prefixes in full", "prefixes"), ("curie", "check CURIEs", "curies"),
                             ("iri", "IRIs as CURIEs", "iris")):
        p = sub.add_parser(name, help=help_)
        p.add_argument(arg, nargs="+")
        p.add_argument("--json", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 64 if e.code else 0
    try:
        registry = load(args.refresh)
    except Unreachable as e:
        print(f"the Bioregistry did not answer and no copy is kept: {e}", file=sys.stderr)
        return 2

    if args.command == "search":
        hits = search(registry, args.terms, args.limit, args.any, args.deprecated)
        if args.json:
            print(json.dumps([{**summary(p, registry[p]), "score": n} for n, p in hits], indent=1))
        for n, p in [] if args.json else hits:
            d = summary(p, registry[p])
            flag = "  [deprecated]" if d["deprecated"] else ""
            print(f"{n:>3}  {d['preferred_prefix']}  {d['name']}{flag}\n       {d['page']}")
        if not hits:
            print("no prefix matched every word", file=sys.stderr)
        return 0 if hits else 1

    if args.command == "show":
        out, status = [], 0
        for given in args.prefixes:
            prefix = resolve(registry, given)
            if prefix is None:
                print(f"{given}: not in the Bioregistry (try `search {given}`)", file=sys.stderr)
                status = 1
                continue
            out.append(detail(prefix, registry[prefix]))
            if not args.json:
                print_detail(out[-1])
                print()
        if args.json:
            print(json.dumps(out, indent=1))
        return status

    check = check_curie if args.command == "curie" else parse_iri
    results = [check(registry, x) for x in (args.curies if args.command == "curie" else args.iris)]
    if args.json:
        print(json.dumps(results, indent=1))
    for r in [] if args.json else results:
        given = r.get("curie") if args.command == "curie" else r["iri"]
        if r["ok"]:
            print(f"ok    {given}  ->  {r['standard']}" + (f"  {r['uri']}" if r.get("uri") else ""))
        else:
            print(f"FAIL  {given}: {r['error']}")
        for key in ("note", "warning"):
            if r.get(key):
                print(f"      {r[key]}")
    return 0 if all(r["ok"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
