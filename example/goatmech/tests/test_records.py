"""`just new-record`: a minted id by default, and never an id already in use."""

import re

import pytest
import yaml

from goatmech import records
from goatmech.paths import SLUG


@pytest.fixture
def records_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(records, "RECORDS_DIR", tmp_path)
    return tmp_path


UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


def test_mint_id_is_unique_and_in_the_mechs_namespace():
    a, b = records.mint_id(), records.mint_id()
    assert a != b
    assert re.fullmatch(re.escape(SLUG) + ":" + UUID, a)


def test_an_id_in_use_is_refused(records_dir, capsys):
    (records_dir / "alpha.yaml").write_text(yaml.safe_dump({"id": "X:1", "name": "Alpha"}))
    assert records.main(["new", "--id", "X:1", "--name", "Beta", "--term-label", "beta"]) == 1
    assert "id X:1 is already used by" in capsys.readouterr().out
    assert sorted(p.name for p in records_dir.iterdir()) == ["alpha.yaml"]


def test_without_an_id_one_is_minted(records_dir, monkeypatch):
    # Capture what would be validated and written: a designed schema may need
    # more than a name, which is not what this test is about.
    written = []
    monkeypatch.setattr(records, "write_validated_record", lambda data, path, **_: written.append(data))
    assert records.main(["new", "--name", "Alpha"]) == 0
    assert records.main(["new", "--name", "Beta"]) == 0
    a, b = (d["id"] for d in written)
    assert a != b and re.fullmatch(re.escape(SLUG) + ":" + UUID, a)
    assert "record_term" not in written[0]
