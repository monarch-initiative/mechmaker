"""just load: the graph it builds, the addresses it reads, what it refuses. No server needed."""

from pathlib import Path

import pytest

from goatmech import load
from goatmech.paths import RECORD_CLASS
from goatmech.validate import load as load_yaml

EXAMPLE = load_yaml(Path(__file__).parent / "data" / "example_record.yaml")


def test_graph_has_one_node_per_object_and_an_edge_per_link():
    nodes, edges = load.graph(load.schemaview(), [EXAMPLE])
    ids = [n["id"] for n in nodes]
    assert len(ids) == len(set(ids))
    record = next(n for n in nodes if n["id"] == EXAMPLE["id"])
    assert record[load.LABEL] == RECORD_CLASS
    assert all(e["subject"] in ids and e["object"] in ids for e in edges)
    # Every node but the record hangs from something. (Not a tree: two fields
    # may bind the same term, which is then one node with two edges into it.)
    reached = {e["object"] for e in edges}
    assert set(ids) - reached == {EXAMPLE["id"]}


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


def reference_schema(tmp_path):
    """A record class whose `parent` and `kin` refer to other records by id."""
    import yaml as _yaml
    from linkml_runtime.utils.schemaview import SchemaView

    schema = {
        "id": "https://example.org/refs", "name": "refs", "default_prefix": "ex", "default_range": "string",
        "prefixes": {"linkml": "https://w3id.org/linkml/", "ex": "https://example.org/refs/"},
        "imports": ["linkml:types"],
        "classes": {RECORD_CLASS: {"tree_root": True, "attributes": {
            "id": {"identifier": True}, "name": {},
            "parent": {"range": RECORD_CLASS}, "kin": {"range": RECORD_CLASS, "multivalued": True}}}},
    }
    path = tmp_path / "refs.yaml"
    path.write_text(_yaml.safe_dump(schema))
    return SchemaView(str(path))


# B comes first, so its references are stubs before A itself is read.
REF_RECORDS = [{"id": "ex:b", "name": "B", "parent": "ex:a", "kin": ["ex:a"]}, {"id": "ex:a", "name": "A"}]


def test_references_by_id_become_edges(tmp_path):
    nodes, edges = load.graph(reference_schema(tmp_path), REF_RECORDS)
    assert sorted(n["id"] for n in nodes) == ["ex:a", "ex:b"]
    assert {(e["subject"], e["predicate"], e["object"]) for e in edges} == {
        ("ex:b", "parent", "ex:a"), ("ex:b", "kin", "ex:a")}
    assert next(n for n in nodes if n["id"] == "ex:a")["name"] == "A"  # the stub became the record


def test_two_records_with_one_id_are_refused():
    twin = {**EXAMPLE, "name": "twin"}
    with pytest.raises(SystemExit, match="two records have the id"):
        load.graph(load.schemaview(), [EXAMPLE, twin])


def test_labels_are_escaped_for_cypher():
    assert load._quote("Term") == "`Term`"
    assert load._quote("odd`name") == "`odd``name`"
    assert [len(b) for b in load._batches(list(range(2500)), 1000)] == [1000, 1000, 500]
