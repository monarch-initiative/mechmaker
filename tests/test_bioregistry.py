"""bioregistry.py, on a small canned registry. No network."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "search-bioregistry" / "scripts" / "bioregistry.py"
def load_script(path: Path, name: str):
    """The script as a module under its own name: `bioregistry` is also a PyPI package."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bioregistry = load_script(SCRIPT, "mechmaker_bioregistry")

REGISTRY = {
    "mondo": {"name": "Mondo Disease Ontology", "owners": [{"name": "Monarch Initiative"}],
              "contact": {"name": "A Curator", "email": "c@example.org", "orcid": "0000-0000-0000-0000"},
              "preferred_prefix": "MONDO", "pattern": "^\\d{7}$",
              "example": "0000001", "uri_format": "http://purl.obolibrary.org/obo/MONDO_$1",
              "keywords": ["ontology", "disease"], "description": "Harmonized diseases.",
              "mappings": {"ols": "mondo", "obofoundry": "mondo", "miriam": "mondo"}},
    "go": {"name": "Gene Ontology", "preferred_prefix": "GO", "pattern": "^\\d{7}$", "banana": "GO",
           "uri_format": "http://purl.obolibrary.org/obo/GO_$1", "description": "Gene functions."},
    "pubmed": {"name": "PubMed", "preferred_prefix": "pubmed", "pattern": "^\\d+$", "synonyms": ["PMID"],
               "uri_format": "https://pubmed.ncbi.nlm.nih.gov/$1/", "description": "Biomedical literature."},
    "ncbitaxon": {"name": "NCBI Taxonomy", "preferred_prefix": "NCBITaxon",
                  "pattern": "^(\\d+)|([a-zA-Z_]+)$", "synonyms": ["taxid"], "uri_format": "http://purl.obolibrary.org/obo/NCBITaxon_$1",
                  "mappings": {"miriam": "taxonomy"}, "description": "Taxa.\n\nA long second part."},
    "jcm": {"name": "Japan Collection of Microorganisms", "preferred_prefix": "JCM", "pattern": "^\\d+$",
            "uri_format": "https://www.jcm.riken.jp/cgi-bin/jcm/jcm_number?JCM=$1",
            "description": "Microbial strains."},
    "oldstrain": {"name": "Old Strain Catalog", "preferred_prefix": "oldstrain", "deprecated": True,
                  "has_canonical": "jcm", "description": "Microbial strains, retired."},
}


@pytest.fixture
def registry(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    path = tmp_path / "mechmaker" / "bioregistry.json"
    path.parent.mkdir()
    path.write_text(json.dumps(REGISTRY))
    monkeypatch.setattr(bioregistry, "download", lambda url: pytest.fail("downloaded with a fresh copy"))
    return bioregistry.load()


def test_resolve_any_case_or_synonym(registry):
    assert bioregistry.resolve(registry, "MONDO") == "mondo"
    assert bioregistry.resolve(registry, "PMID") == "pubmed"
    assert bioregistry.resolve(registry, "TaxID") == "ncbitaxon"
    assert bioregistry.resolve(registry, "nonesuch") is None


def test_search_ranks_and_leaves_deprecated_out(registry):
    assert [p for _, p in bioregistry.search(registry, ["microbial", "strain"])] == ["jcm"]
    assert "oldstrain" in [p for _, p in bioregistry.search(registry, ["strain"], deprecated=True)]
    assert [p for _, p in bioregistry.search(registry, ["disease"])] == ["mondo"]
    assert {p for _, p in bioregistry.search(registry, ["ontology"])} == {"go", "mondo"}  # name or keyword


def test_curie_checks_pattern_and_standard_form(registry):
    ok = bioregistry.check_curie(registry, "mondo:0005015")
    assert ok["ok"] and ok["standard"] == "MONDO:0005015"
    assert ok["uri"] == "http://purl.obolibrary.org/obo/MONDO_0005015"
    assert "preferred prefix is MONDO" in ok["note"]
    assert bioregistry.check_curie(registry, "go:GO:0008150")["standard"] == "GO:0008150"
    assert bioregistry.check_curie(registry, "PMID:123")["uri"] == "https://pubmed.ncbi.nlm.nih.gov/123/"
    assert not bioregistry.check_curie(registry, "MONDO:12")["ok"]
    assert bioregistry.check_curie(registry, "NCBITaxon:562")["ok"]
    assert not bioregistry.check_curie(registry, "NCBITaxon:562abc")["ok"]  # the whole id, not its start
    assert "unknown prefix" in bioregistry.check_curie(registry, "foo:1")["error"]
    assert "no colon" in bioregistry.check_curie(registry, "MONDO0005015")["error"]
    assert "use jcm" in bioregistry.check_curie(registry, "oldstrain:1")["warning"]


@pytest.mark.parametrize("iri,standard", [
    ("http://purl.obolibrary.org/obo/MONDO_0005015", "MONDO:0005015"),
    ("https://pubmed.ncbi.nlm.nih.gov/123/", "pubmed:123"),
    ("http://identifiers.org/taxonomy/9606", "NCBITaxon:9606"),
    ("https://identifiers.org/MONDO:0005015", "MONDO:0005015"),
    ("https://bioregistry.io/ncbitaxon:9606", "NCBITaxon:9606"),
])
def test_iri_to_curie(registry, iri, standard):
    result = bioregistry.parse_iri(registry, iri)
    assert result["ok"] and result["standard"] == standard
    assert "note" not in result


def test_show_names_contact_and_owners(registry, capsys):
    assert bioregistry.main(["show", "mondo"]) == 0
    out = capsys.readouterr().out
    assert "contact: A Curator (c@example.org, ORCID 0000-0000-0000-0000)" in out
    assert "owners: Monarch Initiative" in out


def test_iri_that_fits_nothing(registry):
    assert not bioregistry.parse_iri(registry, "https://example.org/x")["ok"]


def test_show_keeps_the_first_paragraph(registry, capsys):
    assert bioregistry.main(["show", "taxid"]) == 0
    out = capsys.readouterr().out
    assert "uri prefix: http://purl.obolibrary.org/obo/NCBITaxon_" in out
    assert "description: Taxa.  (more: --json)" in out and "second part" not in out


def test_exit_status(registry, capsys):
    assert bioregistry.main(["curie", "MONDO:0005015"]) == 0
    assert bioregistry.main(["curie", "MONDO:0005015", "MONDO:1"]) == 1
    assert bioregistry.main(["search", "nonesuch"]) == 1
    assert bioregistry.main(["search", "nonesuch", "--any"]) == 1
    assert "matched any word" in capsys.readouterr().err
    assert bioregistry.main(["show", "nonesuch"]) == 1
    assert bioregistry.main(["frobnicate"]) == 64


def test_no_copy_and_no_answer_is_exit_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

    def fail(url):
        raise bioregistry.Unreachable("down")

    monkeypatch.setattr(bioregistry, "download", fail)
    assert bioregistry.main(["show", "mondo"]) == 2
    path = tmp_path / "mechmaker" / "bioregistry.json"
    path.parent.mkdir()
    path.write_text(json.dumps(REGISTRY))
    os.utime(path, (0, 0))
    assert bioregistry.main(["show", "mondo"]) == 0
    assert "using a copy" in capsys.readouterr().err
