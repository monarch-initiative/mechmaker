#!/usr/bin/env python3
"""Find news articles about past events, as leads for a curator. Standard library only.

    news_leads.py --plan plan.json --out leads.md
    news_leads.py --query '"Toledo" water microcystin' --from 2014-07-15 --to 2014-09-30 --out leads.md
    news_leads.py --wikipedia "East_Palestine,_Ohio,_train_derailment" --keyword water --out leads.md

A plan is JSON:

    {"label": "44413 East Palestine, Ohio",
     "searches": [{"query": "\\"East Palestine\\" water", "from": "2023-02-01", "to": "2023-06-30",
                   "why": "East Palestine train derailment"}],
     "wikipedia": ["East_Palestine,_Ohio,_train_derailment"],
     "keywords": ["water", "well", "bottled"],
     "place": ["East Palestine"],
     "rank": ["bottled", "drink", "well", "advisory", "spill"],
     "known": ["url:https://...", "WIKIPEDIA:..."]}

In the report, each search's leads are ranked: a title naming one of
`place` first, then by how many of `rank` it holds, then those with an
archived copy. The first --show (default 15) are listed; the rest are
folded below them.

Sources, each asked politely and each allowed to fail on its own:

  google     Google News' search feed, with after:/before: dates. Reaches
             back years. Gives title, outlet and date; its links are Google
             redirects, so the curator finds the article itself.
  gdelt      GDELT's article search. Direct article URLs, from 2017 on
             only. One request every 6 seconds; a throttled search is
             retried once, then reported. After two searches in a row
             are refused, it is not asked again in the run.
  wikipedia  The news a Wikipedia article cites: title, outlet, date, URL
             and, often, an archived copy an editor already made. Kept
             when a title holds one of the plan's keywords.

Each article with a direct URL is looked up in the Wayback Machine for an
existing snapshot near its date (read only: nothing is ever submitted for
archiving). A lead whose URL the record already cites is marked so.

The output is a Markdown report of leads. A lead is never evidence: the
curator opens the archived copy, reads it, and quotes it with the Mech's
own `just add-evidence`, citing the snapshot URL.

Exit status: 0 the report was written, 2 no source answered, 64 a usage
error.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USER_AGENT = "mechmaker-news-leads/0.1 (+https://github.com/monarch-initiative/mechmaker)"
GDELT_FIRST = dt.date(2017, 1, 1)
GDELT_PAUSE = 6.0
WAYBACK_PAUSE = 1.5
SOURCES = ("google", "gdelt", "wikipedia")
CITE = re.compile(r"\{\{\s*cite\s+(?:news|web|press release|report|magazine)\s*\|(.*?)\}\}", re.I | re.S)


def get(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def day(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


def iso_date(text: str) -> str:
    """A citation's date as YYYY-MM-DD (or YYYY-MM), when it is one of the common forms; else as given."""
    text = text.strip()
    for fmt, keep in (("%Y-%m-%d", 10), ("%d %B %Y", 10), ("%B %d, %Y", 10), ("%b %d, %Y", 10),
                      ("%d %b %Y", 10), ("%B %Y", 7), ("%Y-%m", 7)):
        try:
            return dt.datetime.strptime(text, fmt).date().isoformat()[:keep]
        except ValueError:
            continue
    return text


def norm_url(url: str) -> str:
    """A URL for comparison: no scheme, no www, no query or fragment, no trailing slash."""
    url = re.sub(r"^https?://web\.archive\.org/web/\d+[a-z_]*/", "", url)
    parts = urllib.parse.urlsplit(url if "://" in url else "https://" + url)
    host = parts.netloc.lower().removeprefix("www.")
    return host + parts.path.rstrip("/")


# ---------------------------------------------------------------- sources


def google_url(query: str, start: str, end: str) -> str:
    q = f"{query} after:{start} before:{end}"
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "en-US", "gl": "US", "ceid": "US:en"})


def parse_google(text: str) -> list[dict]:
    """Leads from a Google News feed. The title's ' - Outlet' tail is moved to outlet."""
    out = []
    for item in ET.fromstring(text).iter("item"):
        title = item.findtext("title") or ""
        source = item.find("source")
        outlet = source.text if source is not None and source.text else ""
        if outlet and title.endswith(" - " + outlet):
            title = title[: -len(" - " + outlet)]
        when = item.findtext("pubDate") or ""
        try:
            date = dt.datetime.strptime(when[:16], "%a, %d %b %Y").date().isoformat()
        except ValueError:
            date = ""
        out.append({"title": title, "outlet": outlet, "date": date, "url": "",
                    "link": item.findtext("link") or "", "source": "google"})
    return out


def gdelt_url(query: str, start: str, end: str) -> str:
    return "https://api.gdeltproject.org/api/v2/doc/doc?" + urllib.parse.urlencode({
        "query": query, "mode": "artlist", "format": "json", "maxrecords": "75", "sort": "DateDesc",
        "startdatetime": start.replace("-", "") + "000000", "enddatetime": end.replace("-", "") + "235959"})


def parse_gdelt(text: str) -> list[dict]:
    out = []
    for a in json.loads(text).get("articles", []):
        if a.get("language") not in (None, "English"):
            continue
        seen = a.get("seendate", "")
        date = f"{seen[:4]}-{seen[4:6]}-{seen[6:8]}" if len(seen) >= 8 else ""
        out.append({"title": a.get("title", ""), "outlet": a.get("domain", ""), "date": date,
                    "url": a.get("url", ""), "link": a.get("url", ""), "source": "gdelt"})
    return out


def wikipedia_url(title: str) -> str:
    return "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "parse", "page": title, "prop": "wikitext", "format": "json", "formatversion": "2",
        "redirects": "1"})


def split_pipes(body: str) -> list[str]:
    """Split a template's body at its own pipes, not those inside [[links]] or {{templates}}."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(body):
        pair = body[i:i + 2]
        if pair in ("[[", "{{"):
            depth += 1
        elif pair in ("]]", "}}") and depth:
            depth -= 1
        elif ch == "|" and depth == 0:
            parts.append(body[start:i])
            start = i + 1
    return parts + [body[start:]]


def cite_params(body: str) -> dict[str, str]:
    """The named parameters of one citation template."""
    params = {}
    for part in split_pipes(body):
        key, sep, value = part.partition("=")
        if sep:
            params[key.strip().lower()] = re.sub(r"\s+", " ", value).strip()
    return params


def parse_wikipedia(wikitext: str, article: str) -> list[dict]:
    out = []
    for m in CITE.finditer(wikitext):
        p = cite_params(m.group(1))
        if not p.get("url"):
            continue
        title = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", p.get("title", ""))
        outlet = next((p[k] for k in ("work", "website", "newspaper", "publisher") if p.get(k)), "")
        out.append({"title": html.unescape(title), "date": iso_date(p.get("date", "")), "url": p["url"],
                    "outlet": outlet,
                    "archive": p.get("archive-url", ""), "link": p["url"], "source": f"wikipedia:{article}"})
    return out


# ---------------------------------------------------------------- run


class Run:
    def __init__(self, sources: tuple[str, ...], wayback: int, pause=time.sleep):
        self.sources, self.wayback, self.pause = sources, wayback, pause
        self.problems: list[str] = []
        self.answered: set[str] = set()
        self._last_gdelt = 0.0
        self._gdelt_refusals = 0

    def search(self, s: dict) -> list[dict]:
        found = []
        if "google" in self.sources:
            try:
                found += parse_google(get(google_url(s["query"], s["from"], s["to"])))
                self.answered.add("google")
            except (urllib.error.URLError, TimeoutError, ET.ParseError) as e:
                self.problems.append(f"google, {s['query']!r}: {e}")
        if "gdelt" in self.sources and day(s["to"]) >= GDELT_FIRST and self._gdelt_refusals < 2:
            start = max(day(s["from"]), GDELT_FIRST).isoformat()
            found += self._gdelt(s["query"], start, s["to"])
        for lead in found:
            lead["why"] = s.get("why", s["query"])
        return found

    def _gdelt(self, query: str, start: str, end: str) -> list[dict]:
        for attempt in range(2):
            wait = GDELT_PAUSE * (attempt + 1) - (time.monotonic() - self._last_gdelt)
            if wait > 0:
                self.pause(wait)
            self._last_gdelt = time.monotonic()
            try:
                text = get(gdelt_url(query, start, end))
            except urllib.error.HTTPError as e:
                text = f"HTTP {e.code}: {e.reason}"
                if e.code == 429:
                    continue  # throttled: wait longer, once
                break
            except (urllib.error.URLError, TimeoutError) as e:
                self.problems.append(f"gdelt, {query!r}: {e}")
                return []
            if text.lstrip().startswith("{"):
                self.answered.add("gdelt")
                self._gdelt_refusals = 0
                return parse_gdelt(text)
        self._gdelt_refusals += 1
        self.problems.append(f"gdelt, {query!r}: {text.strip()[:120]}")
        if self._gdelt_refusals == 2:
            self.problems.append("gdelt refused two searches in a row; not asked again in this run")
        return []

    def wikipedia(self, article: str, keywords: list[str]) -> list[dict]:
        if "wikipedia" not in self.sources:
            return []
        try:
            text = json.loads(get(wikipedia_url(article)))["parse"]["wikitext"]
            self.answered.add("wikipedia")
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as e:
            self.problems.append(f"wikipedia, {article}: {e}")
            return []
        words = [k.lower() for k in keywords]
        leads = [lead for lead in parse_wikipedia(text, article)
                 if not words or any(w in lead["title"].lower() for w in words)]
        for lead in leads:
            lead["why"] = f"cited in Wikipedia's {article.replace('_', ' ')}"
        return leads

    def snapshot(self, lead: dict) -> str:
        """An existing Wayback snapshot of the lead, near its date, or ''."""
        if lead.get("archive") or not lead.get("url"):
            return lead.get("archive", "")
        if self.wayback <= 0:
            lead["archive_unchecked"] = True
            return ""
        self.wayback -= 1
        stamp = re.sub(r"\D", "", lead.get("date", ""))[:8]
        query = urllib.parse.urlencode({"url": lead["url"], **({"timestamp": stamp} if stamp else {})})
        for attempt in range(2):
            self.pause(WAYBACK_PAUSE * (attempt + 1))
            try:
                closest = json.loads(get(f"https://archive.org/wayback/available?{query}", timeout=30))
                snap = (closest.get("archived_snapshots") or {}).get("closest") or {}
                return snap.get("url", "").replace("http://", "https://", 1) if snap.get("available") else ""
            except (urllib.error.HTTPError) as e:
                if e.code != 429:
                    break
            except (urllib.error.URLError, TimeoutError, ValueError):
                break
        lead["archive_unchecked"] = True
        return ""


def dedupe(leads: list[dict], known: list[str]) -> list[dict]:
    """One lead per article: by URL where there is one, else by title. Marks leads already cited."""
    cited = {norm_url(k.removeprefix("url:")) for k in known if k.startswith(("url:", "http"))}
    out, seen = [], set()
    for lead in leads:
        key = norm_url(lead["url"]) if lead.get("url") else "title:" + lead["title"].lower().strip()
        if key in seen:
            continue
        seen.add(key)
        lead["cited"] = bool(lead.get("url")) and (
            norm_url(lead["url"]) in cited or norm_url(lead.get("archive", "") or "-") in cited)
        out.append(lead)
    return out


def score(lead: dict, place: list[str], rank: list[str]) -> tuple:
    """Higher first: names the place, holds more rank words, has an archived copy, newer."""
    title = lead["title"].lower()
    return (any(p.lower() in title for p in place), sum(w.lower() in title for w in rank),
            bool(lead.get("archive")), lead.get("date", ""))


def cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def row(lead: dict) -> str:
    title = cell(lead["title"]) or "(no title)"
    if lead.get("url"):
        title = f"[{title}]({lead['url']})"
    if lead.get("cited"):
        title += " (already cited)"
    if lead.get("archive"):
        arch = f"[snapshot]({lead['archive']})"
    elif lead.get("archive_unchecked"):
        arch = "unchecked"
    else:
        arch = "none" if lead.get("url") else "search title and outlet"
    # A Google lead's link is a long redirect: kept, but behind a short word.
    found = f"[google]({lead['link']})" if lead["source"] == "google" else cell(lead["source"])
    cells = [cell(lead.get("date", "")), cell(lead.get("outlet", "")), title, arch, found]
    return "| " + " | ".join(cells) + " |"


def report(label: str, leads: list[dict], run: Run, searches: list[dict], today: str,
           place: list[str] = (), rank: list[str] = (), show: int = 15) -> str:
    lines = [f"# News leads: {label}", "",
             f"Found {today} by `news_leads.py` from {', '.join(run.sources)}. "
             "Leads, not evidence: open the archived copy, read it, and quote it with "
             "`just add-evidence`, citing the snapshot URL. Never cite this file. A Google lead has no "
             "article URL: search its title and outlet to find the article, then its snapshot.", ""]
    if searches:
        lines += ["Searches:", ""] + [f"- {s.get('why', '')}: `{s['query']}`, {s['from']} to {s['to']}"
                                      for s in searches] + [""]
    if run.problems:
        lines += ["Not answered:", ""] + [f"- {p}" for p in run.problems] + [""]
    groups: dict[str, list[dict]] = {}
    for lead in leads:
        groups.setdefault(lead.get("why", ""), []).append(lead)
    head = ["| Date | Outlet | Title | Archived copy | Found by |", "|---|---|---|---|---|"]
    for why, group in groups.items():
        ranked = sorted(group, key=lambda x: score(x, list(place), list(rank)), reverse=True)
        lines += [f"## {why}", "", f"{len(group)} lead(s), most promising first.", ""]
        lines += head + [row(lead) for lead in ranked[:show]] + [""]
        if len(ranked) > show:
            lines += [f"<details><summary>{len(ranked) - show} more</summary>", ""]
            lines += head + [row(lead) for lead in ranked[show:]] + ["", "</details>", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--plan", type=Path, help="a JSON plan, as above")
    ap.add_argument("--query", help="one search, with --from and --to")
    ap.add_argument("--from", dest="start", help="YYYY-MM-DD")
    ap.add_argument("--to", dest="end", help="YYYY-MM-DD")
    ap.add_argument("--wikipedia", action="append", default=[], help="a Wikipedia article title; repeatable")
    ap.add_argument("--keyword", action="append", default=[],
                    help="keep Wikipedia citations whose title holds it; repeatable")
    ap.add_argument("--sources", default=",".join(SOURCES), help=f"comma-separated, of {', '.join(SOURCES)}")
    ap.add_argument("--wayback", type=int, default=40, metavar="N",
                    help="look up archived copies for at most N leads (default 40; 0: none)")
    ap.add_argument("--show", type=int, default=15, help="leads listed per search before the rest are folded")
    ap.add_argument("--out", type=Path, required=True, help="where to write the Markdown report")
    args = ap.parse_args(argv)

    plan = json.loads(args.plan.read_text(encoding="utf-8")) if args.plan else {}
    searches = list(plan.get("searches", []))
    if args.query:
        if not (args.start and args.end):
            ap.error("--query needs --from and --to")
        searches.append({"query": args.query, "from": args.start, "to": args.end, "why": args.query})
    articles = list(plan.get("wikipedia", [])) + args.wikipedia
    sources = tuple(s for s in args.sources.split(",") if s)
    if not (searches or articles) or any(s not in SOURCES for s in sources):
        ap.error("give a --plan, a --query, or a --wikipedia title, and sources from: " + ", ".join(SOURCES))
    for s in searches:
        day(s["from"]), day(s["to"])

    run = Run(sources, wayback=args.wayback)
    leads: list[dict] = []
    for s in searches:
        leads += run.search(s)
    for article in articles:
        leads += run.wikipedia(article, list(plan.get("keywords", [])) + args.keyword)
    leads = dedupe(leads, list(plan.get("known", [])))
    for lead in leads:
        lead["archive"] = run.snapshot(lead)
    if not run.answered:
        print("No source answered:\n  " + "\n  ".join(run.problems), file=sys.stderr)
        return 2
    args.out.parent.mkdir(parents=True, exist_ok=True)
    text = report(plan.get("label", "search"), leads, run, searches, dt.date.today().isoformat(),
                  place=plan.get("place", []), rank=plan.get("rank", []), show=args.show)
    args.out.write_text(text, encoding="utf-8")
    print(f"Wrote {len(leads)} lead(s) to {args.out}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
