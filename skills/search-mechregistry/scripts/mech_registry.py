#!/usr/bin/env python3
"""Search MechRegistry (https://monarch-initiative.github.io/mechregistry/) for Mechs that
overlap a planned one, and look into a Mech's repository for what another Mech can reuse.
Standard library only.

    mech_registry.py search culture medium               # every word must match; best first
    mech_registry.py search --ontology CHEBI --domain microbiology
    mech_registry.py overlap --ontology GO --ontology ECO --domain genomics --source GOA \\
        --words "gene annotation"                         # every Mech, ranked by what it shares
    mech_registry.py show culturemech                     # one Mech in full, with links both ways
    mech_registry.py repo culturemech                     # its repository: conversion scripts, exports

A word or "quoted phrase" matches a Mech's id, name, synonyms, record type,
description, domains, ontologies, data sources or collection, at the start
of a word and ignoring a plural or ending. Every word must match; --any
ranks by how many do.

`overlap` takes what a planned Mech will use (its ontologies, domains,
data sources and the words of its record type) and lists the Mechs that
share any of it, most shared first, saying what each shares.

`show` gives a Mech's record type and count, maturity, repository, schema,
license, ontologies, identifier policy, data sources, products, contacts,
and its links: the Mechs it names (consumes, hands_off_to ...) and the
Mechs that name it.

`repo` asks GitHub about a Mech's repository: the commit to pin, whether
mechmaker made it (its .copier-answers.yml, and from which mechmaker
version), its conversion and ingest scripts, its records folder, and the
exports attached to its latest release. It lists the scripts in scripts/
and src/<package>/ whose names say they bring data in (convert, ingest,
import, fetch, load, parse, transform ...), and counts the rest. Set GITHUB_TOKEN (or
GH_TOKEN) to raise GitHub's limit of 60 requests an hour; `repo` makes
seven or more per Mech, one more for each package under src/ and each
fetch or convert folder in it. If GitHub stops answering partway, the
Mechs already read are still printed, and the exit status is 2.

The registry is one file, downloaded once and kept for a day in
$XDG_CACHE_HOME/mechmaker (~/.cache/mechmaker); --refresh downloads it
again. If the download fails, an older copy is used, with a warning.

Add --json to any command but repo's text for output a program reads.

Exit status: 0 found, 1 nothing matched or an id is unknown, 2 the registry
(or, for repo, GitHub) could not be reached, 64 a usage error.
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://monarch-initiative.github.io/mechregistry/registry/mechs.json"
PAGE = "https://monarch-initiative.github.io/mechregistry/mech/{id}/"
GITHUB = "https://api.github.com"
USER_AGENT = "mechmaker-mech-registry/0.1 (+https://github.com/monarch-initiative/mechmaker)"
MAX_AGE = 24 * 3600
WEIGHTS = (("id", 6), ("name", 6), ("synonyms", 5), ("record_type", 4), ("ontologies", 4),
           ("domains", 3), ("data_sources", 3), ("collection", 2), ("description", 1))


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
    """The registry's mechs; ValueError if the file is not the registry."""
    data = json.loads(body)
    if not isinstance(data, dict) or not isinstance(data.get("mechs"), list):
        raise ValueError("not the registry: no mechs list")
    return data["mechs"]


def load(refresh: bool = False, path: Path | None = None) -> list[dict]:
    """The registry's Mechs, from the cached copy when it is fresh."""
    path = path or cache_dir() / "mechregistry.json"
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
        print(f"warning: could not download MechRegistry ({e}); using a copy {age:.0f} days old",
              file=sys.stderr)
        return kept
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(body)
    tmp.replace(path)
    return got


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


def strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    return [v for v in value or [] if isinstance(v, str)]


def source_names(mech: dict) -> list[str]:
    return [s.get("name", "") for s in mech.get("data_sources") or [] if isinstance(s, dict)]


def fields(mech: dict) -> dict[str, list[str]]:
    out = {name: [v.lower() for v in strings(mech.get(name))] for name, _ in WEIGHTS}
    out["data_sources"] = [n.lower() for n in source_names(mech)]
    return out


def term_score(term: str, pattern: re.Pattern, texts: dict[str, list[str]]) -> int:
    """The weight of the best field the term appears in; 0 if none."""
    best = 0
    for name, weight in WEIGHTS:
        values = texts[name]
        if name in ("id", "ontologies") and term.lower() in values:
            weight += 5  # the term is the id, or an ontology prefix, itself
        if any(pattern.search(v) for v in values):
            best = max(best, weight)
    return best


def has_all(mech: dict, ontologies=(), domains=(), collections=()) -> bool:
    def lower(key):
        return {v.lower() for v in strings(mech.get(key))}
    return ({o.lower() for o in ontologies} <= lower("ontologies")
            and {d.lower() for d in domains} <= lower("domains")
            and {c.lower() for c in collections} <= lower("collection"))


def search(mechs: list[dict], terms: list[str], ontologies=(), domains=(), collections=(),
           any_term: bool = False) -> list[tuple[int, dict]]:
    """Mechs matching every term (or, with any_term, at least one), most terms then best score first."""
    patterns = [(t, word_pattern(t)) for t in terms]
    hits = []
    for m in mechs:
        if not has_all(m, ontologies, domains, collections):
            continue
        texts = fields(m)
        scores = [term_score(t, pattern, texts) for t, pattern in patterns]
        if not terms or all(scores) or (any_term and any(scores)):
            hits.append((sum(1 for n in scores if n), sum(scores), m))
    hits.sort(key=lambda h: (-h[0], -h[1], h[2]["id"]))
    return [(score, m) for _, score, m in hits]


def words_of(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def same_source(a: str, b: str) -> bool:
    """Two source names for one source: the words of one are all words of the other (GOA, GOA files).

    Whole words only, so GO is not GOLD, and an empty name matches nothing.
    """
    wa, wb = words_of(a), words_of(b)
    return bool(wa and wb) and (wa <= wb or wb <= wa)


def overlap(mechs: list[dict], ontologies=(), domains=(), sources=(), words: str = "") -> list[dict]:
    """Every Mech that shares something with a planned one, with what it shares, most shared first.

    Shared ontologies weigh most: two Mechs grounded in the same ontologies can join records.
    A source matches when the words of one name are all words of the other (GOA, GOA files).
    """
    want_o = {o.lower() for o in ontologies}
    want_d = {d.lower() for d in domains}
    patterns = [(w, word_pattern(w)) for w in words.split() if len(w) > 2]
    out = []
    for m in mechs:
        shared_o = sorted(o for o in strings(m.get("ontologies")) if o.lower() in want_o)
        shared_d = sorted(d for d in strings(m.get("domains")) if d.lower() in want_d)
        shared_s = sorted({n for n in source_names(m) for s in sources if same_source(n, s)})
        record = " ".join([m.get("record_type", ""), m.get("name", "")]).lower()
        shared_w = [w for w, p in patterns if p.search(record)]
        score = 3 * len(shared_o) + 3 * len(shared_s) + 2 * len(shared_w) + len(shared_d)
        if score:
            out.append({**summary(m), "score": score, "ontologies": shared_o, "domains": shared_d,
                        "data_sources": shared_s, "record_words": shared_w})
    out.sort(key=lambda x: (-x["score"], x["id"]))
    return out


def find(mechs: list[dict], key: str) -> dict | None:
    """A Mech by id, name or synonym, ignoring case."""
    key = key.lower()
    for test in (lambda m: m["id"].lower() == key,
                 lambda m: m.get("name", "").lower() == key,
                 lambda m: key in {s.lower() for s in strings(m.get("synonyms"))}):
        for m in mechs:
            if test(m):
                return m
    return None


def links(mechs: list[dict], mech: dict) -> tuple[list[dict], list[dict]]:
    """The Mechs this one names in its cross_references, and those that name it."""
    out = [{"id": x.get("target", ""), "relation": x.get("relation", ""),
            "description": x.get("description", "")} for x in mech.get("cross_references") or []]
    into = [{"id": m["id"], "relation": x.get("relation", ""), "description": x.get("description", "")}
            for m in mechs if m["id"] != mech["id"]
            for x in m.get("cross_references") or [] if x.get("target") == mech["id"]]
    return out, into


def summary(m: dict) -> dict:
    return {"id": m["id"], "name": m.get("name", ""), "record_type": m.get("record_type", ""),
            "maturity": m.get("maturity", ""), "status": m.get("activity_status", ""),
            "record_count": m.get("record_count"), "page": PAGE.format(id=m["id"])}


def detail(mechs: list[dict], m: dict) -> dict:
    license_ = m.get("license") or {}
    out, into = links(mechs, m)
    return {
        **summary(m),
        "record_count_date": m.get("record_count_date", ""),
        "description": m.get("description", ""),
        "repository": m.get("repository", ""),
        "homepage": m.get("homepage_url", ""),
        "schema": m.get("schema_url", ""),
        "license": license_.get("spdx_id") or license_.get("label", "") if isinstance(license_, dict) else "",
        "code_license": (m.get("code_license") or {}).get("spdx_id", ""),
        "domains": strings(m.get("domains")),
        "ontologies": strings(m.get("ontologies")),
        "collection": strings(m.get("collection")),
        "taxon": strings(m.get("taxon")),
        "identifier_prefix": m.get("identifier_prefix") or "",
        "identifier_policy": m.get("record_identifier_policy", ""),
        "records_path": (m.get("record_count_source") or {}).get("path", ""),
        "data_sources": [{"name": s.get("name", ""), "url": s.get("url", ""),
                          "relation": s.get("relation_type", "")} for s in m.get("data_sources") or []],
        "products": [{"name": p.get("name", ""), "category": p.get("category", ""),
                      "format": p.get("format", ""), "url": p.get("product_url", "")}
                     for p in m.get("products") or []],
        "contacts": [c.get("label", "") for c in m.get("contacts") or []],
        "links_out": out,
        "links_in": into,
        "warnings": strings(m.get("warnings")),
    }


def github(path: str, raw: bool = False):
    """A GitHub API answer, as JSON (or, with raw, as text). None for a 404."""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(GITHUB + path, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        if e.code in (403, 429):
            raise Unreachable("GitHub refused: rate limited. Set GITHUB_TOKEN, or wait an hour.") from e
        raise Unreachable(f"GitHub: {e}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Unreachable(f"GitHub: {e}") from e
    return body if raw else json.loads(body)


def answers(text: str) -> dict[str, str]:
    """The top-level scalar answers in a .copier-answers.yml, without a YAML library."""
    out = {}
    for line in text.splitlines():
        match = re.match(r"^([A-Za-z_][\w]*):\s*(.*?)\s*$", line)
        if match and match.group(2) and not match.group(2).startswith(("[", "{", ">", "|")):
            out[match.group(1)] = match.group(2).strip("'\"")
    return out


# A script whose name says it brings data in. Only these are listed; others are counted.
# A part of the name between underscores starts with the word (fetch_bacdive, not repair_sparse).
INGEST_WORDS = re.compile(
    r"(?:^|_)(?:convert|ingest|import|fetch|download|load|harvest|parse|transform|normali[sz])")


# The modules every mechmaker Mech carries under src/<slug>/, other than convert.py. load.py reads
# records and schema_import.py imports a schema; neither brings data in. tests/test_mech_registry.py
# keeps this list equal to the template's.
TEMPLATE_MODULES = {
    "__init__.py", "compliance.py", "docs.py", "evidence.py", "export.py", "fleet.py", "history.py",
    "kgx.py", "literature.py", "load.py", "oak_compat.py", "ols.py", "paths.py", "qc.py", "records.py",
    "render.py", "report.py", "research.py", "schema_import.py", "site.py", "termcheck.py", "terms.py",
    "titles.py", "validate.py", "warm.py"}


def ingests(name: str) -> bool:
    return not name.startswith("test_") and name not in TEMPLATE_MODULES and bool(INGEST_WORDS.search(name))


def listing(full: str, path: str, sha: str) -> list[dict]:
    """One folder of the repository at the commit (GitHub lists up to 1,000 entries); [] if there is none."""
    found = github(f"/repos/{full}/contents/{urllib.parse.quote(path)}?ref={sha}")
    return found if isinstance(found, list) else []


def repo(m: dict) -> dict:
    """What a Mech's repository holds for another Mech to reuse, at its current commit."""
    match = re.match(r"https://github\.com/([^/]+)/([^/#?]+)", m.get("repository", ""))
    if not match:
        return {"id": m["id"], "error": f"not a GitHub repository: {m.get('repository')!r}"}
    full = f"{match.group(1)}/{match.group(2).removesuffix('.git')}"
    info = github(f"/repos/{full}")
    if info is None:
        return {"id": m["id"], "error": f"{full} not found on GitHub (private, renamed or gone)"}
    branch = info.get("default_branch", "main")
    sha = (github(f"/repos/{full}/commits/{urllib.parse.quote(branch)}") or {}).get("sha", "")
    out = {"id": m["id"], "repository": full, "branch": branch, "commit": sha,
           "pushed_at": info.get("pushed_at", ""),
           "repo_license": (info.get("license") or {}).get("spdx_id", "")}
    found = github(f"/repos/{full}/contents/.copier-answers.yml?ref={sha}")
    ans = answers(base64.b64decode(found["content"]).decode("utf-8", "replace")) if found else {}
    out["mechmaker"] = "mechmaker" in ans.get("_src_path", "")
    out["mechmaker_version"] = ans.get("_commit", "")
    out["template"] = ans.get("_src_path", "")

    in_scripts = [e for e in listing(full, "scripts", sha) if e["name"].endswith(".py")]
    scripts = [e["path"] for e in in_scripts if ingests(e["name"])]
    out["other_scripts"] = len(in_scripts) - len(scripts)
    packages = [e["path"] for e in listing(full, "src", sha) if e["type"] == "dir"]
    for package in packages:
        for e in listing(full, package, sha):
            if e["type"] == "file" and e["name"].endswith(".py") and ingests(e["name"]):
                scripts.append(e["path"])
            elif e["type"] == "dir" and INGEST_WORDS.search(e["name"]):
                scripts += [x["path"] for x in listing(full, e["path"], sha)
                            if x["name"].endswith(".py") and x["name"] != "__init__.py"]
    out["scripts"] = sorted(scripts)
    slug = ans.get("mech_slug", "")
    helper = f"src/{slug}/convert.py"
    out["convert_helper"] = helper if slug and helper in out["scripts"] else ""

    source = m.get("record_count_source") or {}
    out["records_dir"] = (ans.get("records_dir") or source.get("path", "")).rstrip("/")
    if out["records_dir"]:
        entries = listing(full, out["records_dir"], sha)
        out["record_sample"] = [e["path"] for e in entries if e["name"].endswith(".yaml")][:3] or \
            [e["path"] for e in entries if e["type"] == "dir"][:3]
        out["records_url"] = f"https://github.com/{full}/tree/{sha}/{out['records_dir']}"
    release = github(f"/repos/{full}/releases/latest")
    out["release"] = {"tag": release.get("tag_name", ""), "url": release.get("html_url", ""),
                      "assets": [a.get("name", "") for a in release.get("assets") or []]} if release else {}
    out["browse"] = f"https://github.com/{full}/tree/{sha}" if sha else f"https://github.com/{full}"
    out["record_count"] = m.get("record_count")
    return out


def print_summary(s: dict, score: int | None = None) -> None:
    lead = f"{score:>3}  " if score is not None else ""
    count = f", {s['record_count']} records" if s.get("record_count") is not None else ""
    status = "" if s["status"] in ("active", "") else f" [{s['status']}]"
    print(f"{lead}{s['id']}  ({s['maturity']}{count}){status}  {s['name']}")
    pad = " " * len(lead)
    print(f"{pad}  one record is {s['record_type']}")
    print(f"{pad}  {s['page']}")


def print_detail(d: dict) -> None:
    status = "" if d["status"] in ("active", "") else f"  [{d['status']}]"
    print(f"{d['id']}: {d['name']}  ({d['maturity']}){status}")
    print(f"  one record is {d['record_type']}")
    if d["record_count"] is not None:
        print(f"  records: {d['record_count']} on {d['record_count_date']}")
    for label, key in (("page", "page"), ("repository", "repository"), ("homepage", "homepage"),
                       ("schema", "schema"), ("records", "records_path"), ("license", "license"),
                       ("code license", "code_license"), ("identifier prefix", "identifier_prefix"),
                       ("identifiers", "identifier_policy")):
        if d[key]:
            print(f"  {label}: {d[key]}")
    for label, key in (("ontologies", "ontologies"), ("domains", "domains"), ("collection", "collection"),
                       ("taxon", "taxon"), ("contacts", "contacts")):
        if d[key]:
            print(f"  {label}: {', '.join(d[key])}")
    for s in d["data_sources"]:
        print(f"  source: {s['name']}  {s['url']}  ({s['relation']})")
    for p in d["products"]:
        print(f"  product: {p['name']}  [{p['category']}, {p['format']}]  {p['url']}")
    for label, key in (("links to", "links_out"), ("linked from", "links_in")):
        for x in d[key]:
            note = f": {x['description']}" if x["description"] else ""
            print(f"  {label}: {x['id']}  {x['relation']}{note}")
    for w in d["warnings"]:
        print(f"  warning: {w}")
    if d["description"]:
        print(f"  description: {d['description']}")


def print_repo(r: dict) -> None:
    if r.get("error"):
        print(f"{r['id']}: {r['error']}")
        return
    print(f"{r['id']}: {r['repository']}  ({r['branch']} at {r['commit'][:12]}, pushed {r['pushed_at']})")
    print(f"  browse at this commit: {r['browse']}")
    if r["mechmaker"]:
        print(f"  made with mechmaker {r['mechmaker_version']}: its records and conversion scripts follow the"
              " template's layout")
    elif r.get("template"):
        print(f"  made from {r['template']}, not mechmaker: read its README for its layout")
    else:
        print("  not made from a Copier template: read its README for its layout")
    if r["repo_license"]:
        print(f"  repository license: {r['repo_license']}")
    if r.get("records_dir"):
        count = f"{r['record_count']} records, as the registry counts them, " if r.get("record_count") else ""
        print(f"  records: {count}in {r['records_url']}")
        for p in r.get("record_sample", []):
            print(f"    e.g. {p}")
    if r["convert_helper"]:
        print(f"  conversion helper: {r['convert_helper']}")
    if r["scripts"]:
        print(f"  scripts that bring data in ({len(r['scripts'])}):")
        for p in r["scripts"][:30]:
            print(f"    {p}")
        if len(r["scripts"]) > 30:
            print(f"    ... {len(r['scripts']) - 30} more (--json lists them)")
    if r.get("other_scripts"):
        print(f"  and {r['other_scripts']} other scripts in scripts/, named for other work")
    if r["release"]:
        print(f"  latest release: {r['release']['tag']}  {r['release']['url']}")
        for a in r["release"]["assets"]:
            print(f"    {a}")
    else:
        print("  no release: read records from the repository, at the commit above")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--refresh", action="store_true", help="download the registry again")
    sub = parser.add_subparsers(dest="command", required=True)
    # --refresh is taken after the command too; SUPPRESS keeps a subcommand from resetting it.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--refresh", action="store_true", default=argparse.SUPPRESS)
    s = sub.add_parser("search", help="Mechs matching every word", parents=[common])
    s.add_argument("terms", nargs="*", help='words or "quoted phrases"')
    s.add_argument("--ontology", action="append", default=[], help="an ontology prefix every hit uses")
    s.add_argument("--domain", action="append", default=[], help="a domain every hit has")
    s.add_argument("--collection", action="append", default=[], help="a collection every hit is in")
    s.add_argument("--any", action="store_true", help="match any word, not every word")
    s.add_argument("--json", action="store_true")
    o = sub.add_parser("overlap", help="Mechs ranked by what they share with a planned one", parents=[common])
    o.add_argument("--ontology", action="append", default=[])
    o.add_argument("--domain", action="append", default=[])
    o.add_argument("--source", action="append", default=[], help="a data source's name")
    o.add_argument("--words", default="", help="the planned record type, in words")
    o.add_argument("--json", action="store_true")
    for name, help_ in (("show", "Mechs in full, by id"), ("repo", "what a Mech's repository holds")):
        p = sub.add_parser(name, help=help_, parents=[common])
        p.add_argument("ids", nargs="+")
        p.add_argument("--json", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 64 if e.code else 0
    if args.command == "search" and not (args.terms or args.ontology or args.domain or args.collection):
        print("search needs a word, an --ontology, a --domain or a --collection", file=sys.stderr)
        return 64
    if args.command == "overlap":
        args.ontology, args.domain, args.source = ([x for x in xs if x.strip()]
                                                   for xs in (args.ontology, args.domain, args.source))
    if args.command == "overlap" and not (args.ontology or args.domain or args.source or args.words.strip()):
        print("overlap needs an --ontology, a --domain, a --source or --words", file=sys.stderr)
        return 64
    try:
        mechs = load(args.refresh)
    except Unreachable as e:
        print(f"MechRegistry did not answer and no copy is kept: {e}", file=sys.stderr)
        return 2

    if args.command == "search":
        hits = search(mechs, args.terms, args.ontology, args.domain, args.collection, args.any)
        if args.json:
            print(json.dumps([{**summary(m), "score": n} for n, m in hits], indent=1))
        for n, m in [] if args.json else hits:
            print_summary(summary(m), n)
        if not hits:
            print(f"no Mech matched {'any' if args.any else 'every'} word", file=sys.stderr)
        return 0 if hits else 1

    if args.command == "overlap":
        rows = overlap(mechs, args.ontology, args.domain, args.source, args.words)
        if args.json:
            print(json.dumps(rows, indent=1))
        for r in [] if args.json else rows:
            print_summary(r, r["score"])
            for label in ("ontologies", "data_sources", "record_words", "domains"):
                if r[label]:
                    print(f"       shares {label.replace('_', ' ')}: {', '.join(r[label])}")
        if not rows:
            print("no Mech shares any of these", file=sys.stderr)
        return 0 if rows else 1

    status, out = 0, []
    for key in args.ids:
        m = find(mechs, key)
        if m is None:
            print(f"{key}: not in MechRegistry (try `search {key}`)", file=sys.stderr)
            status = 1
            continue
        if args.command == "show":
            out.append(detail(mechs, m))
            if not args.json:
                print_detail(out[-1])
                print()
            continue
        try:
            out.append(repo(m))
        except Unreachable as e:
            # Usually the rate limit: stop asking, and keep what was already fetched.
            print(f"{m['id']}: {e}", file=sys.stderr)
            status = 2
            break
        if out[-1].get("error"):
            status = 1
        if not args.json:
            print_repo(out[-1])
            print()
    if args.json:
        print(json.dumps(out, indent=1))
    return status


if __name__ == "__main__":
    sys.exit(main())
