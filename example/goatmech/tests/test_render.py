"""The record browser's layout rules: labels, links, tables, cards, escaping."""

import pytest

from goatmech import render


@pytest.fixture(autouse=True)
def schema(monkeypatch):
    slots = {"spdx_id": ("SPDX id", "SPDX license identifier."), "horn_status": (None, "Horned or not.")}
    values = {"HORNED": "Normally horned.", "SUPPORT": "SUPPORT"}
    monkeypatch.setattr(render, "schema_info", lambda: (slots, values))


def test_labels_are_readable():
    assert render.label("horn_status") == "Horn status"
    assert render.label("spdx_id") == "SPDX id"  # a schema title wins
    assert render.help_text("horn_status") == "Horned or not."


@pytest.mark.parametrize("ref,url", [
    ("PMID:123", "https://pubmed.ncbi.nlm.nih.gov/123"),
    ("WIKIPEDIA:Boer_goat", "https://en.wikipedia.org/wiki/Boer_goat"),
    ("url:https://example.org/a.txt", "https://example.org/a.txt"),
    ("VBO:0000736", "https://bioregistry.io/VBO:0000736"),
])
def test_curie_links(ref, url):
    assert render.curie_url(ref) == url


def test_scalars_link_badge_and_escape():
    assert '<a href="https://example.org/x">' in render.scalar("https://example.org/x")
    assert 'title="Normally horned."' in render.scalar("HORNED") and ">horned<" in render.scalar("HORNED")
    assert render.scalar("ZFIN") == "ZFIN"  # capitals alone do not make an enum value
    assert "<script>" not in render.scalar("<script>alert(1)</script>")
    assert "&lt;script&gt;" in render.card({"preferred_term": "<script>x</script>"})


def test_long_references_are_shortened():
    ref = "url:https://raw.githubusercontent.com/org/repo/" + "a" * 40 + "/README.md"
    text = render.ref_text(ref)
    assert len(text) == 64 and text.startswith("raw.githubusercontent.com") and text.endswith("README.md")


def test_tables_for_uniform_rows_cards_for_mentions():
    rows = [{"trait": {"id": "VT:1", "label": "body mass"}, "value": 115, "unit": "kg"}]
    assert render.tabular(rows) == ["trait", "value", "unit"]
    assert render.tabular([{"preferred_term": "white body", "notes": "x"}]) is None
    assert render.tabular([{"a": "x" * 200, "b": 1}]) is None
    assert render.tabular([{"a": 1, "b": {"nested": [1]}}]) is None


def test_record_body_splits_overview_and_sections():
    data = {"id": "x:1", "name": "X", "repository": "https://example.org", "horn_status": "HORNED",
            "origins": [{"preferred_term": "here"}],
            "curation_history": [{"timestamp": "2026-01-01T00:00:00Z"}],
            "secret_section": [{"a": 1}]}
    body = render.record_body(data, hidden=["secret_section"])
    assert [name for name, _, _ in body["overview"]] == ["Repository", "Horn status"]
    assert [s["key"] for s in body["sections"]] == ["origins", "curation_history"]
    assert "<details" in body["sections"][1]["html"]
