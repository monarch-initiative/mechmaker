"""mech_registry.py, on a small canned registry and canned GitHub answers. No network."""

from __future__ import annotations

import base64
import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills"


def load_script(path: Path, name: str):
    """The script as a module under its own name."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mech_registry = load_script(SCRIPTS / "search-mechregistry" / "scripts" / "mech_registry.py",
                            "mechmaker_mech_registry")
kg_registry = load_script(SCRIPTS / "search-kg-registry" / "scripts" / "kg_registry.py",
                          "mechmaker_kg_registry")

MECHS = [
    {"id": "culturemech", "name": "CultureMech", "record_type": "a culture-medium recipe",
     "maturity": "curating", "activity_status": "active", "record_count": 6320,
     "domains": ["microbiology", "nutrition"],
     "ontologies": ["CHEBI", "FOODON"], "collection": ["x-mech-suite"],
     "description": "Microbial culture-media recipes.", "repository": "https://github.com/CultureBotAI/CultureMech",
     "record_count_source": {"path": "data/merged"},
     "data_sources": [{"name": "MediaDive", "url": "https://mediadive.dsmz.de/",
                       "relation_type": "prov:hadPrimarySource"}],
     "license": {"spdx_id": "CC0-1.0"},
     "cross_references": [{"target": "dismech", "relation": "follows_pattern_of"}]},
    {"id": "communitymech", "name": "CommunityMech", "record_type": "a microbial community",
     "maturity": "curating", "activity_status": "active", "record_count": 458,
     "domains": ["microbiology"], "ontologies": ["NCBITaxon", "ENVO"], "description": "Communities.",
     "repository": "https://github.com/CultureBotAI/CommunityMech", "data_sources": [],
     "cross_references": [{"target": "culturemech", "relation": "consumes",
                           "description": "Community records name the medium by CultureMech id."}]},
    {"id": "ai-gene-review", "name": "ai-gene-review", "record_type": "a gene product and the review of its "
     "existing GO annotations", "maturity": "curating", "activity_status": "active", "record_count": 6760,
     "domains": ["genomics"], "ontologies": ["GO", "ECO"], "description": "GO annotation reviews.",
     "repository": "https://github.com/ai4curation/ai-gene-review",
     "data_sources": [{"name": "GOA", "url": "https://www.ebi.ac.uk/QuickGO/"}]},
]


@pytest.fixture
def mechs(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    path = tmp_path / "mechmaker" / "mechregistry.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"@context": {}, "mechs": MECHS}))
    monkeypatch.setattr(mech_registry, "download", lambda url: pytest.fail("downloaded with a fresh copy"))
    return mech_registry.load()


def ids(hits):
    return [m["id"] for _, m in hits]


def test_search_by_words_and_filters(mechs):
    assert ids(mech_registry.search(mechs, ["culture media"])) == ["culturemech"]
    assert ids(mech_registry.search(mechs, ["mediadive"])) == ["culturemech"]  # a data source
    assert ids(mech_registry.search(mechs, [], ontologies=["chebi"])) == ["culturemech"]
    assert ids(mech_registry.search(mechs, [], domains=["microbiology"])) == ["communitymech", "culturemech"]
    assert ids(mech_registry.search(mechs, ["community", "recipe"], any_term=True)) == [
        "communitymech", "culturemech"]


def test_overlap_says_what_is_shared(mechs):
    rows = mech_registry.overlap(mechs, ontologies=["GO", "ECO"], domains=["genomics"],
                                 sources=["GOA"], words="gene annotation")
    assert [r["id"] for r in rows] == ["ai-gene-review"]
    (row,) = rows
    assert row["ontologies"] == ["ECO", "GO"] and row["data_sources"] == ["GOA"]
    assert row["record_words"] == ["gene", "annotation"] and row["domains"] == ["genomics"]
    assert mech_registry.overlap(mechs, ontologies=["UBERON"]) == []


def test_show_lists_links_both_ways(mechs):
    d = mech_registry.detail(mechs, mech_registry.find(mechs, "CultureMech"))
    assert d["links_out"][0]["id"] == "dismech"
    assert d["links_in"] == [{"id": "communitymech", "relation": "consumes",
                              "description": "Community records name the medium by CultureMech id."}]
    assert d["license"] == "CC0-1.0" and d["records_path"] == "data/merged"


ANSWERS = "_commit: 0.2.0-28-gb88834f\n_src_path: gh:monarch-initiative/mechmaker\nmech_slug: goatmech\n" \
          "records_dir: data/breeds\nontologies: [VBO]\n"


def fake_github(answers: str | None, scripts: list[str], release: dict | None):
    def entry(path, kind="file"):
        return {"path": path, "name": path.rsplit("/", 1)[-1], "type": kind}

    def answer(path, raw=False):
        if path == "/repos/o/goatmech":
            return {"default_branch": "main", "pushed_at": "2026-10-01T00:00:00Z",
                    "license": {"spdx_id": "MIT"}}
        if path == "/repos/o/goatmech/commits/main":
            return {"sha": "a" * 40}
        if path.startswith("/repos/o/goatmech/contents/.copier-answers.yml"):
            return {"content": base64.b64encode(answers.encode()).decode()} if answers else None
        if path.startswith("/repos/o/goatmech/contents/scripts?"):
            return [entry(p) for p in scripts]
        if path.startswith("/repos/o/goatmech/contents/src?"):
            return [entry("src/goatmech", "dir")]
        if path.startswith("/repos/o/goatmech/contents/src/goatmech?"):
            return [entry("src/goatmech/convert.py"), entry("src/goatmech/render.py"),
                    entry("src/goatmech/fetch", "dir")]
        if path.startswith("/repos/o/goatmech/contents/src/goatmech/fetch?"):
            return [entry("src/goatmech/fetch/__init__.py"), entry("src/goatmech/fetch/oba.py")]
        if path.startswith("/repos/o/goatmech/contents/data/breeds?"):
            return [entry("data/breeds/boer.yaml"), entry("data/breeds/saanen.yaml")]
        if path == "/repos/o/goatmech/releases/latest":
            return release
        return None
    return answer


def test_repo_reads_a_mechmaker_mech(monkeypatch):
    scripts = ["scripts/convert_oba.py", "scripts/check_links.py", "scripts/repair_sparse.py",
               "scripts/test_load.py", "scripts/fetch_breeds.py"]
    release = {"tag_name": "v1", "html_url": "https://x/v1", "assets": [{"name": "goatmech-records.jsonl"}]}
    monkeypatch.setattr(mech_registry, "github", fake_github(ANSWERS, scripts, release))
    mech = {"id": "goatmech", "repository": "https://github.com/o/goatmech", "record_count": 2}
    r = mech_registry.repo(mech)
    assert r["mechmaker"] and r["mechmaker_version"] == "0.2.0-28-gb88834f"
    assert r["commit"] == "a" * 40 and r["records_dir"] == "data/breeds"
    assert r["scripts"] == ["scripts/convert_oba.py", "scripts/fetch_breeds.py", "src/goatmech/convert.py",
                            "src/goatmech/fetch/oba.py"]
    assert r["other_scripts"] == 3  # check_links, repair_sparse (not "parse"), test_load
    assert r["convert_helper"] == "src/goatmech/convert.py"
    assert r["record_sample"] == ["data/breeds/boer.yaml", "data/breeds/saanen.yaml"]
    assert r["release"]["assets"] == ["goatmech-records.jsonl"]
    assert r["records_url"] == f"https://github.com/o/goatmech/tree/{'a' * 40}/data/breeds"


def test_repo_names_another_template(monkeypatch, capsys):
    other = "_commit: v0.4.1\n_src_path: https://github.com/linkml/linkml-project-copier\n"
    monkeypatch.setattr(mech_registry, "github", fake_github(other, [], None))
    r = mech_registry.repo({"id": "goatmech", "repository": "https://github.com/o/goatmech"})
    assert not r["mechmaker"] and r["template"].endswith("linkml-project-copier")
    mech_registry.print_repo(r)
    out = capsys.readouterr().out
    assert "made from https://github.com/linkml/linkml-project-copier, not mechmaker" in out
    assert "no release" in out


def test_repo_that_is_not_on_github():
    r = mech_registry.repo({"id": "x", "repository": "https://gitlab.com/o/x"})
    assert "not a GitHub repository" in r["error"]


def test_exit_status(mechs, monkeypatch, capsys):
    assert mech_registry.main(["search", "nonesuch"]) == 1
    assert mech_registry.main(["search", "nonesuch", "--any"]) == 1
    assert "matched any word" in capsys.readouterr().err
    assert mech_registry.main(["search"]) == 64
    assert mech_registry.main(["overlap"]) == 64
    assert mech_registry.main(["show", "culturemech", "nonesuch"]) == 1

    def refused(path, raw=False):
        raise mech_registry.Unreachable("GitHub refused: rate limited")

    monkeypatch.setattr(mech_registry, "github", refused)
    assert mech_registry.main(["repo", "culturemech"]) == 2


@pytest.mark.parametrize("name", ["cache_dir", "download", "stem", "word_pattern"])
def test_shares_its_helpers_with_the_other_registry_scripts(name):
    assert inspect.getsource(getattr(mech_registry, name)) == inspect.getsource(getattr(kg_registry, name))


def test_template_modules_are_the_templates():
    # A mechmaker Mech's own modules are not scripts that bring data in, except convert.py.
    names = set()
    for path in (ROOT / "template" / "src" / "{{mech_slug}}").iterdir():
        name = path.name.removesuffix(".jinja")
        name = name.split("%}")[1].split("{%")[0] if "%}" in name else name  # {% if x %}name.py{% endif %}
        if name.endswith(".py"):
            names.add(name)
    assert names - {"convert.py"} == mech_registry.TEMPLATE_MODULES
    assert not mech_registry.ingests("load.py") and not mech_registry.ingests("schema_import.py")
    assert mech_registry.ingests("convert.py") and mech_registry.ingests("fetch_bacdive.py")


@pytest.mark.parametrize("word,finds,misses", [
    ("species", "species", "spectrum"),
    ("analysis", "analyses", "analog"),
    ("process", "processes", "proceed"),
    ("microbe", "microbial", "robe"),
])
def test_stem(word, finds, misses):
    pattern = mech_registry.word_pattern(word)
    assert pattern.search(finds) and not pattern.search(misses)


@pytest.mark.parametrize("phrase,text", [
    ("culture media", "culture-media recipes"), ("sea sample", "a sea-water sample"),
    ("culture medium", "a culture medium")])
def test_phrases_cross_hyphens(phrase, text):
    assert mech_registry.word_pattern(phrase).search(text)


def test_sources_match_on_whole_words(mechs):
    assert mech_registry.same_source("GOA", "GOA")
    assert mech_registry.same_source("GOA", "goa files")
    assert not mech_registry.same_source("GO", "JGI GOLD")
    assert not mech_registry.same_source("", "GOA") and not mech_registry.same_source("GOA", "")
    assert mech_registry.overlap(mechs, sources=["Media"]) == []  # not MediaDive


def test_an_empty_source_is_no_source(mechs, capsys):
    assert mech_registry.main(["overlap", "--source", ""]) == 64
    assert mech_registry.main(["overlap", "--source", " ", "--ontology", "GO"]) == 0
    assert "shares data sources" not in capsys.readouterr().out


def test_refresh_after_the_command(mechs, monkeypatch):
    calls = []

    def fake(url):
        calls.append(url)
        return json.dumps({"mechs": MECHS}).encode()

    monkeypatch.setattr(mech_registry, "download", fake)
    assert mech_registry.main(["search", "culture", "--refresh"]) == 0
    assert mech_registry.main(["--refresh", "show", "culturemech"]) == 0
    assert len(calls) == 2


def test_a_broken_copy_or_download_is_never_used(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    path = tmp_path / "mechmaker" / "mechregistry.json"
    path.parent.mkdir()
    path.write_text('{"mechs": [')  # cut short
    monkeypatch.setattr(mech_registry, "download", lambda url: b'{"error": "maintenance"}')
    assert mech_registry.main(["show", "culturemech"]) == 2
    assert path.read_text() == '{"mechs": ['  # the error page was not cached
    monkeypatch.setattr(mech_registry, "download", lambda url: json.dumps({"mechs": MECHS}).encode())
    assert mech_registry.main(["show", "culturemech"]) == 0
    assert json.loads(path.read_text())["mechs"][0]["id"] == "culturemech"


def test_repo_keeps_what_it_fetched_when_github_stops(mechs, monkeypatch, capsys):
    def repo(m):
        if m["id"] == "communitymech":
            raise mech_registry.Unreachable("GitHub refused: rate limited")
        return {"id": m["id"], "error": "", "repository": "o/x"}

    monkeypatch.setattr(mech_registry, "repo", repo)
    assert mech_registry.main(["repo", "culturemech", "communitymech", "ai-gene-review", "--json"]) == 2
    assert [r["id"] for r in json.loads(capsys.readouterr().out)] == ["culturemech"]
