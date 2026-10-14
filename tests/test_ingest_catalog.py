"""ingest_catalog.py and its copy of the catalog. No network."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "ingest-structured-data" / "scripts"


def load_script(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


ingest_catalog = load_script(SCRIPTS / "ingest_catalog.py", "mechmaker_ingest_catalog")
sys.path.insert(0, str(ROOT / "scripts"))
gen_docs = load_script(ROOT / "scripts" / "gen_docs.py", "mechmaker_gen_docs")


def test_json_copy_equals_copier_yml():
    """The skill's script reads a JSON copy; `uv run python scripts/gen_docs.py` rewrites it."""
    data = yaml.safe_load((ROOT / "copier.yml").read_text())
    assert ingest_catalog.load() == yaml.safe_load(data["ingest_catalog"]["default"])
    assert (SCRIPTS / "ingest_catalog.json").read_text() == gen_docs.ingest_json()


def test_reference_page_gives_each_conf_entry():
    """The Mech's structured-ingests skill sends agents to the page to copy an entry."""
    page = gen_docs.ingests()
    for key, entry in ingest_catalog.load().items():
        assert ingest_catalog.conf_entry(key, entry) == gen_docs.conf_entry(key, entry)
        assert f"```yaml\n{gen_docs.conf_entry(key, entry)}\n```" in page, key


def keys(hits):
    return [k for _, k in hits]


def test_search_by_words_species_and_source():
    catalog = ingest_catalog.load()
    assert keys(ingest_catalog.search(catalog, ["zebrafish", "phenotypes"])) == ["zfin"]
    assert "omim" in keys(ingest_catalog.search(catalog, ["infores:omim"]))
    assert set(keys(ingest_catalog.search(catalog, ["infores:mondo"]))) >= {"clinvar", "hpoa"}
    assert keys(ingest_catalog.search(catalog, ["pathway"]))[0] == "reactome"
    assert ingest_catalog.search(catalog, ["zebrafish", "pathway"]) == []
    assert "zfin" in keys(ingest_catalog.search(catalog, ["zebrafish", "pathway"], any_word=True))


def test_show_gives_the_conf_entry(capsys):
    assert ingest_catalog.main(["show", "omim"]) == 0
    out = capsys.readouterr().out
    entry = yaml.safe_load(out.split("conf/ingests.yaml:\n", 1)[1])
    assert entry == {"omim": {"kind": "release", "repo": "monarch-initiative/omim-ingest",
                              "sources": ["infores:omim"], "files": ["omim_gene_to_disease_edges.tsv"]}}


def test_unknown_key_and_usage(capsys):
    assert ingest_catalog.main(["show", "nosuch"]) == 1
    assert ingest_catalog.main(["search", "nothingmatchesthis"]) == 1
    assert ingest_catalog.main(["frobnicate"]) == 64


def test_releases_and_check_read_the_latest_release(monkeypatch, capsys):
    def latest(repo):
        assets = {f: 2_000_000 for f in ingest_catalog.load()["omim"]["files"]}
        if repo.endswith("omim-ingest"):
            assets["release-metadata.yaml"] = 600
        return {"tag": "2026-10-01", "published": "2026-10-01T05:06:55Z", "assets": assets}

    monkeypatch.setattr(ingest_catalog, "latest_release", latest)
    assert ingest_catalog.main(["releases", "omim"]) == 0
    assert "2.0 MB" in capsys.readouterr().out
    assert ingest_catalog.main(["releases", "--json", "omim"]) == 0
    assert json.loads(capsys.readouterr().out)["omim"]["tag"] == "2026-10-01"
    assert ingest_catalog.main(["check"]) == 1  # every other entry lacks its files here
    assert "omim         2026-10-01   ok" in capsys.readouterr().out
