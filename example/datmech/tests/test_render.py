"""The record browser's layout rules: labels, links, tables, cards, escaping."""

import pytest

from datmech import render


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


def test_every_bounding_box_is_on_the_map_named_by_what_holds_it():
    box = {"west": -83.7, "south": 43.0, "east": -83.6, "north": 43.1}
    data = {"name": "X", "area": {"vintage": 2020, "bounding_box": box},
            "watersheds": [{"name": "Flint", "bounding_box": box}, {"name": "<b>Swan</b>", "extent": box}],
            "secret": {"bounding_box": box}}
    found = render.map_boxes(data, hidden=["secret"])
    assert [b["name"] for b in found] == ["Area", "Watersheds: Flint", "Watersheds: &lt;b&gt;Swan&lt;/b&gt;"]
    assert [b["group"] for b in found] == [0, 1, 1]
    assert found[0]["bounds"] == [[43.0, -83.7], [43.1, -83.6]]


def test_no_box_no_map_and_map_can_be_turned_off():
    box = {"west": 1, "south": 2, "east": 3, "north": 4}
    assert render.record_body({"name": "X", "area": {"name": "a"}}, hidden=[])["map"] is None
    placed = {"name": "X", "area": {"bounding_box": box}}
    assert render.record_body(placed, hidden=[], show_map=False)["map"] is None
    shown = render.record_body(placed, hidden=[])["map"]
    assert '"bounds": [[2, 1], [4, 3]]' in shown


def test_a_box_the_validator_rejects_is_left_off_and_json_cannot_end_the_script():
    bad = {"west": 10, "south": 0, "east": -10, "north": 1}
    assert render.map_boxes({"area": {"bounding_box": bad}}) == []
    box = {"name": "</script><script>alert(1)</script>", "west": 0, "south": 0, "east": 1, "north": 1}
    assert "</" not in render.map_data({"area": box})
