#!/usr/bin/env python3
"""Search KG-Registry (https://kghub.org/kg-registry/): knowledge graphs, data sources,
ontologies, aggregators and data models, with what each one is built from. Standard library only.

    kg_registry.py search microbe traits                 # every word must match; best first
    kg_registry.py search "rare disease" --category KnowledgeGraph
    kg_registry.py search --domain microbiology --category DataSource
    kg_registry.py show kg-microbe bacdive               # one resource in full
    kg_registry.py used-by bacdive                       # which resources take it as a source
    kg_registry.py domains                               # the domain words, with counts

A word or "quoted phrase" matches a resource's id, name, synonyms, domains,
infores id or description, at the start of a word and ignoring a plural or
ending (microbe finds microbial). Every word must match; --any ranks by how
many do. A match in the id, name or synonyms ranks above
one in the description. Categories are DataSource, Ontology,
KnowledgeGraph, Aggregator, DataModel and Resource. Inactive, orphaned and
unresponsive resources are listed too, with their status.

`show` gives a resource's page, homepage, repository, license, domains,
taxa, its own products by kind, its sources (what its products are built
from) and the resources that take it as a source. Each source and user is a
KG-Registry id, which `show` takes in turn.

The registry is one file, downloaded once and kept for a week in
$XDG_CACHE_HOME/mechmaker (~/.cache/mechmaker); --refresh downloads it
again. If the download fails, an older copy is used, with a warning.

Add --json to search, show or used-by for output a program reads.

Exit status: 0 found, 1 nothing matched or an id is unknown, 2 the registry
could not be downloaded and no copy is kept, 64 a usage error.
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

URL = "https://kghub.org/kg-registry/registry/kgs.jsonld"
PAGE = "https://kghub.org/kg-registry/resource/{id}/{id}.html"
USER_AGENT = "mechmaker-kg-registry/0.1 (+https://github.com/monarch-initiative/mechmaker)"
MAX_AGE = 7 * 24 * 3600
CATEGORIES = ("DataSource", "Ontology", "KnowledgeGraph", "Aggregator", "DataModel", "Resource")
WEIGHTS = (("id", 5), ("name", 4), ("synonyms", 4), ("infores_id", 4), ("domains", 3), ("description", 1))


class Unreachable(Exception):
    pass


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    return Path(base) / "mechmaker"


def download(url: str) -> bytes:
    """The body of url, asked for gzipped (KG-Registry's file shrinks from 38 MB to under 3 MB)."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return body
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Unreachable(f"{url}: {e}") from e


def parse(body: bytes | str) -> list[dict]:
    """The registry's resources; ValueError if the file is not the registry."""
    data = json.loads(body)
    if not isinstance(data, dict) or not isinstance(data.get("resources"), list):
        raise ValueError("not the registry: no resources list")
    return data["resources"]


def load(refresh: bool = False, path: Path | None = None) -> list[dict]:
    """The registry's resources, from the cached copy when it is fresh."""
    path = path or cache_dir() / "kg-registry.jsonld"
    kept = None
    if path.exists():
        try:
            kept = parse(path.read_text())
        except ValueError:
            kept = None  # a broken copy: download again
    fresh = kept is not None and time.time() - path.stat().st_mtime < MAX_AGE
    if fresh and not refresh:
        return kept
    try:
        body = download(URL)
        got = parse(body)  # never cache a file that is not the registry
    except (Unreachable, ValueError) as e:
        if kept is None:
            raise Unreachable(str(e)) from e
        age = (time.time() - path.stat().st_mtime) / 86400
        print(f"warning: could not download KG-Registry ({e}); using a copy {age:.0f} days old",
              file=sys.stderr)
        return kept
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(body)
    tmp.replace(path)
    return got


def page(rid: str) -> str:
    return PAGE.format(id=rid)


def fields(resource: dict) -> dict[str, list[str]]:
    out = {}
    for name, _ in WEIGHTS:
        value = resource.get(name) or []
        out[name] = [v.lower() for v in ([value] if isinstance(value, str) else value) if isinstance(v, str)]
    return out


def stem(word: str) -> str:
    """A word cut back to its root, so that microbe finds microbial and microbes, and goat finds goats."""
    word = word.lower()
    if len(word) < 5:
        return word[:-1] if word.endswith("s") and len(word) > 3 else word
    if word.endswith("ss"):
        return word  # process, class
    if word.endswith("sis"):
        return word[:-2]  # analysis finds analyses
    if word.endswith("cies"):
        return word[:-1]  # species, not spec
    return re.sub(r"(ies|es|s|e|y)$", "", word)


def word_pattern(term: str) -> re.Pattern:
    """A term's words, each cut back to its root, in order, each at the start of a word."""
    stems = [re.escape(stem(w)) for w in term.split()]
    return re.compile(r"(?<![a-z0-9])" + r"[a-z0-9-]*[\s_/-]+".join(stems))  # culture-media, sea-water sample


def term_score(term: str, pattern: re.Pattern, texts: dict[str, list[str]]) -> int:
    """The weight of the best field the term appears in; 0 if none."""
    best = 0
    for name, weight in WEIGHTS:
        values = texts[name]
        if name in ("id", "infores_id") and term.lower() in values:
            weight += 5  # the term is the id itself
        if any(pattern.search(v) for v in values):
            best = max(best, weight)
    return best


def search(resources: list[dict], terms: list[str], categories: list[str] = (), domains: list[str] = (),
           limit: int = 25, any_term: bool = False) -> list[tuple[int, dict]]:
    """Resources matching every term (or, with any_term, at least one), most terms then best score first."""
    cats = {c.lower() for c in categories}
    doms = {d.lower() for d in domains}
    patterns = [(t, word_pattern(t)) for t in terms]
    hits = []
    for r in resources:
        if cats and r.get("category", "").lower() not in cats:
            continue
        if doms and not doms <= {d.lower() for d in r.get("domains") or []}:
            continue
        texts = fields(r)
        scores = [term_score(t, pattern, texts) for t, pattern in patterns]
        if all(scores) or (any_term and any(scores)):
            hits.append((sum(1 for n in scores if n), sum(scores), r))
    hits.sort(key=lambda h: (-h[0], -h[1], h[2]["id"]))
    hits = [(score, r) for _, score, r in hits]
    return hits[:limit] if limit else hits


def find(resources: list[dict], key: str) -> dict | None:
    """A resource by id, infores id, synonym or name, ignoring case."""
    key = key.lower()
    for test in (lambda r: r["id"].lower() == key,
                 lambda r: (r.get("infores_id") or "").lower() == key,
                 lambda r: key in {s.lower() for s in r.get("synonyms") or []},
                 lambda r: r.get("name", "").lower() == key):
        for r in resources:
            if test(r):
                return r
    return None


def owner(product_id: str, ids: set[str]) -> str:
    """The resource that makes a product: the longest resource id its id starts with.

    KG-Registry lists a product on its maker's page and on the page of each source it
    uses, so a resource's `products` hold others' products too. The product id says
    whose it is: kg-microbe.graph.raw belongs to kg-microbe, wherever it is listed.
    """
    parts = product_id.split(".")
    for i in range(len(parts), 0, -1):
        if ".".join(parts[:i]) in ids:
            return ".".join(parts[:i])
    return ""


def own_products(r: dict, ids: set[str]) -> list[dict]:
    return [p for p in r.get("products") or [] if owner(p.get("id", ""), ids) == r["id"]]


def sources(r: dict, ids: set[str]) -> dict[str, set[str]]:
    """What the resource's own products are built from: source id -> relation types. Itself excluded."""
    out: dict[str, set[str]] = {}
    for product in own_products(r, ids):
        for src in (product.get("original_source") or []) + (product.get("secondary_source") or []):
            if isinstance(src, dict) and src.get("source") and src["source"] != r["id"]:
                out.setdefault(src["source"], set()).add(src.get("relation_type", ""))
    return out


def used_by(resources: list[dict], rid: str, ids: set[str]) -> list[dict]:
    """Resources whose own products take rid as a source."""
    users: set[str] = set()
    for r in resources:
        for p in r.get("products") or []:
            maker = owner(p.get("id", ""), ids)
            if maker == rid or maker in users:
                continue
            srcs = (p.get("original_source") or []) + (p.get("secondary_source") or [])
            if any(isinstance(src, dict) and src.get("source") == rid for src in srcs):
                users.add(maker)
    return [r for r in resources if r["id"] in users]


def summary(r: dict) -> dict:
    return {"id": r["id"], "name": r.get("name", ""), "category": r.get("category", ""),
            "status": r.get("activity_status", ""), "domains": r.get("domains") or [], "page": page(r["id"])}


def detail(resources: list[dict], r: dict, ids: set[str]) -> dict:
    names = {x["id"]: x.get("name", "") for x in resources}
    products: dict[str, int] = {}
    formats: set[str] = set()
    for p in own_products(r, ids):
        products[p.get("category") or "Product"] = products.get(p.get("category") or "Product", 0) + 1
        if p.get("format"):
            formats.add(p["format"])
    license_ = r.get("license") or {}
    return {
        **summary(r),
        "description": r.get("description", ""),
        "homepage": r.get("homepage_url", ""),
        "repository": r.get("repository", ""),
        "license": license_ if isinstance(license_, str) else license_.get("label") or license_.get("id", ""),
        "taxon": r.get("taxon") or [],
        "infores_id": r.get("infores_id", ""),
        "collection": r.get("collection") or [],
        "use_instead": r.get("use_instead") or [],
        "warnings": r.get("warnings") or [],
        "products": products,
        "formats": sorted(formats),
        "publications": [p.get("doi") or p.get("id", "") for p in r.get("publications") or []],
        "sources": [{"id": s, "name": names.get(s, ""), "relations": sorted(rel)}
                    for s, rel in sorted(sources(r, ids).items())],
        "used_by": [{"id": u["id"], "name": u.get("name", ""), "category": u.get("category", "")}
                    for u in used_by(resources, r["id"], ids)],
    }


def print_summary(s: dict, score: int | None = None) -> None:
    status = "" if s["status"] == "active" else f" [{s['status']}]"
    lead = f"{score:>3}  " if score is not None else ""
    print(f"{lead}{s['id']}  ({s['category']}{status})  {s['name']}")
    pad = " " * len(lead)
    if s["domains"]:
        print(f"{pad}  domains: {', '.join(s['domains'])}")
    print(f"{pad}  {s['page']}")


def print_detail(d: dict, show_all: bool) -> None:
    status = "" if d["status"] == "active" else f"  [{d['status']}]"
    print(f"{d['id']}: {d['name']}  ({d['category']}){status}")
    for label, key in (("page", "page"), ("homepage", "homepage"), ("repository", "repository"),
                       ("license", "license"), ("infores", "infores_id")):
        if d[key]:
            print(f"  {label}: {d[key]}")
    for label, key in (("domains", "domains"), ("taxon", "taxon"), ("collection", "collection"),
                       ("use instead", "use_instead"), ("formats", "formats")):
        if d[key]:
            print(f"  {label}: {', '.join(d[key])}")
    if d["products"]:
        print("  products: " + ", ".join(f"{n} {k}" for k, n in sorted(d["products"].items())))
    if d["description"]:
        print(f"  description: {d['description']}")
    for w in d["warnings"]:
        print(f"  warning: {w}")
    if d["publications"]:
        print(f"  publications: {', '.join(d['publications'][:5])}")
    for label, rows in (("sources", d["sources"]), ("used by", d["used_by"])):
        if not rows:
            continue
        shown = rows if show_all else rows[:20]
        print(f"  {label} ({len(rows)}):")
        for row in shown:
            print(f"    {row['id']}  {row['name']}")
        if len(shown) < len(rows):
            print(f"    ... {len(rows) - len(shown)} more (--all lists them)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="download the registry again")
    sub = parser.add_subparsers(dest="command", required=True)
    # --refresh is taken after the command too; SUPPRESS keeps a subcommand from resetting it.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--refresh", action="store_true", default=argparse.SUPPRESS)
    s = sub.add_parser("search", help="resources matching every word", parents=[common])
    s.add_argument("terms", nargs="*", help='words or "quoted phrases"')
    s.add_argument("--category", action="append", default=[], help=f"one of {', '.join(CATEGORIES)}")
    s.add_argument("--domain", action="append", default=[], help="a domain word, as `domains` lists them")
    s.add_argument("--any", action="store_true", help="match any word, not every word")
    s.add_argument("--limit", type=int, default=25, help="at most this many (0: all)")
    s.add_argument("--json", action="store_true")
    sh = sub.add_parser("show", help="resources in full, by id", parents=[common])
    sh.add_argument("ids", nargs="+")
    sh.add_argument("--all", action="store_true", help="list every source and user")
    sh.add_argument("--json", action="store_true")
    u = sub.add_parser("used-by", help="resources that take each id as a source", parents=[common])
    u.add_argument("ids", nargs="+")
    u.add_argument("--json", action="store_true")
    sub.add_parser("domains", help="the domain words, with counts", parents=[common])
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 64 if e.code else 0
    if args.command == "search" and not (args.terms or args.category or args.domain):
        print("search needs a word, a --category or a --domain", file=sys.stderr)
        return 64
    bad = [c for c in getattr(args, "category", []) if c.lower() not in {x.lower() for x in CATEGORIES}]
    if bad:
        print(f"unknown category: {', '.join(bad)} (one of {', '.join(CATEGORIES)})", file=sys.stderr)
        return 64
    try:
        resources = load(args.refresh)
    except Unreachable as e:
        print(f"KG-Registry did not answer and no copy is kept: {e}", file=sys.stderr)
        return 2

    if args.command == "domains":
        counts: dict[str, int] = {}
        for r in resources:
            for d in r.get("domains") or []:
                counts[d] = counts.get(d, 0) + 1
        for d, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"{n:>5}  {d}")
        return 0

    if args.command == "search":
        hits = search(resources, args.terms, args.category, args.domain, args.limit, args.any)
        if args.json:
            print(json.dumps([{**summary(r), "score": n} for n, r in hits], indent=1))
        for n, r in [] if args.json else hits:
            print_summary(summary(r), n)
        if not hits:
            print(f"no resource matched {'any' if args.any else 'every'} word", file=sys.stderr)
        return 0 if hits else 1

    status = 0
    out = []
    ids = {r["id"] for r in resources}
    for key in args.ids:
        r = find(resources, key)
        if r is None:
            print(f"{key}: not in KG-Registry (try `search {key}`)", file=sys.stderr)
            status = 1
            continue
        if args.command == "show":
            d = detail(resources, r, ids)
            out.append(d)
            if not args.json:
                print_detail(d, args.all)
                print()
        else:
            users = [summary(x) for x in used_by(resources, r["id"], ids)]
            out.append({"id": r["id"], "used_by": users})
            if not args.json:
                print(f"{r['id']} is a source of {len(users)} resource(s):")
                for x in users:
                    print_summary(x)
                print()
    if args.json:
        print(json.dumps(out, indent=1))
    return status


if __name__ == "__main__":
    sys.exit(main())
