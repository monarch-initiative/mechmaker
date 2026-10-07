"""check_terms.py with --adapter, against a fake runoak that prints what OAK prints."""

from __future__ import annotations

import importlib.util
import sys
import urllib.error
import urllib.parse
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


def _fake_ols(seen):
    """A _get that knows one term per ontology, with the IRI that ontology gives it."""
    iris = {"EFO:0004340": "http://www.ebi.ac.uk/efo/EFO_0004340",
            "NCIT:C25464": "http://purl.obolibrary.org/obo/NCIT_C25464",
            "GO:0008150": "http://purl.obolibrary.org/obo/GO_0008150"}

    def get(url, tries=3):
        seen.append(url)
        curie = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("obo_id", [""])[0]
        if curie not in iris:
            raise urllib.error.HTTPError(url, 404, "x", {}, None)
        return {"_embedded": {"terms": [{"iri": iris[curie], "label": "a label"}]}}
    return get


def test_ols_adapter_names_the_ontology(mod, monkeypatch):
    monkeypatch.setattr(mod, "_get", _fake_ols([]))
    mod.ADAPTER = "ols:ncit"
    assert "/ontologies/ncit/terms/" in mod._term_url("NCIT:C25464")
    mod.ADAPTER = None
    assert "/ontologies/go/terms/" in mod._term_url("GO:0008150")


def test_ols_term_url_uses_the_iri_ols_gives(mod, monkeypatch):
    # EFO's IRIs are not OBO PURLs; building one from the CURIE finds nothing.
    seen = []
    monkeypatch.setattr(mod, "_get", _fake_ols(seen))
    mod.ADAPTER = "ols:efo"
    url = mod._term_url("EFO:0004340", "/parents")
    assert seen[0].endswith("/ontologies/efo/terms?obo_id=EFO%3A0004340")
    assert url.endswith("/terms/http%253A%252F%252Fwww.ebi.ac.uk%252Fefo%252FEFO_0004340/parents")
    assert mod.label("EFO:0004340") == "a label" and len(seen) == 1  # looked up once
    assert mod.label("EFO:9999999") is None and mod._term_url("EFO:9999999") is None


def test_outage_and_failure_differ_and_hide_keys(mod, capsys):
    args = ["--adapter", "bioportal:X", "under", "TINY:0000001"]
    with pytest.raises(mod.Unreachable) as outage:
        mod.main(args + ["TINY:0000666"])
    with pytest.raises(mod.OakFailed) as failed:
        mod.main(args + ["TINY:0000777"])
    for exc in (outage.value, failed.value):
        assert "SECRET123" not in str(exc) and "apikey=***" in str(exc)


def test_curie_without_a_colon_is_a_usage_error(mod, capsys):
    assert mod.main(["label", "GO0008150"]) == 64
    assert "Not a CURIE: GO0008150" in capsys.readouterr().err
    assert mod.main(["--adapter", "simpleobo:tiny.obo", "under", "TINY:0000001", "TINY0000003"]) == 64


def test_under_needs_a_term(mod, capsys):
    assert mod.main(["--adapter", "simpleobo:tiny.obo", "under", "TINY:0000001"]) == 64
    assert mod.main(["--adapter", "simpleobo:tiny.obo", "under", "--direct", "TINY:0000001"]) == 64
    assert "under needs a root and at least one term" in capsys.readouterr().err


def _http_error(code):
    def urlopen(url, timeout=None):
        raise urllib.error.HTTPError(url, code, "x", {}, None)
    return urlopen


def test_ols_404_is_missing_and_5xx_is_an_outage(mod, monkeypatch):
    monkeypatch.setattr(mod.time, "sleep", lambda s: None)
    monkeypatch.setattr(mod.urllib.request, "urlopen", _http_error(404))
    assert mod.label("GO:0000000") is None
    assert mod.parents("GO:0000000") == set() and mod.ancestors("GO:0000000") == set()
    monkeypatch.setattr(mod.urllib.request, "urlopen", _http_error(503))
    for call in (mod.label, mod.parents, mod.ancestors):
        with pytest.raises(mod.Unreachable, match="HTTP 503"):
            call("GO:0008150")


def test_ols_adapter_names_the_ontology_for_search(mod, monkeypatch):
    seen = []

    def get(url, tries=3):
        seen.append(url)
        return {"response": {"docs": []}}

    monkeypatch.setattr(mod, "_get", get)
    assert mod.main(["--adapter", "ols:ncit", "search", "-", "France"]) == 0
    assert "ontology=ncit" in seen[0]
