"""just load: the graph it builds, the addresses it reads, what it refuses. No server needed."""

from pathlib import Path

import pytest

from ingestmech import load
from ingestmech.paths import RECORD_CLASS
from ingestmech.validate import load as load_yaml

EXAMPLE = load_yaml(Path(__file__).parent / "data" / "example_record.yaml")


def test_graph_has_one_node_per_object_and_an_edge_per_link():
    nodes, edges = load.graph(load.schemaview(), [EXAMPLE])
    ids = [n["id"] for n in nodes]
    assert len(ids) == len(set(ids))
    record = next(n for n in nodes if n["id"] == EXAMPLE["id"])
    assert record[load.LABEL] == RECORD_CLASS
    assert all(e["subject"] in ids and e["object"] in ids for e in edges)
    assert len(edges) == len(nodes) - 1  # one record, no shared terms: a tree


def test_nested_values_are_not_node_properties():
    nodes, _ = load.graph(load.schemaview(), [EXAMPLE])
    for n in nodes:
        for v in n.values():
            assert not isinstance(v, dict)
            assert not (isinstance(v, list) and any(isinstance(x, dict) for x in v))


def test_a_term_sharing_the_record_curie_gets_its_own_node(monkeypatch):
    sv = load.schemaview()
    classes = sv.all_classes()
    slot = next((s for s in sv.class_induced_slots(RECORD_CLASS)
                 if not s.multivalued and s.range in classes and sv.get_identifier_slot(s.range)), None)
    if slot is None:
        pytest.skip("no single identified object on the record class")
    record = {**EXAMPLE, slot.name: {"id": EXAMPLE["id"], "label": "itself"}}
    nodes, _ = load.graph(sv, [record])
    term = next(n for n in nodes if n["id"] == f"{EXAMPLE['id']} ({slot.range})")
    assert term["curie"] == EXAMPLE["id"]


def test_passwords_are_masked_and_variables_required(monkeypatch):
    assert load.masked("neo4j://neo4j:s3cret@host:7687/neo4j") == "neo4j://neo4j:***@host:7687/neo4j"
    # A password with @ or : in it is hidden whole, not up to its first @.
    assert load.masked("neo4j://neo4j:p@ss:w@host:7687/neo4j") == "neo4j://neo4j:***@host:7687/neo4j"
    monkeypatch.delenv("NO_SUCH_PASSWORD", raising=False)
    with pytest.raises(SystemExit):
        load.expand("neo4j://neo4j:${NO_SUCH_PASSWORD}@host/neo4j")
    monkeypatch.setenv("SOME_PASSWORD", "x")
    assert load.expand("mongodb://u:${SOME_PASSWORD}@h/db") == "mongodb://u:x@h/db"


def test_unknown_target_is_rejected(tmp_path, monkeypatch):
    bad = tmp_path / "load.yaml"
    bad.write_text("targets:\n  solr: http://localhost:8983/solr\n")
    monkeypatch.setattr(load, "SETTINGS", bad)
    with pytest.raises(SystemExit):
        load.settings()


def test_missing_linkml_store_says_what_to_install(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "linkml_store", None)  # as if not installed
    with pytest.raises(SystemExit) as exc:
        load.need("neo4j")
    assert "uv add 'linkml-store[neo4j]" in str(exc.value)
