"""Find recent papers that may bear on this Mech's records.

    python -m <slug>.literature --source MED --days 7
    python -m <slug>.literature --source PPR --date-from 2026-01-01 --date-to 2026-01-31

Queries Europe PMC with the terms in conf/literature_scan.yaml, matches each
paper to records by name, marks papers the records already cite, and writes
build/literature/packet.json and packet.md for the literature-scan agent.
No model runs here. Adapted from DisMech's literature and preprint scans.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import urllib.parse
import urllib.request

import yaml

from .paths import BUILD_DIR, REPO_ROOT
from .validate import _evidence_items, iter_records, load

API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
CONFIG = REPO_ROOT / "conf" / "literature_scan.yaml"
OUT = BUILD_DIR / "literature"


def _quote(term: str) -> str:
    return '"' + term.replace('"', "") + '"'


def build_query(cfg: dict, source: str, start: str, end: str) -> str:
    context = " OR ".join(f"TITLE_ABS:{_quote(t)}" for t in cfg.get("context_terms") or [])
    exclude = " OR ".join(f"TITLE:{_quote(t)}" for t in cfg.get("exclude_terms") or [])
    q = f"SRC:{source} AND FIRST_PDATE:[{start} TO {end}]"
    if context:
        q += f" AND ({context})"
    if exclude:
        q += f" NOT ({exclude})"
    return q


def search(query: str, limit: int) -> list[dict]:
    results: list[dict] = []
    cursor = "*"
    while len(results) < limit:
        params = urllib.parse.urlencode({
            "query": query, "format": "json", "resultType": "core",
            "pageSize": min(100, limit - len(results)), "cursorMark": cursor,
        })
        with urllib.request.urlopen(f"{API}?{params}", timeout=60) as resp:
            data = json.load(resp)
        page = data.get("resultList", {}).get("result", [])
        results.extend(page)
        nxt = data.get("nextCursorMark")
        if not page or not nxt or nxt == cursor:
            break
        cursor = nxt
    return results[:limit]


def _strip_tags(text: str) -> str:
    """Plain text: Europe PMC escapes markup in titles and abstracts."""
    text = html.unescape(html.unescape(text or ""))
    return " ".join(re.sub(r"<[^>]+>", " ", text).split())


def record_names(cfg: dict) -> dict[str, list[str]]:
    fields = cfg.get("name_fields") or ["name"]
    min_len = int(cfg.get("min_name_length", 5))
    stop = {s.lower() for s in cfg.get("stop_names") or []}
    names: dict[str, list[str]] = {}
    for path in iter_records():
        data = load(path) or {}
        found = {path.stem.replace("_", " ")}
        for f in fields:
            v = data.get(f)
            for item in v if isinstance(v, list) else [v]:
                if isinstance(item, str):
                    found.add(item)
        keep = [n for n in found if len(n) >= min_len and n.lower() not in stop]
        names[str(path.relative_to(REPO_ROOT))] = sorted(keep, key=len, reverse=True)
    return names


def cited_references() -> set[str]:
    cited: set[str] = set()
    for path in iter_records():
        for _, ev in _evidence_items(load(path) or {}):
            cited.add(str(ev.get("reference", "")).upper())
    return cited


def paper_id(r: dict) -> str:
    if r.get("source") == "PPR":
        return f"PPR:{r.get('id')}"
    if r.get("pmid"):
        return f"PMID:{r['pmid']}"
    return f"DOI:{r['doi']}" if r.get("doi") else f"{r.get('source')}:{r.get('id')}"


def match(r: dict, names: dict[str, list[str]]) -> list[dict]:
    title = _strip_tags(r.get("title") or "").lower()
    abstract = _strip_tags(r.get("abstractText") or "").lower()
    hits = []
    for path, ns in names.items():
        for n in ns:
            pat = r"\b" + re.escape(n.lower()) + r"\b"
            if re.search(pat, title):
                hits.append({"record": path, "name": n, "where": "title", "score": 4 + len(n) / 20})
                break
            if re.search(pat, abstract):
                hits.append({"record": path, "name": n, "where": "abstract", "score": 1 + len(n) / 20})
                break
    return sorted(hits, key=lambda h: -h["score"])[:5]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source", choices=["MED", "PPR"], default="MED")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--date-from")
    parser.add_argument("--date-to")
    parser.add_argument("--max-records", type=int)
    args = parser.parse_args(argv)
    if bool(args.date_from) != bool(args.date_to):
        parser.error("--date-from and --date-to go together")
    cfg = yaml.safe_load(CONFIG.read_text()) or {}
    end = args.date_to or dt.date.today().isoformat()
    start = args.date_from or (dt.date.today() - dt.timedelta(days=args.days)).isoformat()
    limit = args.max_records or int(cfg.get("max_records", 200))
    query = build_query(cfg, args.source, start, end)
    papers = search(query, limit)
    names = record_names(cfg)
    cited = cited_references()
    rows = []
    for r in papers:
        pid = paper_id(r)
        rows.append({
            "id": pid,
            "title": _strip_tags(r.get("title") or ""),
            "date": r.get("firstPublicationDate"),
            "venue": (r.get("journalInfo") or {}).get("journal", {}).get("title")
            or (r.get("bookOrReportDetails") or {}).get("publisher"),
            "doi": r.get("doi"),
            "link": f"https://europepmc.org/article/{r.get('source')}/{r.get('id')}",
            "preprint": r.get("source") == "PPR",
            "already_cited": pid.upper() in cited,
            "matches": match(r, names),
            "abstract": _strip_tags(r.get("abstractText") or ""),
        })
    rows.sort(key=lambda x: (x["already_cited"], -(x["matches"][0]["score"] if x["matches"] else 0)))
    OUT.mkdir(parents=True, exist_ok=True)
    packet = {"query": query, "source": args.source, "from": start, "to": end, "papers": rows}
    (OUT / "packet.json").write_text(json.dumps(packet, indent=2, ensure_ascii=False))
    lines = [f"# Literature packet ({args.source}, {start} to {end})", "", f"Query: `{query}`",
             f"{len(rows)} paper(s); {sum(bool(x['matches']) for x in rows)} match a record.", ""]
    for x in rows:
        lines += [f"## {x['id']}: {x['title']}", "",
                  f"- date: {x['date']}; venue: {x['venue']}; DOI: {x['doi']}; link: {x['link']}",
                  f"- preprint: {x['preprint']}; already cited: {x['already_cited']}",
                  "- matches: " + (", ".join(f"{m['record']} ({m['name']}, {m['where']})"
                                             for m in x["matches"]) or "none"),
                  "", x["abstract"], ""]
    (OUT / "packet.md").write_text("\n".join(lines))
    print(f"{len(rows)} paper(s) -> {(OUT / 'packet.md').relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
