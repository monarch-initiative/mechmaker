#!/usr/bin/env python3
"""Search the structured data ingests mechmaker knows: the Monarch Initiative's. Standard library only.

    ingest_catalog.py list                       # every ingest, one line each
    ingest_catalog.py search zebrafish phenotype # every word must match; best first
    ingest_catalog.py search infores:omim        # the ingests that read a source
    ingest_catalog.py show zfin hpoa             # in full, with the conf/ingests.yaml entry
    ingest_catalog.py releases zfin              # its latest release: tag, date, file sizes (network)
    ingest_catalog.py check                      # every entry's files are in its latest release (network)

The catalog is ingest_catalog.json beside this script, a copy of
`ingest_catalog` in mechmaker's copier.yml (the Copier `ingests` question
offers the same entries). A word matches an ingest's key, name, what it covers, description,
sources (infores ids), the Biolink classes it produces, or its files, at the
start of a word and ignoring a plural; --any ranks by how many words match.

Each ingest is a repository that turns one upstream source into KGX nodes
and edges with Koza, and publishes them as a GitHub release, monthly, with
a release-metadata.yaml that gives each file's sha256 and the upstream
versions. `releases` reads it. GITHUB_TOKEN or GH_TOKEN, if set, lifts
GitHub's limit of 60 requests an hour.

Add --json to list, search, show or releases for output a program reads.

Exit status: 0 found, 1 nothing matched, a key is unknown or `check` found a
problem, 2 GitHub could not be reached, 64 a usage error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

CATALOG = Path(__file__).resolve().with_name("ingest_catalog.json")
USER_AGENT = "mechmaker-ingest-catalog/0.1 (+https://github.com/monarch-initiative/mechmaker)"
WEIGHTS = (("key", 5), ("name", 5), ("covers", 4), ("sources", 4), ("produces", 3), ("description", 2),
           ("files", 1))


class Unreachable(Exception):
    pass


def load(path: Path = CATALOG) -> dict[str, dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def texts(key: str, entry: dict) -> dict[str, list[str]]:
    def words(value) -> list[str]:
        return [str(v) for v in value] if isinstance(value, list) else [str(value or "")]

    return {"key": [key.replace("_", " ")], "name": words(entry.get("name")),
            "covers": words(entry.get("covers")),
            "description": words(entry.get("description")), "sources": words(entry.get("sources")),
            "produces": [re.sub(r"(?<!^)(?=[A-Z])", " ", p) for p in entry.get("produces") or []],
            "files": [f.replace("_", " ") for f in entry.get("files") or []]}


def word_pattern(term: str) -> re.Pattern:
    term = term.lower()
    if ":" not in term and len(term) > 4 and term.endswith("s"):
        term = term[:-1]
    return re.compile(r"(?<![a-z0-9])" + re.escape(term), re.IGNORECASE)


def search(catalog: dict[str, dict], terms: list[str], any_word: bool = False) -> list[tuple[int, str]]:
    hits = []
    for key, entry in catalog.items():
        fields = texts(key, entry)
        total, matched = 0, 0
        for term in terms:
            pattern = word_pattern(term)
            score = max((w for f, w in WEIGHTS if any(pattern.search(t) for t in fields[f])), default=0)
            matched += bool(score)
            total += score
        if matched and (any_word or matched == len(terms)):
            hits.append((matched * 100 + total, key))
    return sorted(hits, key=lambda h: (-h[0], h[1]))


def conf_entry(key: str, entry: dict) -> str:
    """The lines a Mech's conf/ingests.yaml takes for this ingest."""
    files = "".join(f"\n      - {f}" for f in entry["files"])
    return (f"  {key}:\n    kind: release\n    repo: {entry['repo']}\n"
            f"    sources: [{', '.join(entry['sources'])}]\n    files:{files}")


def get_json(url: str):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as resp:
            return json.loads(resp.read())
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Unreachable(f"{url}: {e}") from e


def latest_release(repo: str) -> dict:
    """The latest release: tag, date, and each asset's size."""
    data = get_json(f"https://api.github.com/repos/{repo}/releases/latest")
    return {"tag": data["tag_name"], "published": data.get("published_at"),
            "assets": {a["name"]: a["size"] for a in data.get("assets") or []}}


def size(n: int) -> str:
    for unit in ("B", "kB", "MB", "GB"):
        if n < 1000 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1000
    return str(n)


def line(key: str, entry: dict) -> str:
    flag = "" if entry.get("in_monarch_kg") else "  (not in the Monarch KG)"
    return f"{key:12} {entry['name']}: {entry['covers']}{flag}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    js = argparse.ArgumentParser(add_help=False)
    js.add_argument("--json", action="store_true")
    sub.add_parser("list", help="every ingest", parents=[js])
    s = sub.add_parser("search", help="ingests matching every word", parents=[js])
    s.add_argument("terms", nargs="+")
    s.add_argument("--any", action="store_true", help="rank by how many words match")
    sh = sub.add_parser("show", help="ingests in full, by key", parents=[js])
    sh.add_argument("keys", nargs="+")
    r = sub.add_parser("releases", help="the latest release of each, from GitHub", parents=[js])
    r.add_argument("keys", nargs="+")
    sub.add_parser("check", help="every entry's files are in its latest release")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 64 if e.code else 0
    catalog = load()
    as_json = getattr(args, "json", False)

    if args.command == "list":
        if as_json:
            print(json.dumps(catalog, indent=1))
        else:
            for key, entry in catalog.items():
                print(line(key, entry))
        return 0

    if args.command == "search":
        hits = search(catalog, args.terms, args.any)
        if as_json:
            print(json.dumps([{"key": k, "score": sc, **catalog[k]} for sc, k in hits], indent=1))
        for _, key in hits if not as_json else []:
            print(line(key, catalog[key]))
        return 0 if hits else 1

    keys = getattr(args, "keys", None) or list(catalog)
    unknown = [k for k in keys if k not in catalog]
    if unknown:
        print(f"not in the catalog: {', '.join(unknown)} (`list` shows every key)", file=sys.stderr)
        return 1

    if args.command == "show":
        if as_json:
            print(json.dumps({k: catalog[k] for k in keys}, indent=1))
            return 0
        for key in keys:
            e = catalog[key]
            print(f"{key}: {e['name']}, {e['covers']}\n  {e['description']}")
            print(f"  repository  https://github.com/{e['repo']}")
            print(f"  sources     {', '.join(e['sources'])}")
            print(f"  produces    {', '.join(e['produces'])}")
            print(f"  code        {e['code_license']} (the upstream data's own terms are separate)")
            print(f"  Monarch KG  {'yes' if e['in_monarch_kg'] else 'no'}")
            if e.get("note"):
                print(f"  note        {e['note']}")
            print("  conf/ingests.yaml:\n" + conf_entry(key, e) + "\n")
        return 0

    try:
        if args.command == "releases":
            out = {k: latest_release(catalog[k]["repo"]) for k in keys}
            if as_json:
                print(json.dumps(out, indent=1))
                return 0
            for key, rel in out.items():
                print(f"{key}: {catalog[key]['repo']} {rel['tag']} ({(rel['published'] or '')[:10]})")
                for f in catalog[key]["files"]:
                    print(f"  {f:48} {size(rel['assets'][f]) if f in rel['assets'] else 'MISSING'}")
            return 0

        problems = []
        for key, entry in catalog.items():
            rel = latest_release(entry["repo"])
            missing = [f for f in entry["files"] + ["release-metadata.yaml"] if f not in rel["assets"]]
            if missing:
                problems.append(f"{key}: {rel['tag']} lacks {', '.join(missing)}")
            print(f"{key:12} {rel['tag']:12} {'ok' if not missing else 'MISSING ' + ', '.join(missing)}")
        print(f"{len(catalog)} ingest(s), {len(problems)} with a problem.")
        return 1 if problems else 0
    except Unreachable as e:
        print(f"GitHub did not answer: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
