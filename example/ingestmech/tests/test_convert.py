"""The conversion helper: DRAFT, validated, never overwriting, every skip reported."""

from pathlib import Path

from ingestmech.convert import Entry, Skip, convert, history_record
from ingestmech.history import HISTORY_SCHEMA_PATH
from ingestmech.validate import load, schema_errors

# Entries start from the Mech's own example record, so the tests keep passing
# when the schema gains required fields.
EXAMPLE = load(Path(__file__).parent / "data" / "example_record.yaml")


def entry(key, name, **extra):
    record = {k: v for k, v in EXAMPLE.items() if k not in ("curation_history", "status")}
    prefix = str(EXAMPLE["id"]).split(":", 1)[0]
    return Entry(key, {**record, "id": f"{prefix}:{key}", "name": name, **extra})


def test_dry_run_writes_nothing(tmp_path):
    report = convert([entry("a1", "Alpha")], source="Old KB", records_dir=tmp_path)
    assert [k for k, _ in report.written] == ["a1"]
    assert list(tmp_path.iterdir()) == []


def test_apply_writes_a_draft_with_its_source(tmp_path):
    report = convert([entry("a1", "Alpha", status="REVIEWED")], source="Old KB",
                     apply=True, records_dir=tmp_path, model="m")
    path = report.written[0][1]
    data = load(path)
    assert path == tmp_path / "alpha.yaml"
    assert data["status"] == "DRAFT"
    event = data["curation_history"][-1]
    assert event["action"] == "CREATE"
    assert "Old KB, entry a1" in event["description"]


def test_skips_invalid_and_reports_why(tmp_path):
    entries = [Skip("b2", "no name in the source"), entry("c3", "Gamma", not_a_slot=1)]
    report = convert(entries, source="Old KB", apply=True, records_dir=tmp_path)
    reasons = dict(report.skipped)
    assert reasons["b2"] == "no name in the source"
    assert "not_a_slot" in reasons["c3"]
    assert list(tmp_path.iterdir()) == []


def test_never_overwrites(tmp_path):
    (tmp_path / "alpha.yaml").write_text("keep: me\n")
    report = convert([entry("a1", "Alpha")], source="Old KB", apply=True, records_dir=tmp_path)
    assert [k for k, _ in report.exists] == ["a1"]
    assert (tmp_path / "alpha.yaml").read_text() == "keep: me\n"


def test_two_entries_one_file(tmp_path):
    report = convert([entry("a1", "Alpha"), entry("a2", "alpha")], source="Old KB", records_dir=tmp_path)
    assert [k for k, _ in report.written] == ["a1"]
    assert "same record file as entry a1" in dict(report.skipped)["a2"]


def test_limit_and_only(tmp_path):
    entries = [entry(k, k.upper()) for k in ("a1", "b2", "c3")]
    assert len(convert(entries, source="S", limit=2, records_dir=tmp_path).written) == 2
    only = convert(entries, source="S", only={"c3"}, records_dir=tmp_path)
    assert [k for k, _ in only.written] == ["c3"]


def test_history_record_is_valid(tmp_path):
    report = convert([entry("a1", "Alpha"), Skip("b2", "no name")], source="Old KB", records_dir=tmp_path)
    out, record = history_record(report, source="Old KB", script=Path("scripts/convert_old_kb.py"),
                                 actor="claude-code", model="m", human=False)
    assert schema_errors(record, "HistoryRecord", HISTORY_SCHEMA_PATH) == []
    assert out.parent.name == "convert-old-kb"
    assert "b2 (no name)" in record["events"][0]["details"]
