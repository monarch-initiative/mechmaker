"""just add-evidence: evidence goes in checked, and nothing else changes."""

import shutil
from pathlib import Path

import pytest

from goatmech import evidence
from goatmech.validate import load, slugify

EXAMPLE = Path(__file__).parent / "data" / "example_record.yaml"
EVENT = {"timestamp": "2026-01-02T00:00:00+00:00", "curator": "tester", "llm_assisted": False,
         "action": "EDIT", "description": "Added evidence."}


def found(reference, snippet):
    return True, "", "A Source Title"


def not_found(reference, snippet):
    return False, "Text part not found as substring", "A Source Title"


@pytest.fixture
def record(tmp_path):
    # The record rules want the filename to follow the record's name.
    path = tmp_path / f"{slugify(load(EXAMPLE)['name'])}.yaml"
    shutil.copy(EXAMPLE, path)
    return path


def item(snippet="Colons: they need quoting."):
    return {"reference": "PMID:1", "supports": "SUPPORT", "snippet": snippet}


def test_adds_item_with_title_and_event(record):
    old, new, problems = evidence.add(record, "record", item(), dict(EVENT), check=found)
    assert problems == []
    record.write_text(new)
    data = load(record)
    added = data["evidence"][-1]
    assert added["reference_title"] == "A Source Title"
    assert added["snippet"] == "Colons: they need quoting."
    assert data["curation_history"][-1]["description"] == "Added evidence."


def test_only_additions_in_the_diff(record):
    old, new, _ = evidence.add(record, "record", item(), dict(EVENT), check=found)
    removed = [line for line in old.splitlines() if line not in new.splitlines()]
    assert removed in ([], ["updated_date: '2026-01-01'"], ["updated_date: 2026-01-01"])


def test_quote_not_found_writes_nothing(record):
    old, new, problems = evidence.add(record, "record", item(), dict(EVENT), check=not_found)
    assert new == old
    assert any("not found" in p for p in problems)


def test_duplicate_is_refused(record):
    _, new, _ = evidence.add(record, "record", item(), dict(EVENT), check=found)
    record.write_text(new)
    _, again, problems = evidence.add(record, "record", item(), dict(EVENT), check=found)
    assert any("already" in p for p in problems)


def test_place_must_carry_evidence(record):
    _, _, problems = evidence.add(record, "curation_history[0]", item(), dict(EVENT), check=found)
    assert problems  # the closed schema rejects evidence on a curation event


@pytest.mark.parametrize("place", ["nowhere", "curation_history[99]", "curation_history.0"])
def test_bad_place_is_explained(record, place):
    with pytest.raises(ValueError):
        evidence.add(record, place, item(), dict(EVENT), check=found)


def test_url_title_that_is_only_the_url_is_not_kept(record):
    url = "https://example.org/notes.txt"
    ref = {"reference": f"url:{url}", "supports": "SUPPORT", "snippet": "A line."}
    _, new, problems = evidence.add(record, "record", ref, dict(EVENT), check=lambda r, s: (True, "", url))
    assert problems == []
    assert "reference_title" not in new.split("url:" + url, 1)[1].split("snippet")[0]
