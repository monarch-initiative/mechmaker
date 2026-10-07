"""The generated Mech's ols.py, against a fake OLS: terms are found by CURIE, not by a guessed IRI."""

from __future__ import annotations

import importlib.util
import urllib.parse
from pathlib import Path

OLS_PY = Path(__file__).resolve().parents[1] / "template" / "src" / "{{mech_slug}}" / "ols.py"

EFO_IRI = "http://www.ebi.ac.uk/efo/EFO_0004340"
ENCODED = urllib.parse.quote(urllib.parse.quote(EFO_IRI, safe=""), safe="")


def _load():
    spec = importlib.util.spec_from_file_location("mech_ols", OLS_PY)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_parents_and_ancestors_follow_the_iri_ols_gives(monkeypatch):
    ols = _load()
    seen = []

    def get(url):
        seen.append(url)
        if "obo_id=" in url:
            return {"_embedded": {"terms": [{"iri": EFO_IRI}]}}
        assert f"/ontologies/efo/terms/{ENCODED}/" in url
        return {"_embedded": {"terms": [{"obo_id": "EFO:0004324", "label": "body weights and measures"}]}}

    monkeypatch.setattr(ols, "_get", get)
    assert ols.parents("EFO:0004340") == [("EFO:0004324", "body weights and measures")]
    assert ols.ancestors("EFO:0004340", "efo") == [("EFO:0004324", "body weights and measures")]
    assert seen[0].endswith("/ontologies/efo/terms?obo_id=EFO%3A0004340")
    assert seen[1].endswith(f"{ENCODED}/parents?size=500")
