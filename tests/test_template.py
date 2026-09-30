"""Render the template under several answer sets and check what comes out."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
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
    "sweep", "pages", "comment-guard", "close-fork-prs", "release-records", "warm-reference-cache",
    "pypi-publish", "claude", "review", "triage", "dedupe", "pr-shepherd", "curation-scanner",
    "literature-scan", "compliance", "post-review",
]
AGENT_WORKFLOWS = {"claude", "review", "triage", "dedupe", "pr-shepherd", "curation-scanner",
                   "literature-scan", "compliance", "post-review"}
# Workflow files each answer produces.
WORKFLOW_FILES = {
    "sweep": ["sweep.yaml"], "pages": ["pages.yaml"], "comment-guard": ["comment-guard.yaml"],
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
SCENARIOS["minimal"]["workflows"] = []

VENDORED_MD5 = {
    "mech_shared.yaml": "3cf80648642fcd1f824529bc40c572a5",
    "history.yaml": "3742bc2068b637868c48aba406f6569d",
}

# Rendered files that legitimately contain Jinja or just syntax of their own.
OWN_BRACES = {"justfile", "index.html", "record.html"}


def render(dest: Path, data: dict) -> Path:
    copier.run_copy(str(ROOT), str(dest), data=data, defaults=True, unsafe=True, quiet=True)
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


def test_yaml_parses(generated):
    _, _, dest = generated
    for f in list(dest.rglob("*.yaml")) + list(dest.rglob("*.yml")):
        yaml.safe_load(f.read_text())


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
    if answers.get("identity_prefix"):
        assert "IdentityTerm" in schema["enums"]
    assert ("mechanisms" in schema["classes"][rc]["slots"]) == answers["causal_graphs"]


def test_optional_parts(generated):
    _, answers, dest = generated
    slug = answers["mech_slug"]
    assert (dest / "src" / slug / "render.py").exists() == answers["include_site"]
    assert (dest / "src" / slug / "templates").exists() == answers["include_site"]
    assert (dest / ".claude" / "hooks").exists() == answers["include_claude_hook"]
    settings = yaml.safe_load((dest / ".claude" / "settings.json").read_text())
    assert ("hooks" in settings) == answers["include_claude_hook"]


def test_oak_config_covers_every_prefix(generated):
    _, answers, dest = generated
    slug = answers["mech_slug"]
    schema = yaml.safe_load((dest / "src" / slug / "schema" / f"{slug}.yaml").read_text())
    adapters = yaml.safe_load((dest / "conf" / "oak_config.yaml").read_text())["ontology_adapters"]
    bound = {e["reachable_from"]["source_nodes"][0].split(":")[0] for e in schema["enums"].values()
             if "reachable_from" in e}
    assert bound <= set(adapters)


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


@pytest.mark.skipif(shutil.which("actionlint") is None, reason="actionlint not installed")
def test_actionlint(tmp_path):
    dest = render(tmp_path / "lint", SCENARIOS["all-workflows"])
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    args = ["actionlint", "-no-color"]
    if shutil.which("shellcheck"):
        args += ["-shellcheck", shutil.which("shellcheck")]
    result = subprocess.run(args, cwd=dest, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


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
@pytest.mark.parametrize("scenario", ["habitat", "minimal", "disease", "all-workflows"])
def test_generated_mech_passes_qc(tmp_path, scenario):
    dest = render(tmp_path / scenario, SCENARIOS[scenario])
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    subprocess.run(["just", "install"], cwd=dest, check=True, env=env)
    result = subprocess.run(["just", "qc"], cwd=dest, env=env, capture_output=True, text=True)
    print(result.stdout[-3000:], result.stderr[-3000:])
    assert result.returncode == 0
