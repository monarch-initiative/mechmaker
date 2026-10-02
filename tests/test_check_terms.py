"""check_terms.py with --adapter, against a fake runoak that prints what OAK prints."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "make-mech" / "scripts" / "check_terms.py"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="the fake runoak is a shell script")

# Ancestors and parents come from OAK's Python API: a fake python that tells
# the two -c programs apart and prints what each prints, one CURIE per line.
# $3 is the adapter.
FAKE_PY = r'''#!/bin/sh
case "$2" in
  *relationships*)
    case "$4" in
      TINY:0000003) echo TINY:0000002 ;;
      TINY:0000002) echo TINY:0000001 ;;
    esac
    exit 0 ;;
esac
case "$4" in
  TINY:0000003) printf 'TINY:0000001\nTINY:0000002\n' ;;
  TINY:0000009) ;;
  TINY:0000666) echo "requests.exceptions.ConnectTimeout: Max retries, url=/x?apikey=SECRET123" >&2; exit 1 ;;
  TINY:0000777) echo "TypeError: something broke, apikey=SECRET123" >&2; exit 1 ;;
esac
'''

# What `runoak -i simpleobo:tests/data/tiny.obo ...` prints, verbatim.
FAKE = r'''#!/bin/sh
shift 2  # -i ADAPTER
case "$1" in
  info)
    case "$2" in
      TINY:0000001) echo "TINY:0000001 ! tiny thing" ;;
      TINY:0000002) echo "TINY:0000002 ! small widget" ;;
      TINY:0000003) echo "TINY:0000003 ! very small widget" ;;
      TINY:0000009) echo "TINY:0000009 ! unrelated thing" ;;
      TINY:0000666) echo "TINY:0000666 ! timing out" ;;
      TINY:0000777) echo "TINY:0000777 ! breaking" ;;
      *) echo "$2 ! None" ;;
    esac ;;
  search) echo "TINY:0000002 ! small widget" ;;
esac
'''


@pytest.fixture
def mod(tmp_path, monkeypatch):
    fake = tmp_path / "runoak"
    fake.write_text(FAKE)
    fake.chmod(0o755)
    fake_py = tmp_path / "python"
    fake_py.write_text(FAKE_PY)
    fake_py.chmod(0o755)
    spec = importlib.util.spec_from_file_location("check_terms", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "OAK", [str(fake)])
    monkeypatch.setattr(m, "OAK_PY", [str(fake_py)])
    return m


def test_label_found_and_missing(mod, capsys):
    assert mod.main(["--adapter", "simpleobo:tiny.obo", "label", "TINY:0000003", "TINY:9"]) == 1
    out = capsys.readouterr().out
    assert "TINY:0000003\tvery small widget" in out
    assert "TINY:9\tNOT FOUND" in out


def test_under_reads_ancestors(mod, capsys):
    args = ["--adapter", "simpleobo:tiny.obo", "under", "TINY:0000001"]
    assert mod.main(args + ["TINY:0000003"]) == 0
    assert mod.main(args + ["TINY:0000009"]) == 1
    assert "TINY:0000009\tNOT under TINY:0000001" in capsys.readouterr().out


def test_under_direct_reads_parents(mod, capsys):
    rc = mod.main(["--adapter", "simpleobo:tiny.obo", "under", "--direct", "TINY:0000001",
                   "TINY:0000003", "TINY:0000001"])
    out = capsys.readouterr().out
    assert rc == 1  # a grandchild, and the root itself, are not direct children
    assert "TINY:0000003\tNOT a direct child of TINY:0000001" in out
    assert "TINY:0000001\tNOT a direct child of TINY:0000001" in out
    rc = mod.main(["--adapter", "simpleobo:tiny.obo", "under", "--direct", "TINY:0000002", "TINY:0000003"])
    assert rc == 0 and "a direct child of TINY:0000002" in capsys.readouterr().out


def test_search(mod, capsys):
    assert mod.main(["--adapter", "simpleobo:tiny.obo", "search", "-", "l~widget"]) == 0
    assert "TINY:0000002\tsmall widget" in capsys.readouterr().out


def test_ols_adapter_names_the_ontology(mod):
    mod.ADAPTER = "ols:ncit"
    assert "/ontologies/ncit/terms/" in mod._term_url("NCIT:C25464")
    mod.ADAPTER = None
    assert "/ontologies/go/terms/" in mod._term_url("GO:0008150")


def test_outage_and_failure_differ_and_hide_keys(mod, capsys):
    args = ["--adapter", "bioportal:X", "under", "TINY:0000001"]
    with pytest.raises(mod.Unreachable) as outage:
        mod.main(args + ["TINY:0000666"])
    with pytest.raises(mod.OakFailed) as failed:
        mod.main(args + ["TINY:0000777"])
    for exc in (outage.value, failed.value):
        assert "SECRET123" not in str(exc) and "apikey=***" in str(exc)
