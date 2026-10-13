"""News about records: leads for curators, from past news and from new stories.

    python -m <slug>.news plan RECORD                 # the searches conf/news.yaml makes for a record
    python -m <slug>.news leads RECORD                # search, and write curation/news/<stem>.md
    python -m <slug>.news leads --plan plan.json --out leads.md
    python -m <slug>.news watch [--seen FILE]         # new stories for records: build/news/watch.md

RECORD is a record's filename stem or its path. conf/news.yaml says which
record fields name a record in the news, where its events and their dates
are, and which words to search with; the record supplies the rest. A plan is
JSON, and can be written or edited by hand:

    {"label": "...", "searches": [{"query": "...", "from": "YYYY-MM-DD", "to": "YYYY-MM-DD",
     "why": "...", "avoid": ["..."]}], "wikipedia": ["Article_title"], "keywords": ["..."],
     "place": ["..."], "rank": ["..."], "known": ["url:https://..."]}

`leads` works in two steps. First it counts: each search runs once, and its
number of hits is printed. A Google News search answers at most about 100
items, so a search at that cap is too broad: its date window is split in two
and both halves are searched, up to `max_splits` times, never below a month. Then it retrieves:
each search keeps its `per_search` most promising leads (the record's name
in the title, more `rank` words, an archived copy already known, then
newer first, or, for a recorded event, nearer its start; in a search for
new events, a title about one the record already has ranks lower), says
how many it left out, and looks up an existing
Wayback snapshot for those it keeps, and only those.

Sources: Google News' search feed (title, outlet and date; its links are
redirects, so the curator finds the article itself), the news a Wikipedia
article cites (with URLs, and often an archived copy), and, if
conf/news.yaml asks, GDELT (article URLs, from 2017; often refuses).

`watch` reads, for up to `watch.max_records` records a run (the next run
takes the next ones), a Google News search feed of the record's words for
the last `watch.days` days, keeping items whose title holds a domain word
(`watch.title_words`, by default the topic, discovery and rank words), and
the feeds `watch.feeds` names, matching their items to records by name. Items listed in --seen (a file holding
earlier watch reports) are skipped, so a story is reported once. It writes
build/news/watch.md and watch.json when there is something new.

Every lead is a lead, never evidence. Leads files sit in curation/news/ and
are never cited: the curator opens the archived copy, reads it, and quotes
it with `just add-evidence`, citing the snapshot URL.

Exit status: 0 done, 1 a record or plan is missing, 2 no source answered.
"""

from __future__ import annotations

import argparse
import calendar
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

import yaml

from .paths import BUILD_DIR, RECORDS_DIR, REPO_ROOT, SLUG
from .validate import iter_records, load

CONF = REPO_ROOT / "conf" / "news.yaml"
NEWS_DIR = REPO_ROOT / "curation" / "news"
WATCH_DIR = BUILD_DIR / "news"
USER_AGENT = f"{SLUG}-news/0.2 (+https://github.com/monarch-initiative/mechmaker)"
SOURCES = ("google", "gdelt", "wikipedia")
GOOGLE_CAP = 100  # Google News' search feed answers about this many items at most
MIN_SPLIT_DAYS = 30  # a window this short is not split again, even at the cap
GDELT_FIRST = dt.date(2017, 1, 1)
GDELT_PAUSE = 6.0
WAYBACK_PAUSE = 1.5
CITE = re.compile(r"\{\{\s*cite\s+(?:news|web|press release|report|magazine)\s*\|(.*?)\}\}", re.I | re.S)
SEEN = re.compile(r"<!-- seen: (\S+) -->")
# watch() ends its problems with this when it asked and no source answered; the command then exits 2.
NONE_ANSWERED = "no source answered"
# GitHub refuses an issue body over 65,536 characters; the watch report stays under it.
REPORT_LIMIT = 60_000
OPEN, CLOSE = "{" * 2, "}" * 2  # a wiki template's braces, spelled so no template engine reads them

DEFAULTS = {
    "subject": {"fields": ["name"], "qualifier_fields": [], "qualifier_map": {}},
    "topic": [],
    "events": {"field": "", "name": "name", "start": "start_date", "end": "end_date", "terms": [],
               "before_days": 30, "after_days": 365},
    "discovery": {"years": 3, "words": [], "exclude": []},
    "wikipedia": {"from_references": True, "keywords": []},
    "rank": [],
    "sources": ["google", "wikipedia"],
    "per_search": 15,
    "max_splits": 4,
    "wayback": 60,
    "watch": {"google": True, "days": 7, "max_records": 50, "feeds": [], "title_words": None},
}


def settings(path: Path = CONF) -> dict:
    """conf/news.yaml over the defaults, one level deep."""
    conf = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
    out = {}
    for key, default in DEFAULTS.items():
        value = (conf or {}).get(key, default)
        out[key] = {**default, **(value or {})} if isinstance(default, dict) else value
    return out


def get(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def day(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


def first_day(text) -> dt.date:
    parts = [int(x) for x in str(text).split("-")]
    return dt.date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)


def last_day(text) -> dt.date:
    parts = [int(x) for x in str(text).split("-")]
    if len(parts) == 3:
        return dt.date(*parts)
    month = parts[1] if len(parts) > 1 else 12
    return dt.date(parts[0], month, calendar.monthrange(parts[0], month)[1])


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


# ---------------------------------------------------------------- record fields


def values(obj, path: str) -> list[str]:
    """The values at a dotted field path, with lists flattened along the way: incidents.name."""
    items = [obj]
    for part in path.split(".") if path else []:
        nxt = []
        for item in items:
            value = item.get(part) if isinstance(item, dict) else None
            nxt += value if isinstance(value, list) else [] if value is None else [value]
        items = nxt
    return [str(v) for v in items if isinstance(v, (str, int, float)) and str(v).strip()]


def references(obj) -> list[str]:
    if isinstance(obj, dict):
        found = [obj["reference"]] if isinstance(obj.get("reference"), str) else []
        return found + [r for v in obj.values() for r in references(v)]
    if isinstance(obj, list):
        return [r for v in obj for r in references(v)]
    return []


def quoted(word: str) -> str:
    """A phrase of several words is quoted, so it is searched whole."""
    return f'"{word}"' if " " in word and not word.startswith('"') else word


def any_of(words: list[str]) -> str:
    """(a OR b OR "two words")."""
    words = list(dict.fromkeys(quoted(w) for w in words if w))
    return "(" + " OR ".join(words) + ")" if len(words) > 1 else (words[0] if words else "")


def subject(data: dict, conf: dict) -> tuple[str, list[str]]:
    """The words that name a record (the first field that is set) and those that qualify it."""
    s = conf["subject"]
    name = next((v for f in s["fields"] for v in values(data, f)), "")
    quals = []
    for f in s["qualifier_fields"]:
        table = (s.get("qualifier_map") or {}).get(f, {})
        quals += [str(table.get(v, v)) for v in values(data, f)]
    return name, quals


def event_terms(event: dict, conf: dict) -> list[str]:
    """Each event's search words: a field's values, or with a map, the words each value maps to."""
    words = []
    for t in conf["events"]["terms"]:
        table = t.get("map")
        for v in values(event, t["field"]):
            if not table:
                words.append(v)
                continue
            mapped = table.get(v) or []
            words += mapped if isinstance(mapped, list) else [mapped]
    return words


def plan(data: dict, conf: dict, today: dt.date | None = None) -> dict:
    """The searches for one record, read from conf/news.yaml."""
    today = today or dt.date.today()
    name, quals = subject(data, conf)
    where = " ".join(f'"{w.strip(chr(34))}"' for w in [name, *quals] if w)
    topic = " ".join(quoted(w) for w in conf["topic"])
    base = " ".join(x for x in (where, topic) if x)
    ev = conf["events"]
    searches, avoid = [], []
    for event in [e for e in values_raw(data, ev["field"]) if isinstance(e, dict)] if ev["field"] else []:
        start = (values(event, ev["start"]) or [""])[0]
        if not start:
            continue
        begin, end = first_day(start), last_day((values(event, ev["end"]) or [start])[0])
        terms = event_terms(event, conf)
        avoid += [t for t in terms if len(t) > 3]
        searches.append({
            "query": f"{base} {any_of(terms)}".strip(),
            "from": (begin - dt.timedelta(days=int(ev["before_days"]))).isoformat(),
            "to": min(max(end, begin + dt.timedelta(days=int(ev["after_days"]))), today).isoformat(),
            "why": f"Recorded event: {(values(event, ev['name']) or ['(unnamed)'])[0]}",
            "near": begin.isoformat()})
    disc = conf["discovery"]
    exclude = " ".join(f"-{quoted(w)}" for w in disc["exclude"])
    for year in range(today.year - int(disc["years"]) + 1, today.year + 1) if base else []:
        searches.append({
            "query": " ".join(x for x in (base, any_of(disc["words"]), exclude) if x),
            "from": f"{year}-01-01", "to": min(dt.date(year, 12, 31), today).isoformat(),
            "why": f"New events in {year}", "avoid": sorted(set(avoid))})
    refs = references(data)
    wiki = sorted({r.split(":", 1)[1] for r in refs if r.startswith("WIKIPEDIA:")}) \
        if conf["wikipedia"]["from_references"] else []
    rank = [w.strip('"') for w in [*conf["rank"], *disc["words"]]]
    for event in [e for e in values_raw(data, ev["field"]) if isinstance(e, dict)] if ev["field"] else []:
        rank += event_terms(event, conf)
    return {"label": str(data.get("name") or data.get("id") or ""), "searches": searches, "wikipedia": wiki,
            "keywords": list(conf["wikipedia"]["keywords"]), "place": [name] if name else [],
            "rank": list(dict.fromkeys(rank)), "known": sorted(set(refs))}


def values_raw(obj, path: str) -> list:
    """Like values, but keeps dicts: the events themselves."""
    items = [obj]
    for part in path.split("."):
        nxt = []
        for item in items:
            value = item.get(part) if isinstance(item, dict) else None
            nxt += value if isinstance(value, list) else [] if value is None else [value]
        items = nxt
    return items


# ---------------------------------------------------------------- sources


def google_url(query: str, start: str = "", end: str = "", when: str = "") -> str:
    q = query + (f" after:{start} before:{end}" if start else "") + (f" when:{when}" if when else "")
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
        out.append({"title": title, "outlet": outlet, "date": rss_date(item.findtext("pubDate") or ""),
                    "url": "", "link": item.findtext("link") or "", "guid": item.findtext("guid") or "",
                    "source": "google"})
    return out


def rss_date(when: str) -> str:
    try:
        return dt.datetime.strptime(when.strip()[:16], "%a, %d %b %Y").date().isoformat()
    except ValueError:
        return ""


def parse_feed(text: str, name: str) -> list[dict]:
    """Items from any RSS 2.0 or Atom feed: title, summary, link, date, guid."""
    out = []
    root = ET.fromstring(text)
    atom = "{http://www.w3.org/2005/Atom}"
    for item in root.iter("item"):
        link = item.findtext("link") or ""
        out.append({"title": item.findtext("title") or "", "summary": item.findtext("description") or "",
                    "link": link, "url": link, "date": rss_date(item.findtext("pubDate") or ""),
                    "guid": item.findtext("guid") or link, "outlet": name, "source": name})
    for entry in root.iter(f"{atom}entry"):
        node = entry.find(f"{atom}link")
        link = node.get("href", "") if node is not None else ""
        out.append({"title": entry.findtext(f"{atom}title") or "",
                    "summary": entry.findtext(f"{atom}summary") or "", "link": link, "url": link,
                    "date": (entry.findtext(f"{atom}updated") or "")[:10],
                    "guid": entry.findtext(f"{atom}id") or link, "outlet": name, "source": name})
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
    """Split a wiki template's body at its own pipes, not those inside links or nested templates."""
    parts, depth, start = [], 0, 0
    for i, ch in enumerate(body):
        pair = body[i:i + 2]
        if pair in ("[[", OPEN):
            depth += 1
        elif pair in ("]]", CLOSE) and depth:
            depth -= 1
        elif ch == "|" and depth == 0:
            parts.append(body[start:i])
            start = i + 1
    return parts + [body[start:]]


def cite_params(body: str) -> dict[str, str]:
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
                    "outlet": outlet, "archive": p.get("archive-url", ""), "link": p["url"],
                    "source": f"wikipedia:{article}"})
    return out


# ---------------------------------------------------------------- leads: count, then retrieve


class Run:
    def __init__(self, sources, wayback: int, max_splits: int = 4, pause=time.sleep, log=None):
        self.sources, self.wayback, self.max_splits, self.pause = tuple(sources), wayback, max_splits, pause
        self.log = log or (lambda text: print(text, file=sys.stderr))
        self.problems: list[str] = []
        self.answered: set[str] = set()
        self.counts: list[str] = []
        self._last_gdelt = 0.0
        self._gdelt_refusals = 0

    def google(self, s: dict, depth: int = 0) -> list[dict]:
        """One search's Google leads. A search at the cap is split in two by date, while it can be."""
        try:
            found = parse_google(get(google_url(s["query"], s["from"], s["to"])))
            self.answered.add("google")
        except (urllib.error.URLError, TimeoutError, ET.ParseError) as e:
            self.problems.append(f"google, {s['query']!r}: {e}")
            return []
        start, end = day(s["from"]), day(s["to"])
        note = f"{len(found):>4}  {s['from']} to {s['to']}  {s.get('why', '')}"
        if len(found) >= GOOGLE_CAP and depth < self.max_splits and (end - start).days > MIN_SPLIT_DAYS:
            middle = start + (end - start) / 2
            self.log(note + "  (at the cap: split in two)")
            self.counts.append(note + " (at the cap: split in two)")
            after = (middle + dt.timedelta(days=1)).isoformat()
            halves = [{**s, "to": middle.isoformat()}, {**s, "from": after}]
            return [lead for half in halves for lead in self.google(half, depth + 1)]
        capped = "  (at the cap: narrow the query to see the rest)" if len(found) >= GOOGLE_CAP else ""
        self.log(note + capped)
        self.counts.append(note + capped.replace("  ", " "))
        return found

    def search(self, s: dict) -> list[dict]:
        found = self.google(s) if "google" in self.sources else []
        if "gdelt" in self.sources and day(s["to"]) >= GDELT_FIRST and self._gdelt_refusals < 2:
            start = max(day(s["from"]), GDELT_FIRST).isoformat()
            found += self._gdelt(s["query"], start, s["to"])
        for lead in found:
            lead["why"] = s.get("why", s["query"])
            lead["avoid"] = s.get("avoid", [])
            lead["near"] = s.get("near", "")
        return found

    def _gdelt(self, query: str, start: str, end: str) -> list[dict]:
        text = ""
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
        cited = parse_wikipedia(text, article)
        words = [k.lower() for k in keywords]
        leads = [lead for lead in cited if not words or any(w in lead["title"].lower() for w in words)]
        note = f"{len(leads):>4}  of {len(cited)} citations, after the keyword filter  Wikipedia: {article}"
        self.log(note)
        self.counts.append(note)
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
            except urllib.error.HTTPError as e:
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


def holds(title: str, word: str) -> bool:
    """The title holds the word at the start of one of its words: test finds testing, not fastest."""
    return re.search(r"(?<![a-z0-9])" + re.escape(word.lower()), title) is not None


def when(lead: dict) -> int:
    """How a lead's date ranks: newer first, or, in a search for a recorded event, nearer its start
    first (early reports carry an event's facts). An undated lead comes last."""
    try:
        date = first_day(lead.get("date", "")[:10])
    except ValueError:
        return -10**7
    near = lead.get("near")
    return -abs((date - first_day(near)).days) if near else date.toordinal()


def score(lead: dict, place: list[str], rank: list[str]) -> tuple:
    """Higher first: names the place, not about an event the record has (in a search for new ones),
    holds more rank words, has an archived copy, then by date (see when)."""
    title = lead["title"].lower()
    about_known = any(a.lower() in title for a in lead.get("avoid", []))
    return (any(p.lower() in title for p in place), not about_known,
            sum(holds(title, w) for w in rank), bool(lead.get("archive")), when(lead))


def select(leads: list[dict], place: list[str], rank: list[str], per_search: int) -> dict[str, tuple]:
    """Each search's most promising leads, and how many it found: why -> (kept, found)."""
    groups: dict[str, list[dict]] = {}
    for lead in leads:
        groups.setdefault(lead.get("why", ""), []).append(lead)
    return {why: (sorted(g, key=lambda x: score(x, place, rank), reverse=True)[:per_search], len(g))
            for why, g in groups.items()}


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
    found = f"[google]({lead['link']})" if lead["source"] == "google" else cell(lead["source"])
    cells = [cell(lead.get("date", "")), cell(lead.get("outlet", "")), title, arch, found]
    return "| " + " | ".join(cells) + " |"


def report(label: str, chosen: dict[str, tuple], run: Run, searches: list[dict], today: str) -> str:
    lines = [f"# News leads: {label}", "",
             f"Found {today} by `just news-leads` from {', '.join(run.sources)}. "
             "Leads, not evidence: open the archived copy, read it, and quote it with "
             "`just add-evidence`, citing the snapshot URL. Never cite this file. A Google lead has no "
             "article URL: search its title and outlet to find the article, then its snapshot.", ""]
    if searches:
        lines += ["Searches:", ""] + [f"- {s.get('why', '')}: `{s['query']}`, {s['from']} to {s['to']}"
                                      for s in searches] + [""]
    if run.counts:
        lines += ["Hits per search:", "", "```text", *run.counts, "```", ""]
    if run.problems:
        lines += ["Not answered:", ""] + [f"- {p}" for p in run.problems] + [""]
    head = ["| Date | Outlet | Title | Archived copy | Found by |", "|---|---|---|---|---|"]
    for why, (kept, found) in chosen.items():
        left = f" {found - len(kept)} lower-ranked left out." if found > len(kept) else ""
        lines += [f"## {why}", "", f"{len(kept)} of {found} lead(s), most promising first.{left}", ""]
        lines += head + [row(lead) for lead in kept] + [""]
    return "\n".join(lines)


def leads(the_plan: dict, conf: dict, out: Path, today: str | None = None, pause=time.sleep) -> int:
    run = Run(conf["sources"], wayback=int(conf["wayback"]), max_splits=int(conf["max_splits"]), pause=pause)
    found: list[dict] = []
    run.log("Counting hits:")
    for s in the_plan.get("searches", []):
        found += run.search(s)
    for article in the_plan.get("wikipedia", []):
        found += run.wikipedia(article, the_plan.get("keywords", []))
    found = dedupe(found, the_plan.get("known", []))
    chosen = select(found, the_plan.get("place", []), the_plan.get("rank", []), int(conf["per_search"]))
    for kept, _ in chosen.values():
        for lead in kept:
            lead["archive"] = run.snapshot(lead)
    if not run.answered:
        print("No source answered:\n  " + "\n  ".join(run.problems), file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    text = report(the_plan.get("label", "search"), chosen, run, the_plan.get("searches", []),
                  today or dt.date.today().isoformat())
    out.write_text(text, encoding="utf-8")
    kept = sum(len(k) for k, _ in chosen.values())
    print(f"Wrote {out.relative_to(REPO_ROOT) if out.is_relative_to(REPO_ROOT) else out}: "
          f"{kept} of {len(found)} leads, in {len(chosen)} section(s).")
    return 0


# ---------------------------------------------------------------- watch


def item_key(item: dict) -> str:
    """An item's identity across runs. A link keeps its query: many feeds tell stories apart by it
    (`?p=123`, `release.aspx?id=77`). Quoted, so no `>` can close the seen marker it goes in."""
    key = item.get("guid") or item.get("link") or item.get("title", "")
    if not key.startswith("http"):
        return re.sub(r"\s+", "", key)
    query = urllib.parse.urlsplit(key).query
    return urllib.parse.quote(norm_url(key) + (f"?{query}" if query else ""), safe=":/?&=%+,;~")


def names_record(text: str, name: str) -> bool:
    pattern = r"(?<!\w)" + re.escape(name.lower()) + r"(?!\w)"
    return len(name) >= 4 and re.search(pattern, text.lower()) is not None


def watch_batch(records: list[Path], conf: dict, today: dt.date) -> list[Path]:
    """This run's records: max_records of them, starting where the week's turn puts it."""
    size = int(conf["watch"]["max_records"])
    if not records or size <= 0 or size >= len(records):
        return records
    start = (today.isocalendar()[1] * size) % len(records)
    return (records + records)[start:start + size]


def watch(conf: dict, seen: set[str], today: dt.date | None = None, records: list[Path] | None = None,
          pause=time.sleep) -> tuple[list[dict], list[str]]:
    """New items for records: [{record, path, items}], and the problems met."""
    today = today or dt.date.today()
    w = conf["watch"]
    every = records if records is not None else iter_records()
    found: dict[str, dict] = {}
    problems: list[str] = []
    asked = answered = 0
    named: list[tuple[Path, dict, str, list[str]]] = []
    for path in every:
        data = load(path)
        if isinstance(data, dict):
            name, quals = subject(data, conf)
            if name:
                named.append((path, data, name, quals))
    by_path = {p: (d, n, q) for p, d, n, q in named}

    def add(path: Path, item: dict) -> None:
        key = item_key(item)
        if key in seen:
            return
        seen.add(key)
        data, name, _ = by_path[path]
        label = str(data.get("name") or name)
        entry = found.setdefault(str(path), {"record": label, "path": path, "items": []})
        entry["items"].append({**item, "key": key})

    # Google matches a search's words anywhere in a story; a title that holds none of the domain's
    # words is rarely about it. title_words: [] keeps every item.
    words = w.get("title_words")
    words = [x.lower() for x in (words if words is not None else
                                 [*conf["topic"], *conf["discovery"]["words"], *conf["rank"]])]
    if w["google"]:
        topic = " ".join(quoted(x) for x in conf["topic"])
        for path in watch_batch([p for p, *_ in named], conf, today):
            _, name, quals = by_path[path]
            query = " ".join([*(f'"{x}"' for x in [name, *quals]), topic]).strip()
            asked += 1
            try:
                items = parse_google(get(google_url(query, when=f"{int(w['days'])}d")))
            except (urllib.error.URLError, TimeoutError, ET.ParseError) as e:
                problems.append(f"google, {query!r}: {e}")
                continue
            answered += 1
            for item in items:
                if not words or any(holds(item["title"].lower(), x) for x in words):
                    add(path, item)
            pause(1.0)
    for feed in w["feeds"] or []:
        asked += 1
        try:
            items = parse_feed(get(feed["url"]), feed.get("name") or feed["url"])
        except (urllib.error.URLError, TimeoutError, ET.ParseError, KeyError) as e:
            problems.append(f"feed {feed.get('name') or feed.get('url')}: {e}")
            continue
        answered += 1
        for item in items:
            text = f"{item['title']} {item.get('summary', '')}"
            for path, _, name, quals in named:
                qualified = not w.get("require_qualifiers") or all(names_record(text, q) for q in quals)
                if names_record(text, name) and qualified:
                    add(path, item)
    if asked and not answered:
        problems.append(NONE_ANSWERED)
    return list(found.values()), problems


def inert(text: str) -> str:
    """News text, safe in an issue: no @mention notifies anyone, and no HTML (a seen marker) gets in."""
    return cell(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("@", "&#64;")


def watch_report(found: list[dict], problems: list[str], today: str) -> str:
    total = sum(len(f["items"]) for f in found)
    lines = [f"{total} new stor{'y' if total == 1 else 'ies'} for {len(found)} record(s), found {today} by "
             "`just news-watch`.", "",
             "Leads, not evidence. To use one: find the article, read its archived copy, and quote it "
             "with `just add-evidence`, citing the snapshot. `just news-leads <record>` searches a "
             "record's past news.", ""]
    tail = ["Not answered:", ""] + [f"- {p}" for p in problems] + [""] if problems else []
    room = REPORT_LIMIT - len("\n".join(lines + tail)) - 200  # 200: the line saying what was left out
    left_out = 0
    for f in sorted(found, key=lambda x: x["record"].lower()):
        rel = f["path"].relative_to(REPO_ROOT) if f["path"].is_relative_to(REPO_ROOT) else f["path"]
        block = [f"### {f['record']}", "", f"`{rel}`", ""]
        for item in sorted(f["items"], key=lambda i: i.get("date", ""), reverse=True):
            outlet = f" ({inert(item['outlet'])})" if item.get("outlet") else ""
            link = urllib.parse.quote(item["link"], safe=":/?&=#%+,;~")
            line = (f"- {item.get('date') or 'undated'}: [{inert(item['title'])}]({link}){outlet}"
                    f" <!-- seen: {item['key']} -->")
            if left_out or len(line) + 1 > room - sum(len(x) + 1 for x in block):
                left_out += 1
                continue
            block.append(line)
        if len(block) > 4:
            lines += block + [""]
            room -= sum(len(x) + 1 for x in block) + 1
    if left_out:
        lines += [f"{left_out} more stor{'y' if left_out == 1 else 'ies'} did not fit in one issue. They "
                  "are not marked seen, so the next run reports them.", ""]
    return "\n".join(lines + tail)


# ---------------------------------------------------------------- command line


def record_path(target: str) -> Path | None:
    path = Path(target)
    if path.suffix == ".yaml" and path.exists():
        return path.resolve()
    match = sorted(RECORDS_DIR.rglob(f"{target}.yaml"))
    return match[0] if match else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("plan", help="print the searches for a record, as JSON")
    p.add_argument("record")
    lp = sub.add_parser("leads", help="search a record's news and write its leads file")
    lp.add_argument("record", nargs="?")
    lp.add_argument("--plan", type=Path, help="a plan file, in place of a record")
    lp.add_argument("--out", type=Path, help="default: curation/news/<stem>.md")
    wp = sub.add_parser("watch", help="new stories for records, into build/news/")
    wp.add_argument("--seen", type=Path, help="earlier watch reports; their stories are skipped")
    wp.add_argument("--out-dir", type=Path, default=WATCH_DIR)
    args = ap.parse_args(argv)
    conf = settings()

    if args.command == "watch":
        text = args.seen.read_text(encoding="utf-8") if args.seen and args.seen.exists() else ""
        found, problems = watch(conf, set(SEEN.findall(text)))
        for problem in problems:
            print(f"not answered: {problem}", file=sys.stderr)
        if NONE_ANSWERED in problems:
            return 2
        total = sum(len(f["items"]) for f in found)
        print(f"{total} new stories for {len(found)} record(s).")
        if found:
            args.out_dir.mkdir(parents=True, exist_ok=True)
            today = dt.date.today().isoformat()
            (args.out_dir / "watch.md").write_text(watch_report(found, problems, today), encoding="utf-8")
            (args.out_dir / "watch.json").write_text(json.dumps(
                {"date": today, "count": total, "records": [{**f, "path": str(f["path"])} for f in found]},
                indent=1), encoding="utf-8")
        return 0

    if args.command == "leads" and args.plan:
        if not args.plan.exists():
            print(f"{args.plan}: no such plan", file=sys.stderr)
            return 1
        the_plan = json.loads(args.plan.read_text(encoding="utf-8"))
        return leads(the_plan, conf, args.out or NEWS_DIR / f"{args.plan.stem}.md")
    if not args.record:
        ap.error("give a record, or --plan")
    path = record_path(args.record)
    if path is None:
        print(f"{args.record}: no record by that stem or path under {RECORDS_DIR.relative_to(REPO_ROOT)}",
              file=sys.stderr)
        return 1
    the_plan = plan(load(path), conf)
    if args.command == "plan":
        print(json.dumps(the_plan, indent=2))
        return 0
    return leads(the_plan, conf, args.out or NEWS_DIR / f"{path.stem}.md")


if __name__ == "__main__":
    sys.exit(main())
