"""Write a news search plan for one ZIP area, for mechmaker's news_leads.py.

    uv run python scripts/news_plan.py data/zip_areas/44413_east_palestine_ohio.yaml > plan.json
    python3 <ingest-news scripts>/news_leads.py --plan plan.json \
        --out research/news/44413_east_palestine_ohio.md

The plan is what DaTMech knows and news_leads.py does not: which words name
the place, its water, and its incidents, and when to look.

  - One search per recorded incident, from a month before it began to a
    year after it began (or after it ended), for news that adds dates,
    advisories and numbers.
  - One search per year of the last --years (default 3), for incidents the
    record does not have yet.
  - One search per current treatment facility, over the same years.
  - Every Wikipedia article the record cites, for the news that article
    cites.

Every reference the record already cites goes in `known`, so a lead the
record has already used is marked.
"""

from __future__ import annotations

import argparse
import calendar
import datetime as dt
import json
import re
import sys
from pathlib import Path

from datmech.validate import load

STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
    "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
    "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
    "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
    "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
}
# Words news uses for each kind of incident and advisory, for the searches.
KIND_WORDS = {
    "CONTAMINATION": ["contamination", "contaminated"], "TREATMENT_FAILURE": ["treatment", "violation"],
    "SPILL": ["spill", "chemicals"], "TOXIC_BLOOM": ["algae", "toxin"], "OUTBREAK": ["outbreak", "illness"],
    "INFRASTRUCTURE_FAILURE": ["main break", "pressure"], "OTHER": [],
}
ADVISORY_WORDS = {
    "BOIL_WATER": ["boil"], "DO_NOT_DRINK": ["\"do not drink\""], "DO_NOT_USE": ["\"do not use\""],
    "BOTTLED_WATER": ["\"bottled water\""], "EMERGENCY_DECLARATION": ["emergency"],
    "NO_CONTACT": ["\"no contact\"", "sewage"], "OTHER": [],
}
DISCOVERY = ["boil", "\"do not drink\"", "contamination", "advisory", "spill", "\"bottled water\""]
# Kept when a Wikipedia citation's title holds one.
KEYWORDS = ["water", "drink", "well", "bottled", "boil", "advis", "contamin", "spill", "creek", "river",
            "lake", "run", "fish", "toxin", "algae", "lead", "epa", "test", "sample"]


def first_day(text: str) -> dt.date:
    parts = [int(x) for x in str(text).split("-")]
    return dt.date(parts[0], parts[1] if len(parts) > 1 else 1, parts[2] if len(parts) > 2 else 1)


def last_day(text: str) -> dt.date:
    parts = [int(x) for x in str(text).split("-")]
    if len(parts) == 3:
        return dt.date(*parts)
    month = parts[1] if len(parts) > 1 else 12
    return dt.date(parts[0], month, calendar.monthrange(parts[0], month)[1])


def any_of(words: list[str]) -> str:
    """(a OR b OR "two words"): a phrase of several words is quoted, so it is searched whole."""
    words = [f'"{w}"' if " " in w and not w.startswith('"') else w for w in words if w]
    words = list(dict.fromkeys(words))
    return "(" + " OR ".join(words) + ")" if len(words) > 1 else (words[0] if words else "")


def references(obj) -> list[str]:
    if isinstance(obj, dict):
        found = [obj["reference"]] if isinstance(obj.get("reference"), str) else []
        return found + [r for v in obj.values() for r in references(v)]
    if isinstance(obj, list):
        return [r for v in obj for r in references(v)]
    return []


def plan(data: dict, years: int, today: dt.date) -> dict:
    place = data.get("place_name") or data["name"]
    state = STATES.get(data.get("state", ""), data.get("state", ""))
    where = f'"{place}" "{state}"' if state else f'"{place}"'
    searches = []
    for inc in data.get("incidents") or []:
        if not inc.get("start_date"):
            continue
        start = first_day(inc["start_date"])
        end = last_day(inc.get("end_date") or inc["start_date"])
        words = list(KIND_WORDS.get(inc.get("incident_kind", ""), []))  # a copy: the table stays as it is
        for adv in inc.get("advisories") or []:
            words += ADVISORY_WORDS.get(adv.get("advisory_kind"), [])
        words += [c["preferred_term"] for c in inc.get("contaminants") or [] if c.get("preferred_term")]
        searches.append({
            "query": f"{where} water {any_of(words)}".strip(),
            "from": (start - dt.timedelta(days=30)).isoformat(),
            "to": min(max(end, start + dt.timedelta(days=365)), today).isoformat(),
            "why": f"Recorded incident: {inc['name']}"})
    for year in range(today.year - years + 1, today.year + 1):
        span = {"from": f"{year}-01-01", "to": min(dt.date(year, 12, 31), today).isoformat()}
        searches.append({"query": f"{where} water {any_of(DISCOVERY)}", **span,
                         "why": f"New incidents in {year}"})
        for fac in data.get("treatment_facilities") or []:
            if fac.get("service_status") == "CURRENT":
                searches.append({"query": f'"{fac["name"]}"', **span, "why": f"{fac['name']} in {year}"})
    refs = references(data)
    wiki = sorted({r.split(":", 1)[1] for r in refs if r.startswith("WIKIPEDIA:")})
    rank = [w.strip('"') for w in DISCOVERY] + ["sewage", "lead", "toxin", "contaminat", "evacuat", "test"]
    for inc in data.get("incidents") or []:
        rank += [c["preferred_term"] for c in inc.get("contaminants") or [] if c.get("preferred_term")]
    return {"label": data["name"], "searches": searches, "wikipedia": wiki, "keywords": KEYWORDS,
            "place": [place], "rank": list(dict.fromkeys(rank)), "known": sorted(set(refs))}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("record", type=Path)
    ap.add_argument("--years", type=int, default=3, help="how many recent years to search for new incidents")
    args = ap.parse_args(argv)
    data = load(args.record)
    if not isinstance(data, dict) or not re.match(r"^datmech:\d{5}$", str(data.get("id", ""))):
        print(f"{args.record} is not a ZIP area record", file=sys.stderr)
        return 1
    json.dump(plan(data, args.years, dt.date.today()), sys.stdout, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
