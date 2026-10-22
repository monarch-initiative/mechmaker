#!/usr/bin/env python3
"""Read an SSSOM mapping set (https://mapping-commons.github.io/sssom/): what it maps, and the rows
that name an entity. Standard library only.

    sssom_sets.py summary <file-or-url>                  # its metadata, and what it maps to what
    sssom_sets.py find <file-or-url> MONDO:0007739       # the rows with this CURIE on either side
    sssom_sets.py find <file-or-url> "huntington"        # the rows whose labels hold every word
    sssom_sets.py find <file-or-url> MONDO:0007739 --to OMIM   # only rows to (or from) OMIM

A set is a TSV file whose metadata sits above the table in `#` lines (or a
gzipped one, .gz). A URL is downloaded once and kept for a week in
$XDG_CACHE_HOME/mechmaker/sssom (~/.cache/mechmaker/sssom); --refresh
downloads it again.

`summary` gives the metadata (id, version, license, title, how many
prefixes the curie_map declares), the number of rows, and counts of each
(subject prefix, predicate, object prefix) and of each justification.
`find` matches a CURIE exactly, on either side, or words in the labels,
at the start of a word and ignoring case.

Add --json for output a program reads.

Exit status: 0 found, 1 nothing matched, 2 the set could not be read, 64 a usage error.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path

USER_AGENT = "mechmaker-sssom-sets/0.1 (+https://github.com/monarch-initiative/mechmaker)"
MAX_AGE = 7 * 24 * 3600
CURIE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*:\S+$")


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


def fetch(source: str, refresh: bool = False) -> bytes:
    """The set's bytes: a local file, or a URL from the cache when the copy is fresh."""
    if not source.startswith(("http://", "https://")):
        try:
            return Path(source).read_bytes()
        except OSError as e:
            raise Unreachable(f"{source}: {e}") from e
    path = cache_dir() / "sssom" / (hashlib.sha256(source.encode()).hexdigest()[:16] + ".tsv")
    if path.exists() and not refresh and time.time() - path.stat().st_mtime < MAX_AGE:
        return path.read_bytes()
    try:
        body = download(source)
    except Unreachable:
        if not path.exists():
            raise
        age = (time.time() - path.stat().st_mtime) / 86400
        print(f"warning: could not download {source}; using a copy {age:.0f} days old", file=sys.stderr)
        return path.read_bytes()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_bytes(body)
    tmp.replace(path)
    return body


def parse(body: bytes) -> tuple[dict, list[dict]]:
    """The metadata (top-level keys, and curie_map's prefixes) and the rows; ValueError if not SSSOM."""
    if body[:2] == b"\x1f\x8b":
        body = gzip.decompress(body)
    text = body.decode("utf-8-sig")
    meta: dict = {}
    table: list[str] = []
    key = None
    lines = text.splitlines()
    # Some sets write "#key: value", others "# key: value": strip what this one uses.
    pad = 2 if next((x for x in lines if x.startswith("#")), "").startswith("# ") else 1
    for line in lines:
        if not line.startswith("#"):
            table.append(line)
            continue
        inner = line[pad:]
        m = re.match(r"^([A-Za-z_]+):\s*(.*)$", inner)
        if m:
            key, value = m.group(1), m.group(2).strip().strip("'\"")
            meta[key] = value if value else ({} if key == "curie_map" else [])
        elif key == "curie_map" and ":" in inner:
            prefix, _, uri = inner.strip().partition(":")
            meta["curie_map"][prefix.strip().strip("'\"")] = uri.strip().strip("'\"")
        elif key and inner.strip().startswith("- ") and isinstance(meta.get(key), list):
            meta[key].append(inner.strip()[2:].strip("'\""))
    rows = list(csv.DictReader(io.StringIO("\n".join(table)), delimiter="\t"))
    if rows and not {"subject_id", "predicate_id", "object_id"} <= set(rows[0]):
        raise ValueError("not an SSSOM table: no subject_id, predicate_id and object_id columns")
    return meta, rows


def prefix(curie: str) -> str:
    return curie.partition(":")[0] if ":" in curie else ""


def summary(meta: dict, rows: list[dict]) -> dict:
    triples = Counter((prefix(r.get("subject_id", "")), r.get("predicate_id", ""),
                       prefix(r.get("object_id", ""))) for r in rows)
    justifications = Counter(r.get("mapping_justification", "") for r in rows)
    keys = ("mapping_set_id", "mapping_set_version", "mapping_set_title", "license", "mapping_date",
            "publication_date")
    return {
        **{k: meta[k] for k in keys if meta.get(k)},
        "prefixes": len(meta.get("curie_map") or {}),
        "rows": len(rows),
        "maps": [{"subject": s, "predicate": p, "object": o, "rows": n}
                 for (s, p, o), n in triples.most_common()],
        "justifications": dict(justifications.most_common()),
    }


def labels(r: dict) -> str:
    return f"{r.get('subject_label', '')} {r.get('object_label', '')}".lower()


def find(rows: list[dict], term: str, to: str | None = None) -> list[dict]:
    """Rows with the CURIE on either side, or whose labels hold every word; to: the other side's prefix."""
    if CURIE.match(term):
        hits = [r for r in rows if term in (r.get("subject_id"), r.get("object_id"))]
    else:
        patterns = [re.compile(r"(?<![a-z0-9])" + re.escape(w.lower())) for w in term.split()]
        hits = [r for r in rows if all(p.search(labels(r)) for p in patterns)]
    if to:
        hits = [r for r in hits
                if any(prefix(i).lower() == to.lower() and i != term
                       for i in (r.get("subject_id", ""), r.get("object_id", "")))]
    return hits


def show_row(r: dict) -> str:
    def side(name: str) -> str:
        label = r.get(f"{name}_label")
        return f"{r.get(f'{name}_id', '')} ({label})" if label else r.get(f"{name}_id", "")

    mod = f" {r['predicate_modifier']}" if r.get("predicate_modifier") else ""
    how = r.get("mapping_justification", "") + (f", {r['confidence']}" if r.get("confidence") else "")
    return f"{side('subject')}{mod} {r.get('predicate_id', '')} {side('object')}  [{how}]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("source", help="an SSSOM TSV file or URL (.gz too)")
    common.add_argument("--refresh", action="store_true", help="download the set again")
    common.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("summary", help="the set's metadata, and what it maps to what", parents=[common])
    f = sub.add_parser("find", help="rows naming a CURIE, or with every word in their labels",
                       parents=[common])
    f.add_argument("term", help='a CURIE, or words such as "huntington disease"')
    f.add_argument("--to", metavar="PREFIX", help="only rows whose other side has this prefix")
    f.add_argument("--limit", type=int, default=50, help="at most this many (0: all)")
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return 64 if e.code else 0
    try:
        meta, rows = parse(fetch(args.source, args.refresh))
    except (Unreachable, ValueError, UnicodeDecodeError, gzip.BadGzipFile) as e:
        print(f"could not read the set: {e}", file=sys.stderr)
        return 2

    if args.command == "summary":
        s = summary(meta, rows)
        if args.json:
            print(json.dumps(s, indent=1))
            return 0
        for k, v in s.items():
            if k not in ("maps", "justifications"):
                print(f"{k}: {v}")
        print("maps (subject prefix, predicate, object prefix):")
        for m in s["maps"][:40]:
            print(f"  {m['rows']:>8}  {m['subject']} {m['predicate']} {m['object']}")
        if len(s["maps"]) > 40:
            print(f"  ... {len(s['maps']) - 40} more (--json lists them)")
        print("justifications:")
        for j, n in s["justifications"].items():
            print(f"  {n:>8}  {j or '(none)'}")
        return 0

    hits = find(rows, args.term, args.to)
    shown = hits[:args.limit] if args.limit else hits
    if args.json:
        print(json.dumps(shown, indent=1))
    for r in [] if args.json else shown:
        print(show_row(r))
    if len(shown) < len(hits) and not args.json:
        print(f"... {len(hits) - len(shown)} more (--limit 0 lists them)")
    if not hits:
        print(f"no row names {args.term!r}", file=sys.stderr)
    return 0 if hits else 1


if __name__ == "__main__":
    sys.exit(main())
