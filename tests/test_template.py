"""Render the template under several answer sets and check what comes out."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

import copier
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
ANSWERS = ROOT / "tests" / "answers"

BASE = {
    "author_name": "Test Maintainer",
    "author_email": "test@example.org",
    "github_org": "example-org",
}

SCENARIOS = {
    "habitat": yaml.safe_load((ANSWERS / "habitat.yml").read_text()),
    "minimal": {
        **BASE,
        "mech_name": "MinimalMech",
        "record_class": "Widget",
        "ontologies": [],
        "causal_graphs": False,
        "include_site": False,
        "include_claude_hook": False,
    },
    "disease": {
        **BASE,
        "mech_name": "TinyDisMech",
        "record_class": "Disease",
        "identity_prefix": "MONDO",
        "identity_root": "MONDO:0000001",
        "ontologies": ["HP", "CL", "UBERON", "GO_BP", "GO_MF", "GO_CC", "CHEBI", "MAXO"],
        "domains": ["biomedical", "clinical"],
        "taxon_scope": "NCBITaxon:9606",
        "collection": "monarch",
        "data_license": "CC0-1.0",
        "code_license": "MIT",
    },
    "all-ontologies": {
        **BASE,
        "mech_name": "EverythingMech",
        "record_class": "ThingOfInterest",
        "ontologies": [
            "GO_BP", "GO_MF", "GO_CC", "CL", "UBERON", "CHEBI", "HP", "MONDO", "NCBITaxon",
            "ENVO", "PATO", "OBI", "UO", "PR", "SO", "MAXO", "FOODON",
        ],
        "code_license": "Apache-2.0",
    },
}

ALL_WORKFLOWS = [
    "sweep", "docs", "comment-guard", "close-fork-prs", "release-records", "warm-reference-cache",
    "pypi-publish", "claude", "review", "triage", "dedupe", "pr-shepherd", "curation-scanner",
    "literature-scan", "compliance", "post-review",
]
AGENT_WORKFLOWS = {"claude", "review", "triage", "dedupe", "pr-shepherd", "curation-scanner",
                   "literature-scan", "compliance", "post-review"}
# Workflow files each answer produces.
WORKFLOW_FILES = {
    "sweep": ["sweep.yaml"], "docs": ["docs.yaml"], "comment-guard": ["comment-guard.yaml"],
    "close-fork-prs": ["close-fork-prs.yaml"], "release-records": ["release-records.yaml"],
    "warm-reference-cache": ["warm-reference-cache.yaml"], "pypi-publish": ["pypi-publish.yaml"],
    "claude": ["claude.yaml"], "review": ["review.yaml"], "triage": ["triage.yaml"],
    "dedupe": ["dedupe.yaml", "auto-close-duplicates.yaml"], "pr-shepherd": ["pr-shepherd.yaml"],
    "curation-scanner": ["curation-scanner.yaml"], "literature-scan": ["literature-scan.yaml"],
    "compliance": ["compliance.yaml"], "post-review": ["post-review.yaml"],
}

SCENARIOS["all-workflows"] = {
    **SCENARIOS["habitat"],
    "mech_name": "EveryWorkflowMech",
    "mech_slug": "everyworkflowmech",
    "workflows": ALL_WORKFLOWS,
    "agent_schedules": True,
    "langfuse": True,
}
# Ontologies outside the catalog, read through three kinds of OAK adapter.
TINY = {"prefix": "TINY", "root": "TINY:0000001", "root_label": "tiny thing", "noun": "tiny entity",
        "adapter": "simpleobo:ontologies/tiny.obo", "uri": "http://example.org/TINY_"}
SCENARIOS["extras"] = {
    **BASE,
    "mech_name": "ExtraMech",
    "record_class": "Specimen",
    "term_backend": "sqlite",
    # Records are breeds: direct children of Goat breed, as in GoatMech.
    "identity_prefix": "VBO",
    "identity_root": "VBO:0400025",
    "identity_direct_only": True,
    "ontologies": ["VBO", "VT", "NCIT_COUNTRY"],
    "extra_ontologies": [
        TINY,
        # Not a real BioPortal ontology: the render is tested, not the lookup.
        {"prefix": "BPX", "root": "BPX:1", "root_label": "example root",
         "noun": "clinical finding", "adapter": "bioportal:BPX", "uri": "https://example.org/BPX_"},
        {"prefix": "ZFA", "root": "ZFA:0100000", "root_label": "zebrafish anatomical entity",
         "noun": "anatomy", "slot": "anatomy_terms"},
    ],
    "workflows": ["sweep"],
    # KGX in the Mech's own terms, with no Biolink.
    "output_formats": ["yaml", "json", "sqlite", "kgx", "kgx_maximal"],
    "kgx_biolink": False,
}
SCENARIOS["minimal"]["workflows"] = []
ALL_FORMATS = ["yaml", "json", "jsonld", "ttl", "sqlite", "duckdb", "sql", "csv", "tsv", "kgx", "kgx_maximal"]
SCENARIOS["disease"].update({"site_palette": "brown", "site_theme": "light", "deep_research": True,
                             "output_formats": ALL_FORMATS, "tabular_layout": "flat",
                             "load_targets": ["mongodb", "neo4j"]})
SCENARIOS["all-workflows"].update({"site_palette": "yellow", "site_accent": "amber", "site_theme": "dark"})

VENDORED_MD5 = {
    "mech_shared.yaml": "3cf80648642fcd1f824529bc40c572a5",
    "history.yaml": "3742bc2068b637868c48aba406f6569d",
}

# Rendered files that legitimately contain Jinja or just syntax of their own.
OWN_BRACES = {"justfile", "index.html", "record.html", "style.css"}


def render(dest: Path, data: dict) -> Path:
    # vcs_ref="HEAD": without it Copier copies the latest release tag, not the
    # working tree, and the tests would check the release instead of the branch.
    copier.run_copy(str(ROOT), str(dest), data=data, defaults=True, unsafe=True, quiet=True,
                    vcs_ref="HEAD")
    return dest


@pytest.fixture(scope="module", params=list(SCENARIOS))
def generated(request, tmp_path_factory) -> tuple[str, dict, Path]:
    data = SCENARIOS[request.param]
    dest = tmp_path_factory.mktemp(request.param)
    render(dest, data)
    answers = yaml.safe_load((dest / ".copier-answers.yml").read_text())
    return request.param, answers, dest


def test_answers_recorded(generated):
    _, answers, _ = generated
    assert answers["mech_slug"]
    assert "ontology_catalog" not in answers


def test_no_unrendered_template_syntax(generated):
    _, _, dest = generated
    for f in dest.rglob("*"):
        if f.is_file() and f.name not in OWN_BRACES and ".git" not in f.parts:
            text = f.read_text(errors="ignore")
            assert "{{" not in text.replace("${{", ""), f
            assert "{%" not in text, f
        assert not f.name.endswith(".jinja"), f


class _AnyTagLoader(yaml.SafeLoader):
    """mkdocs.yml uses a !!python/name tag; parse it without importing anything."""


_AnyTagLoader.add_multi_constructor("", lambda loader, suffix, node: None)


def test_yaml_parses(generated):
    _, _, dest = generated
    for f in list(dest.rglob("*.yaml")) + list(dest.rglob("*.yml")):
        yaml.load(f.read_text(), Loader=_AnyTagLoader)


def test_docs_site_config(generated):
    _, answers, dest = generated
    cfg = yaml.load((dest / "mkdocs.yml").read_text(), Loader=_AnyTagLoader)
    assert cfg["site_name"] == answers["mech_name"]
    nav = yaml.dump(cfg["nav"])
    assert "elements/index.md" in nav and "structure.md" in nav
    assert ("records/index.html" in nav) == answers["include_site"]
    for page in ["index.md", "DOMAIN.md", "CURATION.md", "WORKFLOWS.md"]:
        assert (dest / "docs" / page).exists(), page


def test_recipes_run_on_bash_3(generated):
    """macOS ships bash 3.2, which has no globstar: `shopt -s globstar` stops
    the recipe before it checks anything."""
    _, _, dest = generated
    assert not re.search(r"shopt[^\n]*globstar", (dest / "justfile").read_text())


def test_named_recipes_exist(generated):
    """Every `just <recipe>` the agent's instructions name is in the justfile.
    Recipes gated off by an answer (render with include_site: false) must not
    be named either, or the agent runs into "recipe not found"."""
    _, _, dest = generated
    recipes = set(re.findall(r"^([a-z][a-z0-9-]*)[^\n=]*:", (dest / "justfile").read_text(), re.M))
    texts = [dest / "CLAUDE.md", dest / "README.md", *(dest / ".claude").rglob("*.md"),
             *(dest / "conf").glob("*.yaml")]
    missing = set()
    for path in texts:
        for name in re.findall(r"(?:^|`)\s*(?:# )?just ([a-z][a-z0-9-]*)", path.read_text(), re.M):
            if name not in recipes:
                missing.add((str(path.relative_to(dest)), name))
    assert not missing, sorted(missing)


def test_schema_pages_are_in_a_folder_per_kind(generated):
    """Every Mech has a Term class and a term slot. In one folder their pages
    are Term.md and term.md, one file where case is ignored, and the docs
    build fails there. A folder per kind keeps them apart."""
    _, answers, dest = generated
    source = (dest / "src" / answers["mech_slug"] / "docs.py").read_text()
    assert "subfolder_type_separation=True" in source


def test_registry_entry_front_matter(generated):
    _, answers, dest = generated
    text = (dest / "registry" / f"{answers['mech_slug']}.md").read_text()
    header = yaml.safe_load(text.split("---")[1])
    assert header["id"] == answers["mech_slug"]
    assert header["domains"]
    assert all(p["id"].startswith(answers["mech_slug"] + ".") for p in header["products"])


def test_vendored_modules_byte_identical(generated):
    _, answers, dest = generated
    schema_dir = dest / "src" / answers["mech_slug"] / "schema"
    for name, md5 in VENDORED_MD5.items():
        assert hashlib.md5((schema_dir / name).read_bytes()).hexdigest() == md5


def test_schema_structure(generated):
    _, answers, dest = generated
    slug = answers["mech_slug"]
    schema = yaml.safe_load((dest / "src" / slug / "schema" / f"{slug}.yaml").read_text())
    rc = answers["record_class"]
    assert schema["classes"][rc]["tree_root"] is True
    catalog = yaml.safe_load((ROOT / "copier.yml").read_text())["ontology_catalog"]["default"]
    catalog = yaml.safe_load(catalog)
    for key in answers["ontologies"]:
        entry = catalog[key]
        assert entry["descriptor"] in schema["classes"]
        assert entry["enum"] in schema["enums"]
        assert entry["prefix"] in schema["prefixes"]
        assert entry["slot"] in schema["classes"][rc]["slots"]
    for extra in answers.get("extra_ontologies") or []:
        assert extra["prefix"] in schema["prefixes"]
        roots = [e["reachable_from"]["source_nodes"][0] for e in schema["enums"].values()
                 if "reachable_from" in e]
        assert extra["root"] in roots
    if answers.get("identity_prefix"):
        assert "IdentityTerm" in schema["enums"]
    assert ("mechanisms" in schema["classes"][rc]["slots"]) == answers["causal_graphs"]


def test_identity_rule_follows_answers(generated):
    _, answers, dest = generated
    slug = answers["mech_slug"]
    schema = yaml.safe_load((dest / "src" / slug / "schema" / f"{slug}.yaml").read_text())
    if not answers.get("identity_prefix"):
        assert "IdentityTerm" not in schema["enums"]
        return
    query = schema["enums"]["IdentityTerm"]["reachable_from"]
    direct = answers.get("identity_direct_only", False)
    assert (query["is_direct"], query["include_self"]) == (direct, not direct)
    assert ("check-identity" in (dest / "src" / slug / "qc.py").read_text())
    claude = (dest / "CLAUDE.md").read_text()
    assert (f"a record id's parents must include {answers['identity_root']}" in claude) == direct


def test_optional_parts(generated):
    _, answers, dest = generated
    slug = answers["mech_slug"]
    assert (dest / "src" / slug / "render.py").exists() == answers["include_site"]
    assert (dest / "src" / slug / "templates").exists() == answers["include_site"]
    assert (dest / ".claude" / "hooks").exists() == answers["include_claude_hook"]
    settings = yaml.safe_load((dest / ".claude" / "settings.json").read_text())
    assert ("hooks" in settings) == answers["include_claude_hook"]


def test_the_browser_is_rendered_not_committed(generated):
    """The docs build renders the browser fresh; a committed pages/ would only go stale (#44)."""
    _, answers, dest = generated
    assert "pages/" in (dest / ".gitignore").read_text().splitlines()
    assert "render-check" not in (dest / "justfile").read_text()
    assert "render-check" not in (dest / "src" / answers["mech_slug"] / "qc.py").read_text()


def test_oak_config_covers_every_prefix(generated):
    _, answers, dest = generated
    slug = answers["mech_slug"]
    schema = yaml.safe_load((dest / "src" / slug / "schema" / f"{slug}.yaml").read_text())
    adapters = yaml.safe_load((dest / "conf" / "oak_config.yaml").read_text())["ontology_adapters"]
    bound = {e["reachable_from"]["source_nodes"][0].split(":")[0] for e in schema["enums"].values()
             if "reachable_from" in e}
    assert bound <= set(adapters)


def test_adapters_follow_answers(generated):
    name, answers, dest = generated
    adapters = yaml.safe_load((dest / "conf" / "oak_config.yaml").read_text())["ontology_adapters"]
    if name != "extras":
        assert not (dest / "ontologies").exists()
        return
    assert adapters["VT"] == "sqlite:obo:vt"  # term_backend: sqlite
    assert adapters["NCIT"] == "sqlite:obo:ncit"
    assert adapters["TINY"] == "simpleobo:ontologies/tiny.obo"
    assert adapters["BPX"] == "bioportal:BPX"
    assert adapters["ZFA"] == "ols:zfa"  # an extra's default
    assert "simpleobo:ontologies/tiny.obo" in (dest / "ontologies" / "README.md").read_text()
    slug = answers["mech_slug"]
    schema = yaml.safe_load((dest / "src" / slug / "schema" / f"{slug}.yaml").read_text())
    slots = schema["classes"][answers["record_class"]]["slots"]
    want = {"breeds", "traits", "countries", "tiny_entities", "clinical_findings", "anatomy_terms"}
    assert want <= set(slots)
    assert {"TinyEntityTerm", "ClinicalFindingTerm", "AnatomyTerm"} <= set(schema["enums"])
    for wf in ("qc.yaml", "sweep.yaml"):
        assert "secrets.BIOPORTAL_API_KEY" in (dest / ".github" / "workflows" / wf).read_text()


def test_agents_that_check_terms_get_the_bioportal_key(tmp_path):
    term_checkers = ["claude", "review", "post-review", "compliance", "curation-scanner"]
    dest = render(tmp_path / "bp", {**SCENARIOS["extras"], "workflows": term_checkers})
    for key in term_checkers:
        text = (dest / ".github" / "workflows" / f"{key}.yaml").read_text()
        assert yaml.safe_load(text)["env"]["BIOPORTAL_API_KEY"] == "${{ secrets.BIOPORTAL_API_KEY }}", key


def test_no_bioportal_secret_without_bioportal(generated):
    name, _, dest = generated
    if name == "extras":
        return
    for wf in (dest / ".github" / "workflows").glob("*.yaml"):
        assert "BIOPORTAL" not in wf.read_text(), wf.name


@pytest.mark.parametrize("extras", [
    [{"prefix": "VT", "root": "VT:0000001", "noun": "trait"}],  # no root_label
    [{"prefix": "VT", "root": "GO:0008150", "root_label": "x", "noun": "trait"}],  # root not VT
    [{"prefix": "V T", "root": "V T:1", "root_label": "x", "noun": "trait"}],  # bad prefix
    "VT:0000001",  # not a list
])
def test_bad_extra_ontologies_rejected(tmp_path, extras):
    data = {**BASE, "mech_name": "BadExtraMech", "record_class": "Thing", "extra_ontologies": extras}
    with pytest.raises(Exception):  # noqa: B017
        render(tmp_path / "out", data)


@pytest.mark.parametrize("extras", [
    # The prefix of a picked catalog ontology (GO_BP).
    [{"prefix": "GO", "root": "GO:0003674", "root_label": "molecular_function", "noun": "activity"}],
    # The slot of a picked catalog ontology: CHEBI's chemical_entities.
    [{"prefix": "PO", "root": "PO:0025131", "root_label": "plant anatomical entity",
      "noun": "plant structure", "slot": "chemical_entities"}],
    # A default slot that collides: "organism" pluralizes to NCBITaxon's organisms.
    [{"prefix": "PO", "root": "PO:0025131", "root_label": "plant anatomical entity", "noun": "organism"}],
    # Two extras with one prefix, and two with one slot.
    [{"prefix": "PO", "root": "PO:0025131", "root_label": "plant anatomical entity",
      "noun": "plant structure"},
     {"prefix": "PO", "root": "PO:0009012", "root_label": "plant structure development stage",
      "noun": "plant stage"}],
    [{"prefix": "PO", "root": "PO:0025131", "root_label": "plant anatomical entity",
      "noun": "plant structure"},
     {"prefix": "ZFA", "root": "ZFA:0100000", "root_label": "zebrafish anatomical entity",
      "noun": "fish part", "slot": "plant_structures"}],
])
def test_duplicate_extra_ontologies_rejected(tmp_path, extras):
    data = {**BASE, "mech_name": "DupExtraMech", "record_class": "Thing",
            "ontologies": ["GO_BP", "CHEBI", "NCBITaxon"], "extra_ontologies": extras}
    with pytest.raises(Exception, match="already"):
        render(tmp_path / "out", data)


def test_distinct_extra_ontologies_accepted(tmp_path):
    extras = [{"prefix": "PO", "root": "PO:0025131", "root_label": "plant anatomical entity",
               "noun": "plant structure"}]
    data = {**BASE, "mech_name": "PlantExtraMech", "record_class": "Thing",
            "ontologies": ["GO_BP", "CHEBI", "NCBITaxon"], "extra_ontologies": extras, "workflows": []}
    dest = render(tmp_path / "out", data)
    assert "PO" in yaml.safe_load((dest / "conf" / "oak_config.yaml").read_text())["ontology_adapters"]


@pytest.mark.parametrize("records_dir", ["", "  ", "data/widgets/", "/data/widgets", "../widgets",
                                         "data/../widgets", "data//widgets", "./data", "data/my widgets"])
def test_bad_records_dir_rejected(tmp_path, records_dir):
    data = {**BASE, "mech_name": "BadDirMech", "record_class": "Widget", "records_dir": records_dir}
    with pytest.raises(Exception):  # noqa: B017
        render(tmp_path / "out", data)


def test_export_settings_follow_answers(generated):
    _, answers, dest = generated
    cfg = yaml.safe_load((dest / "conf" / "export.yaml").read_text())
    assert cfg["formats"] == answers["output_formats"]
    want = answers.get("tabular_layout") or "per_class"
    assert cfg["tabular_layout"] == want


def test_linkml_store_only_when_chosen(generated):
    _, answers, dest = generated
    deps = tomllib.loads((dest / "pyproject.toml").read_text())["project"]["dependencies"]
    store = [d for d in deps if d.startswith("linkml-store")]
    targets = answers.get("load_targets") or []
    assert bool(store) == ("duckdb" in answers["output_formats"] or bool(targets))
    for t in targets:
        assert t in store[0]
    load_cfg = yaml.safe_load((dest / "conf" / "load.yaml").read_text())
    assert sorted(load_cfg["targets"]) == sorted(targets)


def test_kgx_settings_follow_answers(generated):
    _, answers, dest = generated
    deps = tomllib.loads((dest / "pyproject.toml").read_text())["project"]["dependencies"]
    kgx = {"kgx", "kgx_maximal"} & set(answers["output_formats"])
    biolink = answers.get("kgx_biolink", True)
    assert any(d.startswith("biolink-model") for d in deps) == bool(kgx and biolink)
    cfg = yaml.safe_load((dest / "conf" / "kgx.yaml").read_text())
    assert cfg["biolink"] is biolink
    slug = answers["mech_slug"]
    schema = yaml.safe_load((dest / "src" / slug / "schema" / f"{slug}.yaml").read_text())
    record_slots = set(schema["classes"][answers["record_class"]]["slots"])
    assert set(cfg["sections"]) <= record_slots
    prefix = "biolink:" if biolink else f"{slug}:"
    assert cfg["record_category"].startswith(prefix)
    assert all(s["category"].startswith(prefix) and s["predicate"].startswith(prefix)
               for s in cfg["sections"].values())


def test_no_output_format_is_rejected(tmp_path):
    data = {**BASE, "mech_name": "NoFormatMech", "record_class": "Thing", "output_formats": []}
    with pytest.raises(Exception):  # noqa: B017
        render(tmp_path / "out", data)


def test_workflow_files_match_answer(generated):
    _, answers, dest = generated
    got = {p.name for p in (dest / ".github" / "workflows").glob("*.yaml")}
    want = {"qc.yaml"} | {f for key in answers["workflows"] for f in WORKFLOW_FILES[key]}
    assert got == want


def test_agent_support_only_with_agents(generated):
    _, answers, dest = generated
    uses_agents = bool(AGENT_WORKFLOWS & set(answers["workflows"]))
    gh = dest / ".github"
    for path in [gh / "agent-config.yaml", gh / "actions" / "setup-agent" / "action.yml",
                 gh / "prompts", gh / "scripts" / "check_agent_run.py", gh / "scripts" / "render_prompt.py"]:
        assert path.exists() == uses_agents, path
    for key in AGENT_WORKFLOWS - {"claude", "dedupe"}:
        assert (gh / "prompts" / f"{key}.md").exists() == (key in answers["workflows"])


def test_agent_workflows_share_pin_and_credentials(generated):
    _, answers, dest = generated
    pins, creds = set(), set()
    for key in AGENT_WORKFLOWS & set(answers["workflows"]):
        text = (dest / ".github" / "workflows" / WORKFLOW_FILES[key][0]).read_text()
        pins |= set(re.findall(r"anthropics/claude-code-action@\S+", text))
        creds |= {line.strip() for line in text.splitlines() if "claude_code_oauth_token:" in line}
        assert "--max-turns" in text and "check_agent_run.py" in text, key
        assert "dangerously-skip-permissions" not in text, key
    if AGENT_WORKFLOWS & set(answers["workflows"]):
        assert len(pins) == 1 and len(creds) == 1, (pins, creds)


def test_review_reads_the_pr_as_data_and_posts_without_a_model(tmp_path):
    dest = render(tmp_path / "review", SCENARIOS["all-workflows"])
    jobs = yaml.safe_load((dest / ".github" / "workflows" / "review.yaml").read_text())["jobs"]
    review, publish = jobs["review"]["steps"], jobs["publish"]["steps"]

    # Forks stop before anything is checked out.
    assert review[0]["name"].startswith("Refuse pull requests from forks")
    assert "isCrossRepository" in review[0]["run"]
    # The agent's job can write nothing, and nothing in it runs the PR's code:
    # the tools are the default branch's, the PR's files are data in pr/.
    assert all(v in ("read", "none") for v in jobs["review"]["permissions"].values())
    assert not any("gh pr checkout" in s.get("run", "") for s in review)
    checkouts = [s for s in review if "actions/checkout" in s.get("uses", "")]
    assert checkouts[0]["with"]["ref"] == "${{ github.event.repository.default_branch }}"
    assert checkouts[1]["with"]["path"] == "pr" and checkouts[1]["with"]["persist-credentials"] is False
    agent = next(s for s in review if "claude-code-action" in s.get("uses", ""))
    assert "--json-schema" in agent["with"]["claude_args"]
    assert "gh pr review" not in agent["with"]["claude_args"]
    # Posting has no model; only it holds the reviewer App's key.
    assert not any("claude-code-action" in s.get("uses", "") for s in publish)
    assert jobs["publish"]["permissions"]["pull-requests"] == "write"
    assert not any("MECH_REVIEWER" in str(s) for s in review)
    assert (dest / ".github" / "scripts" / "review-publish.js").exists()


# Agents that hold a write token on purpose. Each reads only text a person
# with write access put in front of it.
WRITING_AGENTS = {"claude", "curation-scanner", "compliance"}


def test_agents_that_read_untrusted_text_cannot_write(tmp_path):
    dest = render(tmp_path / "readers", SCENARIOS["all-workflows"])
    for key in AGENT_WORKFLOWS - WRITING_AGENTS:
        for name in WORKFLOW_FILES[key]:
            flow = yaml.safe_load((dest / ".github" / "workflows" / name).read_text())
            for job_name, job in flow["jobs"].items():
                agent = next((s for s in job["steps"] if "claude-code-action" in s.get("uses", "")), None)
                if agent is None:
                    continue
                where = f"{name}:{job_name}"
                perms = job.get("permissions", flow.get("permissions"))
                assert all(v in ("read", "none") for v in perms.values()), where
                assert not any("create-github-app-token" in s.get("uses", "") for s in job["steps"]), where
                args = agent["with"]["claude_args"]
                assert "--json-schema" in args, where
                for tool in ("gh issue create", "gh issue edit", "gh issue comment", "gh pr comment",
                             "gh pr review", "gh label", "git push"):
                    assert f"Bash({tool}" not in args, (where, tool)


def test_triage_applies_only_its_own_labels(tmp_path):
    dest = render(tmp_path / "triage", SCENARIOS["all-workflows"])
    jobs = yaml.safe_load((dest / ".github" / "workflows" / "triage.yaml").read_text())["jobs"]
    agent = next(s for s in jobs["choose"]["steps"] if "claude-code-action" in s.get("uses", ""))
    schema = json.loads(re.search(r"--json-schema '(.+)'", agent["with"]["claude_args"]).group(1))
    offered = set(schema["properties"]["labels"]["items"]["enum"])
    script = jobs["apply"]["steps"][0]["with"]["script"]
    listed = re.search(r"ALLOWED = new Set\(\[(.+?)\]\)", script, re.S).group(1)
    allowed = set(re.findall(r"'([\w-]+)'", listed))
    assert offered == allowed
    assert not allowed & {"scope-override", "duplicate-pending", "needs-human", "editorial", "literature"}
    labels = {x["name"] for x in yaml.safe_load((dest / ".github" / "labels.yaml").read_text())}
    assert allowed <= labels
    # `curation` hands an issue to an agent that can push; a stranger's issue does not get it.
    assert "author_association" in script


@pytest.mark.skipif(shutil.which("actionlint") is None, reason="actionlint not installed")
def test_actionlint(tmp_path):
    dest = render(tmp_path / "lint", SCENARIOS["all-workflows"])
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    args = ["actionlint", "-no-color"]
    if shutil.which("shellcheck"):
        args += ["-shellcheck", shutil.which("shellcheck")]
    result = subprocess.run(args, cwd=dest, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def _action_refs(root: Path) -> set[tuple[str, str]]:
    refs = set()
    for f in list(root.rglob("*.yml")) + list(root.rglob("*.yaml")):
        if ".github" not in f.parts:
            continue
        for m in re.finditer(r"uses:\s*([\w.-]+/[\w.-]+)(?:/[\w./-]+)?@([\w.-]+)", f.read_text()):
            refs.add((m.group(1), m.group(2)))
    return refs


@pytest.mark.slow
def test_every_action_ref_exists(tmp_path):
    """actionlint does not check that a tag exists. A missing one fails CI at "Set up job"."""
    dest = render(tmp_path / "refs", SCENARIOS["all-workflows"])
    refs = _action_refs(dest) | _action_refs(ROOT)
    assert refs
    missing = []
    for repo in sorted({r for r, _ in refs}):
        out = ""
        for _ in range(3):  # GitHub is sometimes slow to answer; retry before failing
            try:
                out = subprocess.run(["git", "ls-remote", f"https://github.com/{repo}"],
                                     capture_output=True, text=True, timeout=60).stdout
                break
            except subprocess.TimeoutExpired:
                continue
        names = {line.split("\t")[1].removesuffix("^{}") for line in out.splitlines() if "\t" in line}
        shas = {line.split("\t")[0] for line in out.splitlines() if "\t" in line}
        for r, ref in refs:
            if r != repo:
                continue
            ok = ref in shas if re.fullmatch(r"[0-9a-f]{40}", ref) else (
                f"refs/tags/{ref}" in names or f"refs/heads/{ref}" in names)
            if not ok:
                missing.append(f"{repo}@{ref}")
    assert not missing, missing


def test_site_settings_follow_answers(generated):
    _, answers, dest = generated
    settings = yaml.safe_load((dest / "conf" / "site.yaml").read_text())
    assert settings["palette"] == answers["site_palette"]
    assert settings["accent"] == answers["site_accent"]
    assert settings["theme"] == answers["site_theme"]
    assert (dest / ".claude" / "skills" / "site-design" / "SKILL.md").exists()


def test_deep_research_parts(generated):
    _, answers, dest = generated
    on = answers["deep_research"]
    slug = answers["mech_slug"]
    for path in [dest / "research" / "templates" / "record.md", dest / "src" / slug / "research.py",
                 dest / ".claude" / "skills" / "deep-research" / "SKILL.md"]:
        assert path.exists() == on, path
    assert ("research-providers:" in (dest / "justfile").read_text()) == on
    if on:
        prompt = (dest / "research" / "templates" / "record.md").read_text()
        assert "{name}" in prompt and "{{" not in prompt


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("just") is None or shutil.which("uv") is None, reason="needs just and uv")
def test_mock_research_run(tmp_path):
    """A generated Mech runs deep-research-client end to end with the free mock provider."""
    dest = render(tmp_path / "research", {**SCENARIOS["habitat"], "deep_research": True})
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    subprocess.run(["just", "install"], cwd=dest, check=True, env=env, capture_output=True)
    subprocess.run(["just", "new-record", "--id", "ENVO:00000051", "--name", "Hot spring",
                    "--term-label", "hot spring", "--apply"],
                   cwd=dest, check=True, env=env, capture_output=True)
    run = subprocess.run(["just", "research", "mock", "hot_spring"], cwd=dest, capture_output=True, text=True,
                         env={**env, "ENABLE_MOCK_PROVIDER": "true"})
    # 3 means the report was written and a check could not finish (e.g. OLS down).
    assert run.returncode in (0, 3), run.stdout + run.stderr
    report = (dest / "research" / "hot_spring-deep-research-mock.md").read_text()
    assert "provider: mock" in report
    assert "Name: Hot spring" in report
    again = subprocess.run(["just", "research", "mock", "hot_spring"], cwd=dest, capture_output=True,
                           text=True, env={**env, "ENABLE_MOCK_PROVIDER": "true"})
    assert again.returncode == 1 and "--force" in again.stdout


def test_uv_lock_is_not_ignored(generated):
    """The Mech standard requires uv.lock to be committed."""
    _, _, dest = generated
    if not (dest / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    ignored = subprocess.run(["git", "check-ignore", "-q", "uv.lock"], cwd=dest).returncode == 0
    assert not ignored
    lock = subprocess.run(["git", "check-ignore", "-q", "cache/go/terms.csv.lock"], cwd=dest).returncode == 0
    assert lock


def test_identity_prefix_requires_root(tmp_path):
    data = {**BASE, "mech_name": "NoRootMech", "record_class": "Thing", "identity_prefix": "ENVO"}
    with pytest.raises(Exception):  # noqa: B017  copier raises its own validation errors
        render(tmp_path / "out", data)


def test_bad_slug_rejected(tmp_path):
    data = {**BASE, "mech_name": "BadMech", "mech_slug": "Bad-Slug", "record_class": "Thing"}
    with pytest.raises(Exception):  # noqa: B017
        render(tmp_path / "out", data)


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("just") is None or shutil.which("uv") is None, reason="needs just and uv")
@pytest.mark.parametrize("scenario", ["habitat", "minimal", "disease", "all-workflows", "extras"])
def test_generated_mech_passes_qc(tmp_path, scenario):
    dest = render(tmp_path / scenario, SCENARIOS[scenario])
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    subprocess.run(["just", "install"], cwd=dest, check=True, env=env)
    result = subprocess.run(["just", "qc"], cwd=dest, env=env, capture_output=True, text=True)
    print(result.stdout[-3000:], result.stderr[-3000:])
    assert result.returncode == 0


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("just") is None or shutil.which("uv") is None, reason="needs just and uv")
def test_local_ontology_file_checks_terms(tmp_path):
    """A record bound to a local OBO file: the enum, the label and the recipes all use the file."""
    data = {**BASE, "mech_name": "LocalMech", "record_class": "Specimen", "ontologies": [],
            "extra_ontologies": [TINY], "workflows": []}
    dest = render(tmp_path / "local", data)
    shutil.copy(ROOT / "tests" / "data" / "tiny.obo", dest / "ontologies" / "tiny.obo")
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    subprocess.run(["just", "install"], cwd=dest, check=True, env=env)

    def run(*args):
        return subprocess.run(["just", *args], cwd=dest, env=env, capture_output=True, text=True)

    assert run("validate-terms", "tests/data/example_record.yaml").returncode == 0
    probe = dest / "probe.yaml"
    probe.write_text(
        "id: localmech:probe\nname: probe\nstatus: DRAFT\ntiny_entities:\n"
        "  - preferred_term: outside\n    term:\n      id: TINY:0000009\n      label: unrelated thing\n")
    bad = run("validate-terms", "probe.yaml")
    assert bad.returncode != 0 and "TINY:0000009" in bad.stdout + bad.stderr
    assert run("term-under", "TINY:0000003", "TINY:0000001").returncode == 0
    assert run("term-under", "TINY:0000009", "TINY:0000001").returncode == 1
    assert "small widget" in run("search-term", "TINY", "l~widget").stdout


@pytest.mark.slow
@pytest.mark.skipif(not os.environ.get("BIOPORTAL_API_KEY"), reason="needs BIOPORTAL_API_KEY")
@pytest.mark.skipif(shutil.which("just") is None or shutil.which("uv") is None, reason="needs just and uv")
def test_bioportal_terms_checked(tmp_path):
    """SNOMED CT through BioPortal: the enum holds, and the key never prints."""
    data = {**BASE, "mech_name": "PortalMech", "record_class": "Patient", "ontologies": [],
            "workflows": [],
            "extra_ontologies": [{"prefix": "SNOMEDCT", "root": "SNOMEDCT:404684003",
                                  "root_label": "Clinical finding", "noun": "clinical finding",
                                  "adapter": "bioportal:SNOMEDCT",
                                  "uri": "http://purl.bioontology.org/ontology/SNOMEDCT/"}]}
    dest = render(tmp_path / "portal", data)
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    subprocess.run(["just", "install"], cwd=dest, check=True, env=env)
    probe = dest / "probe.yaml"
    probe.write_text(
        "id: portalmech:probe\nname: probe\nstatus: DRAFT\nclinical_findings:\n"
        "  - preferred_term: heart attack\n    term:\n      id: SNOMEDCT:22298006\n"
        "      label: Myocardial infarction\n")
    good = subprocess.run(["just", "validate-terms", "probe.yaml"], cwd=dest, env=env,
                          capture_output=True, text=True)
    out = good.stdout + good.stderr
    assert env["BIOPORTAL_API_KEY"] not in out
    if "could not reach" in out:
        pytest.skip("BioPortal did not answer")
    assert good.returncode == 0, out[-2000:]
    text = probe.read_text().replace("22298006", "71388002")
    probe.write_text(text.replace("Myocardial infarction", "Procedure"))
    bad = subprocess.run(["just", "validate-terms", "probe.yaml"], cwd=dest, env=env,
                         capture_output=True, text=True)
    assert env["BIOPORTAL_API_KEY"] not in bad.stdout + bad.stderr
    if "could not reach" not in bad.stdout + bad.stderr:
        assert bad.returncode != 0 and "not in dynamic enum" in bad.stdout + bad.stderr


# Set these to run the load test against real servers, e.g. from Docker:
#   MECHMAKER_TEST_MONGODB=mongodb://localhost:27017/mechtest
#   MECHMAKER_TEST_NEO4J=neo4j://neo4j:password@localhost:7687/neo4j   (its data is deleted)
LOAD_SERVERS = {"mongodb": os.environ.get("MECHMAKER_TEST_MONGODB"),
                "neo4j": os.environ.get("MECHMAKER_TEST_NEO4J")}


@pytest.mark.slow
@pytest.mark.skipif(not any(LOAD_SERVERS.values()), reason="no MECHMAKER_TEST_MONGODB or _NEO4J")
@pytest.mark.skipif(shutil.which("just") is None or shutil.which("uv") is None, reason="needs just and uv")
def test_load_into_real_servers(tmp_path):
    targets = [t for t, h in LOAD_SERVERS.items() if h]
    data = {**BASE, "mech_name": "LoadMech", "record_class": "Specimen", "load_targets": targets,
            "workflows": []}
    dest = render(tmp_path / "load", data)
    config = {"targets": {t: LOAD_SERVERS[t] for t in targets}}
    (dest / "conf" / "load.yaml").write_text(yaml.safe_dump(config))
    records = dest / "data" / "specimens"
    records.mkdir(parents=True, exist_ok=True)
    shutil.copy(dest / "tests" / "data" / "example_record.yaml", records / "example_specimen.yaml")
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    subprocess.run(["just", "install"], cwd=dest, check=True, env=env)
    for t in targets:
        cmd = ["just", "load", t, "--replace"]
        result = subprocess.run(cmd, cwd=dest, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "1 document(s)" in result.stdout if t == "mongodb" else "node(s)" in result.stdout


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("just") is None or shutil.which("uv") is None, reason="needs just and uv")
def test_import_a_json_schema(tmp_path):
    """--from json-schema, through schema-automator: the record class gains the source's fields and enum."""
    data = {**BASE, "mech_name": "PantryMech", "record_class": "Item", "ontologies": [], "workflows": []}
    dest = render(tmp_path / "pantry", data)
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    subprocess.run(["just", "install"], cwd=dest, check=True, env=env)
    source = ROOT / "tests" / "data" / "ingredient.schema.json"
    cmd = ["just", "import-schema", str(source), "--from", "json-schema", "--record-class", "Ingredient",
           "--apply"]
    result = subprocess.run(cmd, cwd=dest, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    schema = yaml.safe_load((dest / "src" / "pantrymech" / "schema" / "pantrymech.yaml").read_text())
    assert {"cas_number", "form", "source"} <= set(schema["classes"]["Item"]["slots"])
    assert "class_uri" not in schema["classes"]["Item"]  # a converted schema's namespace is not kept
    records = dest / "data" / "items"
    records.mkdir(parents=True, exist_ok=True)
    (records / "salt.yaml").write_text(
        "id: pantrymech:salt\nname: salt\nstatus: DRAFT\nform: powder\nsource:\n  supplier: Acme\n"
        "creation_date: '2026-01-01'\ncuration_history:\n  - timestamp: '2026-01-01T00:00:00Z'\n"
        "    curator: t\n    llm_assisted: false\n    action: CREATE\n    description: Test.\n")
    ok = subprocess.run(["just", "validate-schema", "data/items/salt.yaml"], cwd=dest, env=env,
                        capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    (records / "salt.yaml").write_text((records / "salt.yaml").read_text().replace("powder", "plasma"))
    bad = subprocess.run(["just", "validate-schema", "data/items/salt.yaml"], cwd=dest, env=env,
                         capture_output=True, text=True)
    assert bad.returncode != 0 and "plasma" in bad.stdout + bad.stderr
