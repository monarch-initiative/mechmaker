"""KGX exports: the edges, the evidence on them, and the Biolink checks, when Biolink is used."""

import json
import sys
from pathlib import Path

import pytest

from ingestmech import export, kgx
from ingestmech.validate import load

EXAMPLE = load(Path(__file__).parent / "data" / "example_record.yaml")
try:
    import biolink_model  # noqa: F401

    HAS_BIOLINK = True
except ImportError:
    HAS_BIOLINK = False
needs_biolink = pytest.mark.skipif(not HAS_BIOLINK, reason="biolink-model is installed only for Biolink KGX")


def cfg(biolink=True, **sections):
    return kgx.resolve({"biolink": biolink, "sections": sections})


def test_one_edge_per_bound_term_with_its_evidence():
    record = {"id": "x:1", "name": "one", "places": [
        {"preferred_term": "a", "term": {"id": "T:1", "label": "one"},
         "evidence": [{"reference": "PMID:1", "supports": "SUPPORT", "snippet": "A quote.",
                       "explanation": "Why."}]},
        {"preferred_term": "b", "term": {"id": "T:1", "label": "one"},
         "evidence": [{"reference": "url:https://example.org/x", "supports": "PARTIAL", "snippet": "More."}]},
        {"preferred_term": "unbound"},
    ]}
    nodes, edges = kgx.association_graph([record], cfg(places={"predicate": "biolink:related_to",
                                                                 "category": "biolink:GeographicLocation"}))
    assert {n["id"] for n in nodes} == {"x:1", "T:1"}
    assert len(edges) == 1  # two items, one term: one edge with both items' evidence
    e = edges[0]
    assert (e["subject"], e["predicate"], e["object"]) == ("x:1", "biolink:related_to", "T:1")
    assert e["publications"] == ["PMID:1", "https://example.org/x"]
    assert e["supporting_text"][0] == "[PMID:1] [SUPPORT] A quote. --- Explanation: Why."
    assert e["id"] == kgx.edge_id("x:1", "biolink:related_to", "T:1")  # stable


@needs_biolink
def test_biolink_checks():
    b = kgx.Biolink()
    nodes = [{"id": "x:1", "category": ["biolink:OrganismalEntity"]},
             {"id": "T:1", "category": ["biolink:Nope"]}]
    edges = [{"id": "e", "subject": "x:1", "predicate": "biolink:not_a_predicate", "object": "T:1"},
             {"id": "f", "subject": "x:1", "predicate": "biolink:related_to", "object": "T:9"}]
    problems, _ = kgx.check(nodes, edges, b, maximal=False)
    text = " ".join(problems)
    assert "abstract" in text and "biolink:Nope" in text and "not a Biolink predicate" in text
    assert "not exported" in text  # T:9


@needs_biolink
def test_a_predicate_that_does_not_fit_warns():
    b = kgx.Biolink()
    nodes = [{"id": "x:1", "category": ["biolink:NamedThing"]},
             {"id": "T:1", "category": ["biolink:PhenotypicFeature"]}]
    edges = [{"id": "e", "subject": "x:1", "predicate": "biolink:has_phenotype", "object": "T:1"}]
    problems, warnings = kgx.check(nodes, edges, b, maximal=False)
    assert problems == [] and "domain" in warnings[0]


def test_without_biolink_the_mech_uses_its_own_terms(monkeypatch):
    monkeypatch.setitem(sys.modules, "biolink_model", None)  # never loaded
    record = {"id": "x:1", "name": "one",
              "places": [{"preferred_term": "a", "term": {"id": "T:1", "label": "a"}}]}
    c = cfg(biolink=False, places={"predicate": f"{kgx.SLUG}:places"})
    nodes, edges = kgx.association_graph([record], c)
    assert {n["id"]: n["category"] for n in nodes} == {"x:1": [f"{kgx.SLUG}:{kgx.RECORD_CLASS}"],
                                                        "T:1": [f"{kgx.SLUG}:Term"]}
    assert kgx.check(nodes, edges, None, maximal=False) == ([], [])
    edges[0]["predicate"] = "places"
    problems, _ = kgx.check(nodes, edges, None, maximal=False)
    assert problems == ["places is not a CURIE: give it a prefix"]


@pytest.mark.skipif(kgx.settings()["biolink"] and not HAS_BIOLINK, reason="conf/kgx.yaml uses Biolink")
def test_both_formats_from_the_example_record(tmp_path):
    written, problems = export.export({"formats": ["kgx", "kgx_maximal"], "tabular_layout": "per_class"},
                                      [Path(__file__).parent / "data" / "example_record.yaml"], tmp_path)
    assert problems == []
    names = sorted(p.name for p in written)
    assert len(names) == 8
    nodes = (tmp_path / f"{kgx.SLUG}-kgx_maximal_nodes.jsonl").read_text(encoding="utf-8")
    maximal = [json.loads(line) for line in nodes.split("\n") if line]
    record = next(n for n in maximal if n["id"] == EXAMPLE["id"])
    assert f"{kgx.SLUG}:{kgx.RECORD_CLASS}" in record["category"]
