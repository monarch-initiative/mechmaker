"""sssom_sets.py, on small canned mapping sets. No network."""

from __future__ import annotations

import gzip
import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


sssom_sets = load_script(ROOT / "skills" / "search-mappings" / "scripts" / "sssom_sets.py",
                         "mechmaker_sssom_sets")
kg_registry = load_script(ROOT / "skills" / "search-kg-registry" / "scripts" / "kg_registry.py",
                          "mechmaker_kg_registry")

ROWS = "".join("\t".join(row) + "\n" for row in [
    ["subject_id", "subject_label", "predicate_id", "object_id", "object_label", "mapping_justification"],
    ["MONDO:0007739", "Huntington disease", "skos:exactMatch", "OMIM:143100", "huntington disease",
     "semapv:ManualMappingCuration"],
    ["MONDO:0007739", "Huntington disease", "skos:exactMatch", "DOID:12858", "Huntington's disease",
     "semapv:UnspecifiedMatching"],
    ["DOID:0001", "OMIM thing", "skos:broadMatch", "MONDO:0000001", "disease", "semapv:LexicalMatching"],
])
# Mondo writes "# key:", sssom-py "#key:"; both are SSSOM.
SPACED = """# curie_map:
#   DOID: http://purl.obolibrary.org/obo/DOID_
#   MONDO: http://purl.obolibrary.org/obo/MONDO_
#   OMIM: https://omim.org/entry/
# mapping_set_id: https://example.org/spaced.sssom.tsv
# license: https://creativecommons.org/licenses/by/4.0/
# creator_label:
#   - A Curator
""" + ROWS
TIGHT = SPACED.replace("# ", "#")


@pytest.mark.parametrize("text", [SPACED, TIGHT])
def test_metadata_in_either_style(text):
    meta, rows = sssom_sets.parse(text.encode())
    assert meta["mapping_set_id"] == "https://example.org/spaced.sssom.tsv"
    assert meta["curie_map"]["OMIM"] == "https://omim.org/entry/"
    assert meta["creator_label"] == ["A Curator"]
    assert len(rows) == 3


def test_summary_counts_what_maps_to_what():
    s = sssom_sets.summary(*sssom_sets.parse(SPACED.encode()))
    assert s["rows"] == 3 and s["prefixes"] == 3
    assert {"subject": "MONDO", "predicate": "skos:exactMatch", "object": "OMIM", "rows": 1} in s["maps"]
    assert s["justifications"]["semapv:UnspecifiedMatching"] == 1


def test_find_by_curie_words_and_other_side():
    _, rows = sssom_sets.parse(SPACED.encode())
    assert len(sssom_sets.find(rows, "MONDO:0007739")) == 2
    assert [r["object_id"] for r in sssom_sets.find(rows, "MONDO:0007739", to="omim")] == ["OMIM:143100"]
    assert len(sssom_sets.find(rows, "huntington disease")) == 2  # every word, in either label
    assert sssom_sets.find(rows, "ington") == []  # at the start of a word only
    # Without a CURIE, either side can have the prefix.
    assert [r["subject_id"] for r in sssom_sets.find(rows, "omim", to="DOID")] == ["DOID:0001"]


def test_a_table_that_is_not_sssom_is_refused():
    with pytest.raises(ValueError):
        sssom_sets.parse(b"a\tb\n1\t2\n")


def test_main_reads_gzip_and_says_what_it_found(tmp_path, capsys):
    path = tmp_path / "set.sssom.tsv.gz"
    path.write_bytes(gzip.compress(SPACED.encode()))
    assert sssom_sets.main(["find", str(path), "MONDO:0007739", "--to", "OMIM"]) == 0
    assert "OMIM:143100 (huntington disease)" in capsys.readouterr().out
    assert sssom_sets.main(["find", str(path), "MONDO:9999999"]) == 1
    assert sssom_sets.main(["summary", str(path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["rows"] == 3
    assert sssom_sets.main(["summary", str(tmp_path / "missing.tsv")]) == 2
    assert sssom_sets.main(["find"]) == 64


def test_a_url_is_kept_and_reused(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    calls = []
    monkeypatch.setattr(sssom_sets, "download", lambda url: calls.append(url) or SPACED.encode())
    for _ in range(2):
        assert sssom_sets.fetch("https://example.org/x.sssom.tsv") == SPACED.encode()
    assert len(calls) == 1
    sssom_sets.fetch("https://example.org/x.sssom.tsv", refresh=True)
    assert len(calls) == 2


@pytest.mark.parametrize("name", ["cache_dir", "download"])
def test_shares_its_helpers_with_kg_registry(name):
    # Each skill stands alone, so each script carries its own copy; a fix to one goes in both.
    assert inspect.getsource(getattr(sssom_sets, name)) == inspect.getsource(getattr(kg_registry, name))
