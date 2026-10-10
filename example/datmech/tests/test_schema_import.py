"""just import-schema: copy and reference modes, on a small external schema."""

import shutil
from pathlib import Path

import pytest
import yaml

from datmech import schema_import
from datmech.paths import RECORD_CLASS, SCHEMA_DIR, SCHEMA_PATH
from datmech.validate import load, schema_errors

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
    before = (schema_dir / SCHEMA_PATH.name).read_text(encoding="utf-8")
    assert run("--apply") == 1
    assert "'status'" in capsys.readouterr().out
    assert (schema_dir / SCHEMA_PATH.name).read_text(encoding="utf-8") == before


def test_copy_folds_the_class_in_and_keeps_its_rules(schema_dir):
    assert run("--rename", "status=sample_status", "--apply") == 0
    path = schema_dir / SCHEMA_PATH.name
    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
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
    before = (schema_dir / SCHEMA_PATH.name).read_text(encoding="utf-8")
    assert run("--rename", "status=sample_status") == 0
    assert (schema_dir / SCHEMA_PATH.name).read_text(encoding="utf-8") == before


def test_reference_refuses_a_name_the_checks_depend_on(schema_dir, capsys):
    assert run("--mode", "reference", "--apply") == 1
    assert "use --mode copy" in capsys.readouterr().out


def test_reference_imports_the_source_unchanged(schema_dir, tmp_path, monkeypatch):
    source = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    source["classes"]["Sample"]["slots"].remove("status")
    del source["slots"]["status"]
    del source["enums"]
    variant = tmp_path / "fieldwork.yaml"
    variant.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    args = [str(variant), "--record-class", "Sample", "--mode", "reference", "--apply"]
    assert schema_import.main(args) == 0
    stored = schema_dir / "fieldwork.yaml"
    assert yaml.safe_load(stored.read_text(encoding="utf-8")) == source  # unchanged
    schema = yaml.safe_load((schema_dir / SCHEMA_PATH.name).read_text(encoding="utf-8"))
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


def split_source(root: Path, *, status: bool = True) -> Path:
    """The source schema in three files: Sample, then CollectionSite beside it, then the
    status enum one folder up, so imports nest and one leaves the source's folder."""
    source = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    head = {k: source[k] for k in ("id", "name", "prefixes", "default_prefix", "default_range")}
    site = {**head, "id": f"{head['id']}/site", "name": "site", "imports": ["linkml:types"],
            "classes": {"CollectionSite": source["classes"].pop("CollectionSite")}}
    if status:
        site["imports"].append("../common/status")
        common = {**head, "id": f"{head['id']}/status", "name": "status", "imports": ["linkml:types"],
                  "enums": source.pop("enums")}
        (root / "common").mkdir(parents=True)
        (root / "common" / "status.yaml").write_text(yaml.safe_dump(common), encoding="utf-8")
    else:
        source["classes"]["Sample"]["slots"].remove("status")
        del source["slots"]["status"]
        del source["enums"]
        site["imports"].append("../common/site")
        (root / "common").mkdir(parents=True)
        (root / "common" / "site.yaml").write_text(yaml.safe_dump(
            {**head, "id": f"{head['id']}/common", "name": "common_site", "imports": ["linkml:types"],
             "classes": site.pop("classes")}), encoding="utf-8")
    source["imports"].append("site")
    (root / "fieldwork").mkdir(parents=True)
    (root / "fieldwork" / "site.yaml").write_text(yaml.safe_dump(site), encoding="utf-8")
    main = root / "fieldwork" / "fieldwork.yaml"
    main.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    return main


@pytest.fixture
def served(tmp_path, monkeypatch):
    """tmp_path/www as if on a web site, so the URL tests need no network."""
    import urllib.parse

    www = tmp_path / "www"
    www.mkdir()
    site = "https://schemas.example.org"

    def download(url):
        found = urllib.parse.urlparse(url)
        path = www / found.path.lstrip("/")
        if found.netloc != "schemas.example.org" or not path.is_file():
            raise schema_import.Problem(f"could not fetch {url}: HTTP Error 404: Not Found")
        return path.read_bytes()

    monkeypatch.setattr(schema_import, "download", download)
    return www, site


def test_a_failed_download_is_a_problem():
    with pytest.raises(schema_import.Problem, match="could not fetch"):
        schema_import.download("http:///no-host")  # fails at once, without the network


def test_a_url_brings_its_imports_at_any_depth(schema_dir, served):
    www, url = served
    split_source(www / "schemas")
    args = [f"{url}/schemas/fieldwork/fieldwork.yaml", "--record-class", "Sample",
            "--rename", "status=sample_status", "--apply"]
    assert schema_import.main(args) == 0
    path = schema_dir / SCHEMA_PATH.name
    schema = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert "CollectionSite" in schema["classes"]  # an import
    assert "SampleStatus" in schema["enums"]  # an import's import, from ../common
    assert schema_errors(record(sample_status="MELTED"), schema=path)
    assert sorted(p.name for p in schema_dir.rglob("*.yaml")) == sorted(
        p.name for p in SCHEMA_DIR.rglob("*.yaml"))  # nothing written but the schema


def test_a_missing_import_is_a_problem(schema_dir, tmp_path, served, capsys):
    main = split_source(tmp_path / "local")
    (tmp_path / "local" / "common" / "status.yaml").unlink()
    assert schema_import.main([str(main), "--record-class", "Sample"]) == 1
    out = capsys.readouterr().out
    assert "imports ../common/status" in out and "Nothing was written." in out

    www, url = served
    split_source(www / "schemas")
    (www / "schemas" / "common" / "status.yaml").unlink()
    assert schema_import.main([f"{url}/schemas/fieldwork/fieldwork.yaml", "--record-class", "Sample"]) == 1
    out = capsys.readouterr().out
    assert "could not fetch" in out and "Nothing was written." in out


def test_reference_refuses_an_import_from_a_parent_folder(schema_dir, tmp_path, capsys):
    main = split_source(tmp_path / "local", status=False)
    before = sorted(schema_dir.rglob("*"))
    assert schema_import.main([str(main), "--record-class", "Sample", "--mode", "reference", "--apply"]) == 1
    out = capsys.readouterr().out
    assert "outside its folder" in out and "use --mode copy" in out
    assert sorted(schema_dir.rglob("*")) == before


def referenceable() -> dict:
    """The source without the status slot, which reference mode refuses."""
    source = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
    source["classes"]["Sample"]["slots"].remove("status")
    del source["slots"]["status"]
    del source["enums"]
    return source


def test_reference_never_replaces_a_file_beside_the_schema(schema_dir, tmp_path, capsys):
    vendored = (schema_dir / "history.yaml").read_bytes()
    source = referenceable()
    source["imports"].append("history")  # its own history.yaml, beside it
    (tmp_path / "fieldwork.yaml").write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    own = {"id": "https://example.org/history", "name": "history", "imports": ["linkml:types"]}
    (tmp_path / "history.yaml").write_text(yaml.safe_dump(own), encoding="utf-8")
    args = [str(tmp_path / "fieldwork.yaml"), "--record-class", "Sample",
            "--mode", "reference", "--apply"]
    assert schema_import.main(args) == 1
    assert "would replace history.yaml" in capsys.readouterr().out
    assert (schema_dir / "history.yaml").read_bytes() == vendored


@pytest.mark.parametrize("text, said", [("classes: [", "not valid YAML"),
                                        ("- a list\n", "not a LinkML schema")])
def test_a_malformed_local_source_is_a_problem(schema_dir, tmp_path, capsys, text, said):
    bad = tmp_path / "bad.yaml"
    bad.write_text(text, encoding="utf-8")
    assert schema_import.main([str(bad), "--record-class", "Sample"]) == 1
    out = capsys.readouterr().out
    assert said in out and "Nothing was written." in out


def test_reference_needs_a_source_name(schema_dir, tmp_path, capsys):
    source = referenceable()
    del source["name"]
    nameless = tmp_path / "nameless.yaml"
    nameless.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    assert schema_import.main([str(nameless), "--record-class", "Sample", "--mode", "reference"]) == 1
    assert "has no name" in capsys.readouterr().out
