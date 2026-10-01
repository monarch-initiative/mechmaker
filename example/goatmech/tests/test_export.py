"""Every export format, from the example record: written, and read back clean.

This is where a schema change that breaks a format shows first: an RDF IRI
that does not expand (a prefix with no URI), or a table layout the loader
does not know.
"""

import csv
import io
import sqlite3
import zipfile
from pathlib import Path

import pytest

from goatmech import export
from goatmech.paths import RECORD_CLASS, SLUG

EXAMPLE = Path(__file__).parent / "data" / "example_record.yaml"
try:
    import linkml_store  # noqa: F401  only installed when this Mech exports DuckDB

    HAS_DUCKDB = True
except ImportError:
    HAS_DUCKDB = False
# Every format this Mech can write as installed.
INSTALLED = [f for f in export.FORMATS if f != "duckdb" or HAS_DUCKDB]


@pytest.mark.parametrize("layout", ["per_class", "flat"])
def test_every_format_reads_back(tmp_path, layout):
    cfg = {"formats": INSTALLED, "tabular_layout": layout}
    written, problems = export.export(cfg, [EXAMPLE], tmp_path)
    assert problems == []
    names = {p.name for p in written}
    assert f"{SLUG}-records.ttl" in names and f"{SLUG}-records.jsonld" in names
    assert f"{SLUG}-schema.sql" in names and f"{SLUG}-records.sqlite" in names
    if layout == "flat":
        assert f"{SLUG}-records.csv" in names
    else:
        with zipfile.ZipFile(tmp_path / f"{SLUG}-tables-csv.zip") as zf:
            assert f"{RECORD_CLASS}.csv" in zf.namelist()


def test_nested_rows_name_their_field(tmp_path):
    export.export({"formats": ["sqlite"], "tabular_layout": "per_class"}, [EXAMPLE], tmp_path)
    con = sqlite3.connect(tmp_path / f"{SLUG}-records.sqlite")
    tables = [t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
    cols = {t: [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')] for t in tables}
    nested = [t for t, c in cols.items() if f"{RECORD_CLASS}_id" in c and "parent_slot" in c]
    assert nested, "no table points back at the record"
    for t in nested:
        orphans = f'SELECT count(*) FROM "{t}" WHERE parent_slot IS NULL AND "{RECORD_CLASS}_id" IS NOT NULL'
        assert con.execute(orphans).fetchone()[0] == 0


def test_flat_rows_keep_nested_values_as_json(tmp_path):
    export.export({"formats": ["tsv"], "tabular_layout": "flat"}, [EXAMPLE], tmp_path)
    text = (tmp_path / f"{SLUG}-records.tsv").read_text()
    rows = list(csv.DictReader(io.StringIO(text), delimiter="\t"))
    assert len(rows) == 1
    assert rows[0]["curation_history"].startswith("[{")


def test_undeclared_prefix_is_reported(tmp_path):
    sv = export.schemaview()
    import rdflib

    g = rdflib.Graph()
    g.add((rdflib.URIRef("NOPE:1"), rdflib.RDF.type, rdflib.URIRef(sv.get_uri(RECORD_CLASS, expand=True))))
    path = tmp_path / "x.ttl"
    g.serialize(path, format="turtle")
    problems = export.check_rdf(path, "turtle", sv, 1)
    assert any("NOPE" in p for p in problems)


def test_settings_are_checked(tmp_path, monkeypatch):
    bad = tmp_path / "export.yaml"
    bad.write_text("formats: [parquet]\n")
    monkeypatch.setattr(export, "SETTINGS", bad)
    with pytest.raises(SystemExit):
        export.settings()


def test_one_key_list_items_load():
    # linkml-runtime misreads a one-key list item; the export pads it first.
    sv = export.schemaview()
    classes = sv.all_classes()
    slot = next((s for s in sv.class_induced_slots(RECORD_CLASS)
                 if s.multivalued and s.range in classes and len(sv.class_induced_slots(s.range)) > 1), None)
    if slot is None:
        pytest.skip("no list of objects on the record class")
    first = sv.class_induced_slots(slot.range)[0].name
    padded = export.pad_single_keys(sv, RECORD_CLASS, {slot.name: [{first: "x"}]})
    item = padded[slot.name][0]
    assert item[first] == "x" and len(item) == 2 and None in item.values()


@pytest.mark.skipif(HAS_DUCKDB, reason="linkml-store is installed")
def test_duckdb_without_linkml_store_says_what_to_install(tmp_path):
    cfg = {"formats": ["duckdb"], "tabular_layout": "per_class"}
    _, problems = export.export(cfg, [EXAMPLE], tmp_path)
    assert problems == [export.DUCKDB_MISSING]


@pytest.mark.skipif(not HAS_DUCKDB, reason="linkml-store is not installed")
def test_duckdb_holds_the_records(tmp_path):
    import duckdb

    cfg = {"formats": ["duckdb"], "tabular_layout": "per_class"}
    written, problems = export.export(cfg, [EXAMPLE], tmp_path)
    assert problems == []
    con = duckdb.connect(str(written[0]), read_only=True)
    assert con.execute(f'SELECT count(*) FROM "{export.RECORDS_DIR.name}"').fetchone()[0] == 1


def test_a_broken_linkml_store_is_not_called_missing(tmp_path, monkeypatch):
    def broken(*args, **kwargs):
        raise ModuleNotFoundError("No module named 'pymongo'", name="pymongo")

    monkeypatch.setattr(export, "write_duckdb", broken)
    with pytest.raises(ModuleNotFoundError):
        export.export({"formats": ["duckdb"], "tabular_layout": "per_class"}, [EXAMPLE], tmp_path)


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


def test_references_by_id_go_in_their_columns(tmp_path):
    db = tmp_path / "refs.sqlite"
    export.build_sqlite(reference_schema(tmp_path), [(None, r) for r in REF_RECORDS], db)
    con = sqlite3.connect(db)
    assert con.execute(f'SELECT parent FROM "{RECORD_CLASS}" WHERE id = ?', ("ex:b",)).fetchone() == ("ex:a",)
    assert con.execute(f'SELECT kin_id FROM "{RECORD_CLASS}_kin"').fetchall() == [("ex:a",)]


def test_two_records_with_one_id_are_refused(tmp_path):
    twin = tmp_path / "twin.yaml"
    twin.write_text(EXAMPLE.read_text())
    with pytest.raises(SystemExit, match="have the same id"):
        export.export({"formats": ["json"], "tabular_layout": "per_class"}, [EXAMPLE, twin], tmp_path / "out")
