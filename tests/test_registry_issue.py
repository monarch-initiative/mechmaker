"""registry_issue.py, on an example Mech's registry draft and on drafts that lack things."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "register-mech" / "scripts" / "registry_issue.py"
sys.path.insert(0, str(SCRIPT.parent))

import registry_issue  # noqa: E402

GOAT = ROOT / "example" / "goatmech"


def sections(body: str) -> dict[str, str]:
    parts = re.split(r"^### (.+)\n\n", body, flags=re.M)[1:]
    return {k: v.strip() for k, v in zip(parts[::2], parts[1::2], strict=True)}


def test_goatmech_issue(capsys):
    assert registry_issue.main([str(GOAT)]) == 0
    s = sections(capsys.readouterr().out)
    assert list(s)[:2] == ["Name", "Repository URL"]
    assert s["Name"] == "GoatMech"
    assert s["Repository URL"] == "https://github.com/monarch-initiative/goatmech"
    assert s["Record count and date"] == "3 as of 2026-09-30"
    assert s["Ontologies used to ground records"] == "VBO, VT, NCIT, UO, NCBITaxon"
    assert s["Do AI agents generate or maintain most of the content?"] == "Yes"
    assert s["Human review"] == "Pull request review"
    assert s["Relations to other Mechs"] == "- follows_pattern_of dismech"
    # The whole draft rides along, unchanged.
    draft = (GOAT / "registry" / "goatmech.md").read_text().rstrip()
    assert f"````markdown\n{draft}\n````" in s["Draft entry"]


def test_title(capsys):
    assert registry_issue.main([str(GOAT), "--title"]) == 0
    assert capsys.readouterr().out == "Add this Mech: GoatMech\n"


def test_missing_fields_read_no_response(tmp_path, capsys):
    (tmp_path / "registry").mkdir()
    entry = {"name": "TinyMech", "repository": "https://github.com/o/tinymech",
             "curation": {"human_review": "unknown"}}
    (tmp_path / "registry" / "tinymech.md").write_text(f"---\n{yaml.safe_dump(entry)}---\nNothing yet.\n")
    assert registry_issue.main([str(tmp_path)]) == 0
    s = sections(capsys.readouterr().out)
    assert s["Homepage or browser URL"] == registry_issue.NO_RESPONSE
    assert s["Record count and date"] == registry_issue.NO_RESPONSE
    assert s["Do AI agents generate or maintain most of the content?"] == registry_issue.NO_RESPONSE
    assert s["Human review"] == "Not documented"


def test_no_draft(tmp_path, capsys):
    assert registry_issue.main([str(tmp_path)]) == 2
    assert "No registry draft" in capsys.readouterr().err
