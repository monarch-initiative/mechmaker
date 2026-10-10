"""news_leads.py, on canned responses from each source. No network."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "ingest-news" / "scripts" / "news_leads.py"
sys.path.insert(0, str(SCRIPT.parent))

import news_leads  # noqa: E402

GOOGLE = """<?xml version="1.0" encoding="UTF-8"?><rss><channel>
<item><title>Officials say not to drink the water - The Statehouse News Bureau</title>
<link>https://news.google.com/rss/articles/CBMi1</link><pubDate>Tue, 14 Feb 2023 08:00:00 GMT</pubDate>
<source url="https://www.statenews.org">The Statehouse News Bureau</source></item>
</channel></rss>"""
GDELT = json.dumps({"articles": [
    {"url": "https://www.wkbn.com/news/a/", "title": "Water testing continues",
     "seendate": "20230214T013000Z", "domain": "wkbn.com", "language": "English"},
    {"url": "https://example.es/x", "title": "Agua", "seendate": "20230214T013000Z", "domain": "example.es",
     "language": "Spanish"}]})
WIKITEXT = """Text.<ref>{{cite news |title=East Palestine water quality testing continues |url=https://www.wkbn.com/news/a/
 |date=February 11, 2023 |work=WKBN.com |archive-url=https://web.archive.org/web/20230214012618/https://www.wkbn.com/news/a/}}</ref>
More.<ref>{{cite web|title=Train cars [[vinyl chloride|chemicals]] listed|url=https://example.org/b|date=2023-02-12}}</ref>
And.<ref>{{cite web|title=Stock prices fall|url=https://example.org/c}}</ref>"""


def test_google_title_loses_its_outlet_and_date_is_iso():
    (lead,) = news_leads.parse_google(GOOGLE)
    assert lead["title"] == "Officials say not to drink the water"
    assert lead["outlet"] == "The Statehouse News Bureau"
    assert lead["date"] == "2023-02-14" and lead["url"] == ""


def test_google_search_carries_the_dates():
    url = news_leads.google_url('"East Palestine" water', "2023-02-03", "2023-03-15")
    assert "after%3A2023-02-03" in url and "before%3A2023-03-15" in url


def test_gdelt_keeps_english_articles():
    leads = news_leads.parse_gdelt(GDELT)
    assert [lead["url"] for lead in leads] == ["https://www.wkbn.com/news/a/"]
    assert leads[0]["date"] == "2023-02-14"


def test_wikipedia_citations_with_their_archives():
    leads = news_leads.parse_wikipedia(WIKITEXT, "Article")
    assert leads[0]["archive"].startswith("https://web.archive.org/web/20230214012618/")
    assert leads[0]["date"] == "2023-02-11" and leads[0]["outlet"] == "WKBN.com"
    assert leads[1]["title"] == "Train cars chemicals listed"  # a wikilink keeps its text


@pytest.mark.parametrize("text,iso", [
    ("February 11, 2023", "2023-02-11"), ("25 February 2023", "2023-02-25"), ("2023-02-12", "2023-02-12"),
    ("February 2023", "2023-02"), ("sometime", "sometime")])
def test_dates(text, iso):
    assert news_leads.iso_date(text) == iso


def test_one_lead_per_article_and_cited_ones_are_marked():
    leads = news_leads.parse_gdelt(GDELT) + news_leads.parse_wikipedia(WIKITEXT, "Article")
    known = ["url:https://web.archive.org/web/20230214012618/https://www.wkbn.com/news/a/"]
    out = news_leads.dedupe(leads, known)
    assert len(out) == 3  # the WKBN story, found twice, once
    assert out[0]["cited"] and not out[1]["cited"]


def test_wikipedia_keeps_titles_with_a_keyword(monkeypatch):
    page = json.dumps({"parse": {"wikitext": WIKITEXT}})
    monkeypatch.setattr(news_leads, "get", lambda url, timeout=60: page)
    run = news_leads.Run(("wikipedia",), wayback=0, pause=lambda s: None)
    titles = [lead["title"] for lead in run.wikipedia("Article", ["water", "chemicals"])]
    assert titles == ["East Palestine water quality testing continues", "Train cars chemicals listed"]


def test_gdelt_is_not_asked_before_2017(monkeypatch):
    asked = []
    monkeypatch.setattr(news_leads, "get", lambda url, timeout=60: asked.append(url) or GOOGLE)
    run = news_leads.Run(("google", "gdelt"), wayback=0, pause=lambda s: None)
    run.search({"query": "Toledo water", "from": "2014-08-01", "to": "2014-08-31"})
    assert len(asked) == 1 and "news.google.com" in asked[0]


def test_report_says_leads_are_not_evidence():
    run = news_leads.Run(("google",), wayback=0, pause=lambda s: None)
    leads = news_leads.parse_google(GOOGLE)
    for lead in leads:
        lead["why"] = "Recorded incident"
    text = news_leads.report("44413 East Palestine, Ohio", leads, run, [], "2026-10-09")
    assert "Leads, not evidence" in text and "Never cite this file" in text
    assert "| 2023-02-14 | The Statehouse News Bureau |" in text and "search title and outlet" in text


def test_usage(tmp_path):
    with pytest.raises(SystemExit):
        news_leads.main(["--out", str(tmp_path / "x.md")])


def test_gdelt_is_dropped_after_two_refusals(monkeypatch):
    asked = []

    def refuse(url, timeout=60):
        asked.append(url)
        raise news_leads.urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)
    monkeypatch.setattr(news_leads, "get", refuse)
    run = news_leads.Run(("gdelt",), wayback=0, pause=lambda s: None)
    for _ in range(4):
        run.search({"query": "q", "from": "2023-02-01", "to": "2023-02-28"})
    assert len(asked) == 4  # two searches, each tried twice; then none
    assert any("not asked again" in p for p in run.problems)


def test_report_ranks_by_place_and_words_and_folds_the_rest():
    leads = [{"title": t, "outlet": "", "date": d, "url": "", "link": "x", "source": "google", "why": "w"}
             for t, d in [("Lake levels rise", "2024-01-01"), ("Toledo lifts boil advisory", "2024-04-03"),
                          ("Boil advisory in another town", "2024-05-01")]]
    run = news_leads.Run(("google",), wayback=0, pause=lambda s: None)
    text = news_leads.report("x", leads, run, [], "2026-10-09", place=["Toledo"], rank=["boil"], show=2)
    shown, folded = text.split("<details>")
    assert shown.index("Toledo lifts") < shown.index("another town")
    assert "Lake levels" in folded and "1 more" in folded
