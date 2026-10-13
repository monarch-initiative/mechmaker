"""kg_registry.py, on a small canned registry. No network."""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "search-kg-registry" / "scripts" / "kg_registry.py"
def load_script(path: Path, name: str):
    """The script as a module under its own name: `bioregistry` is also a PyPI package."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


kg_registry = load_script(SCRIPT, "mechmaker_kg_registry")
bioregistry = load_script(ROOT / "skills" / "search-bioregistry" / "scripts" / "bioregistry.py",
                          "mechmaker_bioregistry")


def src(*ids, relation="prov:hadPrimarySource"):
    return [{"relation_type": relation, "source": i} for i in ids]


# A product is listed on its maker's page and on each source's page, as KG-Registry does.
KG_RAW = {"id": "kg-microbe.graph.raw", "category": "GraphProduct", "format": "kgx",
          "original_source": src("bacdive", "chebi", "kg-microbe")}
RESOURCES = [
    {"id": "kg-microbe", "name": "KG Microbe", "category": "KnowledgeGraph", "activity_status": "active",
     "domains": ["microbiology", "organisms"], "description": "A Knowledge Graph about microbes.",
     "license": {"id": "https://opensource.org/license/bsd-3-clause", "label": "BSD3"},
     "products": [KG_RAW]},
    {"id": "bacdive", "name": "BacDive", "category": "DataSource", "activity_status": "active",
     "domains": ["microbiology"], "synonyms": ["Bacterial Diversity Metadatabase"],
     "description": "Standardized bacterial strain information.", "license": "CC-BY-4.0",
     "products": [{"id": "bacdive.api", "category": "ProgrammingInterface",
                   "original_source": src("bacdive")},
                  KG_RAW,
                  {"id": "mediadive.portal", "category": "GraphicalInterface",
                   "original_source": src("mediadive"), "secondary_source": src("bacdive")}]},
    {"id": "mediadive", "name": "MediaDive", "category": "DataSource", "activity_status": "inactive",
     "domains": ["microbiology"], "description": "Cultivation media for microbes.",
     "use_instead": ["bacdive"],
     "products": [{"id": "mediadive.portal", "category": "GraphicalInterface",
                   "original_source": src("mediadive"), "secondary_source": src("bacdive")}]},
    {"id": "chebi", "name": "Chemical Entities of Biological Interest", "category": "Ontology",
     "activity_status": "active", "domains": ["chemistry and biochemistry"], "infores_id": "chebi",
     "description": "Small molecules.", "products": [KG_RAW]},
]


@pytest.fixture
def registry(tmp_path, monkeypatch):
    """The canned registry as a fresh cached copy, so nothing is downloaded."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    path = tmp_path / "mechmaker" / "kg-registry.jsonld"
    path.parent.mkdir()
    path.write_text(json.dumps({"@context": {}, "resources": RESOURCES}))
    monkeypatch.setattr(kg_registry, "download", lambda url: pytest.fail("downloaded with a fresh copy"))
    return path


def ids(hits):
    return [r["id"] for _, r in hits]


def test_search_needs_every_word_and_ranks_names_over_descriptions(registry):
    res = kg_registry.load()
    hits = ids(kg_registry.search(res, ["microbe"]))  # microbes, microbiology
    assert hits[0] == "kg-microbe" and set(hits) == {"kg-microbe", "bacdive", "mediadive"}
    assert ids(kg_registry.search(res, ["microbial", "strain"])) == []
    assert ids(kg_registry.search(res, ["microbe", "media"], any_term=True))[0] == "mediadive"


def test_search_matches_word_starts_and_endings_not_insides(registry):
    res = kg_registry.load()
    assert ids(kg_registry.search(res, ["bacterial"])) == ["bacdive"]  # synonym and description
    assert ids(kg_registry.search(res, ["robe"])) == []  # not inside "microbe"
    assert ids(kg_registry.search(res, ["bacterial strains"])) == ["bacdive"]  # a phrase, each word cut back
    assert ids(kg_registry.search(res, ["strain bacterial"])) == []  # in order


def test_search_filters_by_category_and_domain(registry):
    res = kg_registry.load()
    assert ids(kg_registry.search(res, [], categories=["datasource"])) == ["bacdive", "mediadive"]
    assert ids(kg_registry.search(res, [], domains=["chemistry and biochemistry"])) == ["chebi"]


def test_products_belong_to_their_maker_wherever_listed(registry):
    res = kg_registry.load()
    ids = {r["id"] for r in res}
    bacdive = kg_registry.find(res, "BacDive")
    assert kg_registry.sources(bacdive, ids) == {}  # kg-microbe's graph is not bacdive's
    detail = kg_registry.detail(res, bacdive, ids)
    assert detail["products"] == {"ProgrammingInterface": 1}
    assert [u["id"] for u in detail["used_by"]] == ["kg-microbe", "mediadive"]
    microbe = kg_registry.detail(res, kg_registry.find(res, "kg-microbe"), ids)
    assert [s["id"] for s in microbe["sources"]] == ["bacdive", "chebi"]  # itself left out
    assert microbe["license"] == "BSD3" and microbe["formats"] == ["kgx"]


def test_find_by_synonym_and_infores(registry):
    res = kg_registry.load()
    assert kg_registry.find(res, "bacterial diversity metadatabase")["id"] == "bacdive"
    assert kg_registry.find(res, "CHEBI")["id"] == "chebi"
    assert kg_registry.find(res, "nonesuch") is None


def test_show_prints_status_and_replacement(registry, capsys):
    assert kg_registry.main(["show", "mediadive"]) == 0
    out = capsys.readouterr().out
    assert "[inactive]" in out and "use instead: bacdive" in out
    assert "https://kghub.org/kg-registry/resource/mediadive/mediadive.html" in out


def test_exit_status(registry, capsys):
    assert kg_registry.main(["search", "nonesuch"]) == 1
    assert kg_registry.main(["search", "nonesuch", "--any"]) == 1
    assert "matched any word" in capsys.readouterr().err
    assert kg_registry.main(["show", "bacdive", "nonesuch"]) == 1
    assert kg_registry.main(["search"]) == 64
    assert kg_registry.main(["search", "x", "--category", "Thing"]) == 64
    capsys.readouterr()
    assert kg_registry.main(["used-by", "chebi", "--json"]) == 0
    out = capsys.readouterr().out
    assert json.loads(out)[0]["used_by"][0]["id"] == "kg-microbe"


def test_an_old_copy_is_used_when_the_download_fails(registry, monkeypatch, capsys):
    os.utime(registry, (0, 0))

    def fail(url):
        raise kg_registry.Unreachable("down")

    monkeypatch.setattr(kg_registry, "download", fail)
    assert kg_registry.main(["show", "chebi"]) == 0
    assert "using a copy" in capsys.readouterr().err
    registry.unlink()
    assert kg_registry.main(["show", "chebi"]) == 2


@pytest.mark.parametrize("name", ["cache_dir", "download", "stem", "word_pattern"])
def test_the_two_scripts_share_their_helpers(name):
    # Each skill stands alone, so each script carries its own copy; a fix to one goes in both.
    assert inspect.getsource(getattr(kg_registry, name)) == inspect.getsource(getattr(bioregistry, name))
