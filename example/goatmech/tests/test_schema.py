"""The schema, the vendored modules and the record rules."""

import copy
import hashlib
from pathlib import Path

import pytest
from linkml_runtime import SchemaView

from goatmech.compliance import WEIGHTS, score
from goatmech.paths import (
    HISTORY_SCHEMA_PATH,
    RECORD_CLASS,
    SCHEMA_DIR,
    SCHEMA_PATH,
)
from goatmech.validate import load, rule_errors, schema_errors

EXAMPLE = Path(__file__).parent / "data" / "example_record.yaml"

# Fleet canon. These files are vendored byte-identical; a changed hash means
# a local edit. Change them upstream and re-vendor, never here.
VENDORED_MD5 = {
    "mech_shared.yaml": "3cf80648642fcd1f824529bc40c572a5",
    "history.yaml": "3742bc2068b637868c48aba406f6569d",
}


@pytest.fixture
def example() -> dict:
    return load(EXAMPLE)


def test_schema_loads():
    sv = SchemaView(str(SCHEMA_PATH))
    assert RECORD_CLASS in sv.all_classes()
    assert sv.get_class(RECORD_CLASS).tree_root


@pytest.mark.parametrize("kind", ["all_classes", "all_slots", "all_enums", "all_types"])
def test_names_of_one_kind_differ_by_more_than_case(kind):
    """The schema pages are one file per element, in a folder per kind. Two
    names of one kind that differ only by case are one file on macOS and
    Windows, and the documentation build loses a page."""
    names = [str(n) for n in getattr(SchemaView(str(SCHEMA_PATH)), kind)()]
    seen: dict[str, str] = {}
    clashes = []
    for name in names:
        if name.casefold() in seen:
            clashes.append((seen[name.casefold()], name))
        seen[name.casefold()] = name
    assert clashes == []


@pytest.mark.parametrize("name,md5", VENDORED_MD5.items())
def test_vendored_modules_are_unmodified(name, md5):
    assert hashlib.md5((SCHEMA_DIR / name).read_bytes()).hexdigest() == md5


def test_example_is_valid(example):
    assert schema_errors(example) == []
    assert rule_errors(example) == []


def test_unknown_field_is_rejected(example):
    bad = copy.deepcopy(example)
    bad["not_a_field"] = 1
    assert schema_errors(bad)


def test_name_is_required(example):
    bad = copy.deepcopy(example)
    del bad["name"]
    assert schema_errors(bad)


def test_reviewed_needs_a_human_review_event(example):
    bad = copy.deepcopy(example)
    bad["status"] = "REVIEWED"
    assert any("REVIEWED" in e for e in rule_errors(bad))

def test_two_records_with_one_stem_are_refused(tmp_path, example):
    # Pages, history and research name a record by its filename stem alone.
    import yaml

    from goatmech.validate import validate_paths

    paths = []
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        path = tmp_path / sub / "same.yaml"
        path.write_text(yaml.safe_dump({**example, "id": f"{example['id']}-{sub}"}), encoding="utf-8")
        paths.append(path)
    failures = validate_paths(paths)
    assert not any("also used by" in e for e in failures.get(paths[0], []))
    assert any(f"also used by {paths[0]}" in e for e in failures[paths[1]])




def test_an_ontology_id_names_its_term_in_record_term(example):
    """The term check reaches the identity root through record_term only."""
    keyed = copy.deepcopy(example)
    keyed.pop("record_term", None)  # the Mech's example may be keyed by a term
    keyed["id"] = "VBO:0400025"
    assert any("record_term must name it" in e for e in rule_errors(keyed))
    keyed["record_term"] = {"id": "VBO:0", "label": "another term"}
    assert any("is not the record's id" in e for e in rule_errors(keyed))
    keyed["record_term"]["id"] = keyed["id"]
    assert rule_errors(keyed) == []
    minted = {k: v for k, v in example.items() if k != "record_term"}
    minted["id"] = "goatmech:example"
    assert rule_errors(minted) == []  # a minted id needs no record_term


def test_compliance_asks_for_record_term_only_on_a_keyed_id(example):
    keyed = {k: v for k, v in example.items() if k != "record_term"}
    keyed["id"] = "VBO:0400025"
    assert "no record_term" in score(keyed)[1]
    minted = dict(keyed, id="goatmech:example")
    assert "no record_term" not in score(minted)[1]
    assert score(minted)[0] - score(keyed)[0] == pytest.approx(WEIGHTS["record_term"])



def test_malformed_items_are_reported_not_crashed_on(example):
    bad = copy.deepcopy(example)
    bad["status"] = "REVIEWED"
    bad["mechanisms"] = ["a string, not a node", {"name": "n", "downstream": ["not an edge"]}]
    bad["curation_history"] = ["not an event"]
    assert any("REVIEWED" in e for e in rule_errors(bad))  # and no AttributeError


def test_a_broken_history_file_is_reported(tmp_path):
    from goatmech.history import validate_history

    (tmp_path / "dup.yaml").write_text("session: {}\nsession: {}\n", encoding="utf-8")
    (tmp_path / "null.yaml").write_text("session:\n", encoding="utf-8")
    failures = validate_history(tmp_path)
    assert "YAML parse error" in failures[tmp_path / "dup.yaml"][0]
    assert tmp_path / "null.yaml" in failures  # schema errors, not a crash


def test_history_schema_loads():
    sv = SchemaView(str(HISTORY_SCHEMA_PATH))
    assert "HistoryRecord" in sv.all_classes()
