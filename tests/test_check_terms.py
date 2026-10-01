"""check_terms.py with --adapter, against a fake runoak that prints what OAK prints."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "make-mech" / "scripts" / "check_terms.py"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the fake runoak is a shell script")

# What `runoak -i simpleobo:tests/data/tiny.obo ...` prints, verbatim.
FAKE = r'''#!/bin/sh
shift 2  # -i ADAPTER
case "$1" in
  info)
    case "$2" in
      TINY:0000001) echo "TINY:0000001 ! tiny thing" ;;
      TINY:0000003) echo "TINY:0000003 ! very small widget" ;;
      TINY:0000009) echo "TINY:0000009 ! unrelated thing" ;;
      *) echo "$2 ! None" ;;
    esac ;;
  ancestors)
    printf 'id\tlabel\n'
    case "$4" in
      TINY:0000003) printf 'TINY:0000001\ttiny thing\nTINY:0000003\tvery small widget\n'
                    printf 'TINY:0000002\tsmall widget\n' ;;
      TINY:0000009) printf 'TINY:0000009\tunrelated thing\n' ;;
    esac ;;
  search) echo "TINY:0000002 ! small widget" ;;
esac
'''


@pytest.fixture
def mod(tmp_path, monkeypatch):
    fake = tmp_path / "runoak"
    fake.write_text(FAKE)
    fake.chmod(0o755)
    spec = importlib.util.spec_from_file_location("check_terms", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "OAK", [str(fake)])
    return m


def test_label_found_and_missing(mod, capsys):
    assert mod.main(["--adapter", "simpleobo:tiny.obo", "label", "TINY:0000003", "TINY:9"]) == 1
    out = capsys.readouterr().out
    assert "TINY:0000003\tvery small widget" in out
    assert "TINY:9\tNOT FOUND" in out


def test_under_reads_the_ancestor_table(mod, capsys):
    args = ["--adapter", "simpleobo:tiny.obo", "under", "TINY:0000001"]
    assert mod.main(args + ["TINY:0000003"]) == 0
    assert mod.main(args + ["TINY:0000009"]) == 1
    assert "TINY:0000009\tNOT under TINY:0000001" in capsys.readouterr().out


def test_search(mod, capsys):
    assert mod.main(["--adapter", "simpleobo:tiny.obo", "search", "-", "l~widget"]) == 0
    assert "TINY:0000002\tsmall widget" in capsys.readouterr().out


def test_ols_adapter_names_the_ontology(mod):
    mod.ADAPTER = "ols:ncit"
    assert "/ontologies/ncit/terms/" in mod._term_url("NCIT:C25464")
    mod.ADAPTER = None
    assert "/ontologies/go/terms/" in mod._term_url("GO:0008150")
