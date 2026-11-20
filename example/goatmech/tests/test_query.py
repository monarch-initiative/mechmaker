"""The query page: conf/queries.yaml is sound, every query runs, and the page escapes what it shows."""

from pathlib import Path

import pytest
import yaml

from goatmech import query, render
from goatmech.paths import PAGES_DIR

EXAMPLE = Path(__file__).parent / "data" / "example_record.yaml"


def test_committed_queries_are_sound():
    cfg = query.settings()
    assert query.problems(cfg) == []
    assert cfg["queries"], "conf/queries.yaml lists no query"


@pytest.mark.parametrize("bad", [
    {"languages": ["sql", "cypher"]},
    {"queries": [{"id": "a", "title": "A", "language": "sql", "query": "SELECT 1"},
                 {"id": "a", "title": "B", "language": "sql", "query": "SELECT 2"}]},
    {"queries": [{"id": "a", "title": "A", "language": "sql", "query": ""}]},
    {"languages": ["sql"], "queries": [{"id": "a", "title": "A", "language": "sparql", "query": "ASK {}"}]},
])
def test_bad_queries_are_rejected(bad):
    assert query.problems({"languages": ["sql"], "queries": [], **bad})


def test_quotes_and_terms_are_found_with_their_section():
    record = {
        "id": "x:1", "name": "X",
        "description_evidence": [{"reference": "PMID:1", "supports": "SUPPORT", "snippet": "a"}],
        "parts": [{"preferred_term": "p", "term": {"id": "GO:1", "label": "g"},
                   "evidence": [{"reference": "PMID:2", "supports": "REFUTE", "snippet": "b"}]}],
        "curation_history": [{"timestamp": "2026-01-01T00:00:00Z", "curator": "c"}],
    }
    rows = query.derived_rows([(Path("x.yaml"), record)])
    assert [(r[2], r[3], r[5]) for r in rows["record_evidence"]] == [
        ("description", "PMID:1", "SUPPORT"), ("parts", "PMID:2", "REFUTE")]
    assert rows["record_terms"] == [["x:1", "X", "parts", "GO:1", "g"]]


@pytest.fixture
def example_corpus(monkeypatch):
    """The example record as the whole corpus, with a quote against its description, so every query
    runs over real tables and the ones about evidence have some."""
    data = yaml.safe_load(EXAMPLE.read_text(encoding="utf-8"))
    data["description_evidence"] = [{"reference": "PMID:1", "supports": "REFUTE", "snippet": "a placeholder"}]
    monkeypatch.setattr(query, "records", lambda: [(EXAMPLE, data)])
    return data


def test_every_query_runs_over_the_example_record(example_corpus, tmp_path):
    files, problems = query.build(tmp_path)
    assert problems == []
    assert (tmp_path / "tables.json") in files
    assert query.check(data_dir=tmp_path) == []


def test_a_build_replaces_its_own_files_and_leaves_the_rest(example_corpus, tmp_path):
    (tmp_path / "Gone.parquet").write_bytes(b"from a class since removed")
    (tmp_path / "index.html").write_text("not the page's data", encoding="utf-8")
    files, _ = query.build(tmp_path)
    assert not (tmp_path / "Gone.parquet").exists()
    assert (tmp_path / "index.html").read_text(encoding="utf-8") == "not the page's data"
    assert tmp_path / "index.html" not in files


def test_every_query_runs_with_no_records(monkeypatch, tmp_path):
    monkeypatch.setattr(query, "records", lambda: [])
    assert query.build(tmp_path)[1] == []
    assert query.check(data_dir=tmp_path) == []


def test_tables_hold_the_records_and_the_tables_made_for_queries(example_corpus, tmp_path):
    query.build(tmp_path)
    count = query.run_sql(tmp_path, 'SELECT count(*) FROM "GoatBreed"')
    assert count == [(1,)]
    quotes = query.run_sql(tmp_path, "SELECT section, supports FROM record_evidence")
    assert quotes == [("description", "REFUTE")]


def test_the_graph_holds_the_record(example_corpus, tmp_path):
    query.build(tmp_path)
    ns = "https://w3id.org/monarch-initiative/goatmech/"
    found = query.run_sparql(tmp_path, "SELECT ?r WHERE { ?r a <" + ns + "GoatBreed> }")
    assert len(found) == 1


def test_an_ask_query_answers_yes_or_no(example_corpus, tmp_path):
    query.build(tmp_path)
    assert query.run_sparql(tmp_path, "ASK { ?s ?p ?o }") is True


def test_a_broken_query_is_named(example_corpus, tmp_path, monkeypatch):
    lang = query.settings()["languages"][0]
    bad = {"id": "broken", "title": "Broken", "language": lang, "query": "SELECT nothing FROM nowhere"}
    cfg = {**query.settings(), "queries": [bad]}
    query.build(tmp_path, cfg)
    problems = query.check(cfg, data_dir=tmp_path)
    assert len(problems) == 1 and problems[0].startswith("broken")


def test_the_page_escapes_titles_and_its_embedded_queries(monkeypatch):
    lang = query.settings()["languages"][0]
    sneaky = {"id": "x", "title": "<b>bold</b>", "description": "</script><script>alert(1)</script>",
              "language": lang, "query": "SELECT '</script>'"}
    monkeypatch.setattr(query, "settings", lambda: {"languages": [lang], "queries": [sneaky]})
    page = render.build()[PAGES_DIR / "query.html"]
    assert "<b>bold</b>" not in page and "&lt;b&gt;bold&lt;/b&gt;" in page
    embedded = page.split('id="query-config">', 1)[1].split("</script>", 1)[0]
    assert "</" not in embedded
    assert 'href="query.html"' in render.build()[PAGES_DIR / "index.html"]
