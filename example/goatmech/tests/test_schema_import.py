"""just import-schema: copy and reference modes, on a small external schema."""

import shutil
from pathlib import Path

import pytest
import yaml

from goatmech import schema_import
from goatmech.paths import RECORD_CLASS, SCHEMA_DIR, SCHEMA_PATH
from goatmech.validate import load, schema_errors

SOURCE = Path(__file__).parent / "data" / "source_schema.yaml"
# Records start from the Mech's own example, so the tests hold whatever the
# Mech's id pattern and required fields are.
EXAMPLE = load(Path(__file__).parent / "data" / "example_record.yaml")


@pytest.fixture
def schema_dir(tmp_path, monkeypatch):
    """A scratch copy of the Mech's schema directory, so the tests write nothing real."""
    d = tmp_path / "schema"
    shutil.copytree(SCHEMA_DIR, d)
    monkeypatch.setattr(schema_import, "SCHEMA_DIR", d)
    monkeypatch.setattr(schema_import, "SCHEMA_PATH", d / SCHEMA_PATH.name)
    return d


def run(*args):
    return schema_import.main([str(SOURCE), "--record-class", "Sample", *args])


def record(**extra):
    return {**EXAMPLE, **extra}


def test_a_clash_stops_copy_until_renamed(schema_dir, capsys):
    before = (schema_dir / SCHEMA_PATH.name).read_text()
    assert run("--apply") == 1
    assert "'status'" in capsys.readouterr().out
    assert (schema_dir / SCHEMA_PATH.name).read_text() == before


def test_copy_folds_the_class_in_and_keeps_its_rules(schema_dir):
    assert run("--rename", "status=sample_status", "--apply") == 0
    path = schema_dir / SCHEMA_PATH.name
    schema = yaml.safe_load(path.read_text())
    rc = schema["classes"][RECORD_CLASS]
    assert {"sample_weight", "collection_site", "sample_status"} <= set(rc["slots"])
    assert rc["class_uri"] == "fieldwork:Sample"  # the source's meaning, kept
    assert schema["slots"]["sample_weight"]["slot_uri"] == "fieldwork:sample_weight"
    assert schema["slots"]["sample_code"]["identifier"] is False  # records are keyed by id
    assert "mode=copy" in schema["annotations"]["imported_schema"]
    good = record(sample_status="FRESH", sample_weight=2.5, collection_site={"site_name": "pond"})
    assert schema_errors(good, schema=path) == []
    assert schema_errors(record(sample_weight=-1), schema=path)  # minimum_value came along
    assert schema_errors(record(sample_status="MELTED"), schema=path)  # and the enum


def test_dry_run_writes_nothing(schema_dir):
    before = (schema_dir / SCHEMA_PATH.name).read_text()
    assert run("--rename", "status=sample_status") == 0
    assert (schema_dir / SCHEMA_PATH.name).read_text() == before


def test_reference_refuses_a_name_the_checks_depend_on(schema_dir, capsys):
    assert run("--mode", "reference", "--apply") == 1
    assert "use --mode copy" in capsys.readouterr().out


def test_reference_imports_the_source_unchanged(schema_dir, tmp_path, monkeypatch):
    source = yaml.safe_load(SOURCE.read_text())
    source["classes"]["Sample"]["slots"].remove("status")
    del source["slots"]["status"]
    del source["enums"]
    variant = tmp_path / "fieldwork.yaml"
    variant.write_text(yaml.safe_dump(source, sort_keys=False))
    args = [str(variant), "--record-class", "Sample", "--mode", "reference", "--apply"]
    assert schema_import.main(args) == 0
    stored = schema_dir / "fieldwork.yaml"
    assert yaml.safe_load(stored.read_text()) == source  # unchanged
    schema = yaml.safe_load((schema_dir / SCHEMA_PATH.name).read_text())
    assert "fieldwork" in schema["imports"]
    assert schema["classes"][RECORD_CLASS]["is_a"] == "Sample"
    path = schema_dir / SCHEMA_PATH.name
    demoted = schema["classes"][RECORD_CLASS]["slot_usage"]["sample_code"]
    assert demoted == {"identifier": False, "required": False}  # records are keyed by id
    assert schema_errors(record(sample_weight=1.0), schema=path) == []  # no sample_code needed
    assert schema_errors(record(sample_weight=-1.0), schema=path)


def test_unknown_record_class(schema_dir, capsys):
    assert schema_import.main([str(SOURCE), "--record-class", "Nope"]) == 1
    assert "no class 'Nope'" in capsys.readouterr().out
