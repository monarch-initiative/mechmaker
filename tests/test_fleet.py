"""Fleets: the Coordinator template, and Mechs made as members of a Fleet."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import copier
import pytest
import yaml
from test_template import BASE, FLEET_LINKS, SCENARIOS, render

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / "template" / "src" / "{{mech_slug}}" / "schema"
COORDINATOR = {**BASE, "kind": "coordinator", "fleet_name": "TestFleet"}
GIT_ENV = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.org",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.org"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cwd: Path, *args: str, **kw) -> subprocess.CompletedProcess:
    env = {**{k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}, **GIT_ENV}
    return subprocess.run(list(args), cwd=cwd, env=env, capture_output=True, text=True, **kw)


def commit(cwd: Path, message: str = "change") -> None:
    run(cwd, "git", "add", "-A", check=True)
    run(cwd, "git", "commit", "-q", "-m", message, check=True)


@pytest.fixture(scope="module")
def coordinator(tmp_path_factory) -> Path:
    return render(tmp_path_factory.mktemp("coordinator"), COORDINATOR)


@pytest.fixture(scope="module")
def member(tmp_path_factory) -> Path:
    return render(tmp_path_factory.mktemp("member"), SCENARIOS["fleet-member"])


def coordinator_module(dest: Path, name: str):
    """Import one module of a rendered Coordinator's package (those that need only PyYAML)."""
    src = str(dest / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import importlib

    return importlib.import_module(f"testfleet_coordinator.{name}")


# ---------------------------------------------------------------- the Coordinator


def test_coordinator_answers_hold_no_mech_questions(coordinator):
    answers = yaml.safe_load((coordinator / ".copier-answers.yml").read_text())
    assert answers["kind"] == "coordinator"
    assert answers["repo_name"] == "testfleet-coordinator"
    assert not {"mech_name", "record_class", "ontologies", "workflows", "fleet_links"} & set(answers)


def template_snapshot(dest: Path) -> Path:
    """The template as it is in the working tree, committed, for a test that runs `copier update`."""
    dest.mkdir(parents=True)
    for name in ("copier.yml", "template", "coordinator"):
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, dest / name, symlinks=True)
        else:
            shutil.copy2(src, dest / name)
    run(dest, "git", "init", "-q", "-b", "main", check=True)
    commit(dest, "snapshot")
    return dest


def test_an_update_of_a_mech_from_before_kind_does_not_ask_it(tmp_path):
    """Without --defaults, a question left to ask needs a terminal; there is none here, so asking fails."""
    template = template_snapshot(tmp_path / "template")
    dest = tmp_path / "m"
    copier.run_copy(str(template), str(dest), data=SCENARIOS["minimal"], defaults=True, quiet=True)
    answers_file = dest / ".copier-answers.yml"
    answers = yaml.safe_load(answers_file.read_text())
    del answers["kind"]
    answers_file.write_text(yaml.safe_dump(answers, sort_keys=False))
    run(dest, "git", "init", "-q", "-b", "main", check=True)
    commit(dest, "a Mech made before kind")
    copier.run_update(str(dest), skip_answered=True, quiet=True, overwrite=True)
    assert (dest / "src" / "minimalmech").is_dir()
    assert not (dest / "fleet.yaml").exists()


@pytest.mark.skipif(not shutil.which("just"), reason="just is not installed")
@pytest.mark.parametrize("recipe,expected", [
    (["sync", "alphamech", "../alpha", "--apply", "--ref", "abc"],
     "run fleet sync alphamech --root ../alpha --apply --ref abc"),
    (["sync", "alphamech", "../alpha"], "run fleet sync alphamech --root ../alpha"),
    (["audit", "--root", "alphamech=../alpha"], "run fleet audit --root alphamech=../alpha"),
    (["answers", "alphamech"], "run fleet answers alphamech"),
])
def test_coordinator_recipes_pass_their_arguments(coordinator, tmp_path, recipe, expected):
    """Recipes run under `sh` (dash on Debian and on GitHub's runners); a stand-in uv prints what it gets."""
    (tmp_path / "uv").write_text('#!/bin/sh\necho "$@"\n')
    (tmp_path / "uv").chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}"}
    out = subprocess.run(["just", *recipe], cwd=coordinator, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == expected


def test_coordinator_files(coordinator):
    for rel in ["fleet.yaml", "canon/manifest.yaml", "canon/schema/mech_shared.yaml",
                "canon/schema/history.yaml",
                "src/testfleet_coordinator/schema/fleet_schema.yaml", "src/testfleet_coordinator/cli.py",
                "justfile", "mkdocs.yml", "CLAUDE.md", "AGENTS.md", "LICENSE", ".github/workflows/qc.yaml",
                ".github/workflows/fleet-audit.yaml", ".github/workflows/docs.yaml",
                ".claude/skills/onboard-mech/SKILL.md", ".claude/skills/add-relationship/SKILL.md",
                ".claude/skills/change-canon/SKILL.md"]:
        assert (coordinator / rel).is_file(), rel
    assert not (coordinator / "src" / "None").exists()
    assert not list(coordinator.rglob("*.jinja"))
    for f in coordinator.rglob("*"):
        if f.is_file() and f.suffix in {".yaml", ".yml", ".md", ".toml"}:
            text = f.read_text()
            assert "{%" not in text, f
            assert "{{" not in text.replace("${{", ""), f


def test_named_recipes_exist_in_the_coordinator(coordinator):
    """Every `just <recipe>` the Coordinator's instructions name is in its justfile."""
    recipes = set(re.findall(r"^([a-z][a-z0-9-]*)[^\n=]*:", (coordinator / "justfile").read_text(), re.M))
    texts = [coordinator / "CLAUDE.md", coordinator / "README.md", *(coordinator / ".claude").rglob("*.md"),
             *(coordinator / "docs").glob("*.md")]
    missing = set()
    for path in texts:
        for name in re.findall(r"(?:^|`)\s*(?:# )?just ([a-z][a-z0-9-]*)", path.read_text(), re.M):
            if name not in recipes:
                missing.add((str(path.relative_to(coordinator)), name))
    assert not missing, sorted(missing)


def test_coordinator_workflows_follow_answers(tmp_path):
    dest = render(tmp_path / "c", {**COORDINATOR, "coordinator_workflows": []})
    assert sorted(p.name for p in (dest / ".github" / "workflows").iterdir()) == ["qc.yaml"]


def test_coordinator_needs_a_fleet_name(tmp_path):
    with pytest.raises(Exception, match="Fleet's name"):
        render(tmp_path / "c", {**BASE, "kind": "coordinator"})


def test_the_canon_is_one_copy():
    """The Coordinator's canon links to the template's vendored modules; there is no second copy to drift."""
    for name in ("mech_shared.yaml", "history.yaml"):
        link = ROOT / "coordinator" / "canon" / "schema" / name
        assert link.is_symlink()
        assert link.resolve() == (CANON / name).resolve()


def test_every_recorded_hash_of_the_canon_matches(coordinator):
    """The canon's sha256 is written in two templates: the Coordinator's manifest and a member's pin."""
    want = {"mech_shared": sha256(CANON / "mech_shared.yaml"), "history": sha256(CANON / "history.yaml")}
    manifest = yaml.safe_load((ROOT / "coordinator" / "canon" / "manifest.yaml").read_text())
    assert {a["id"]: a["sha256"] for a in manifest["artifacts"]} == want
    pin = (ROOT / "template" / "{% if fleet_name %}fleet{% endif %}" / "pin.yaml.jinja").read_text()
    assert dict(re.findall(r"- id: (\w+)\n.*\n\s+sha256: (\w+)", pin)) == want
    for name in ("mech_shared.yaml", "history.yaml"):
        assert sha256(coordinator / "canon" / "schema" / name) == sha256(CANON / name)


def test_starter_fleet_is_empty_and_named(coordinator):
    data = yaml.safe_load((coordinator / "fleet.yaml").read_text())
    assert data["name"] == "TestFleet"
    assert data["coordinator"] == "example-org/testfleet-coordinator"
    assert data["members"] == {} and data["relationships"] == {}


@pytest.mark.skipif(shutil.which("actionlint") is None, reason="actionlint not installed")
def test_coordinator_actionlint(coordinator):
    run(coordinator, "git", "init", "-q")
    result = run(coordinator, "actionlint", "-no-color")
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------- a member


def test_member_has_a_pin_and_a_check(member):
    pin = yaml.safe_load((member / "fleet" / "pin.yaml").read_text())
    assert pin["coordinator"] == "example-org/testfleet-coordinator"
    assert pin["ref"] == ""
    assert [a["target"] for a in pin["artifacts"]] == [
        "src/alphafleetmembermech/schema/mech_shared.yaml", "src/alphafleetmembermech/schema/history.yaml"]
    assert (member / "src" / "alphafleetmembermech" / "fleet.py").exists()
    assert "check-fleet" in (member / "justfile").read_text()
    assert "## The Fleet" in (member / "CLAUDE.md").read_text()


def member_fleet_check(dest: Path, *args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(dest / "src")}
    return subprocess.run([sys.executable, "-m", "alphafleetmembermech.fleet", *args], cwd=dest, env=env,
                          capture_output=True, text=True)


def test_a_member_not_yet_synced_is_told_to_sync(tmp_path):
    """A Mech that joined with an older canon is told the step that fixes it, not 'undo your edit'."""
    dest = render(tmp_path / "m", SCENARIOS["fleet-member"])
    assert member_fleet_check(dest).returncode == 0
    shared = dest / "src" / "alphafleetmembermech" / "schema" / "mech_shared.yaml"
    shared.write_text(shared.read_text() + "# an older canon\n")
    out = member_fleet_check(dest)
    assert out.returncode == 1
    assert "has not been synced from its Coordinator" in out.stdout
    assert "Undo the local edit" not in out.stdout


def test_an_existing_mech_joins_with_the_documented_update(tmp_path):
    """onboard-mech step 3: a Mech on a Fleet-aware mechmaker takes its fleet answers with copier update."""
    template = template_snapshot(tmp_path / "template")
    data = SCENARIOS["fleet-member"]
    outside = {k: v for k, v in data.items() if not k.startswith("fleet_")}
    dest = tmp_path / "m"
    copier.run_copy(str(template), str(dest), data=outside, defaults=True, quiet=True)
    run(dest, "git", "init", "-q", "-b", "main", check=True)
    commit(dest, "a Mech outside any Fleet")
    fleet_answers = tmp_path / "fleet.yml"
    fleet_answers.write_text(yaml.safe_dump({k: v for k, v in data.items() if k.startswith("fleet_")}))
    run(dest, sys.executable, "-m", "copier", "update", "--vcs-ref=:current:", "--skip-answered",
        "--defaults", "--data-file", str(fleet_answers), check=True)
    schema = (dest / "src" / "alphafleetmembermech" / "schema" / "alphafleetmembermech.yaml").read_text()
    assert "is_a: CrossCorpusLink" in schema
    assert (dest / "fleet" / "pin.yaml").exists()
    assert member_fleet_check(dest).returncode == 0


def test_member_schema_has_a_link_class_per_relationship(member):
    schema = yaml.safe_load((member / "src" / "alphafleetmembermech" / "schema" / "alphafleetmembermech.yaml")
                            .read_text())
    record = schema["classes"]["Widget"]
    assert {"betas", "gamma_sources"} <= set(record["slots"])
    beta = schema["classes"]["BetaMechLink"]
    assert beta["is_a"] == "CrossCorpusLink"
    assert beta["slot_usage"]["corpus"]["equals_string"] == "BetaMech"
    assert beta["slot_usage"]["relation"]["range"] == "BetaMechLinkRelationEnum"
    assert beta["slot_usage"]["basis"]["range"] == "BetaMechLinkBasisEnum"
    assert beta["slot_usage"]["source_version"]["required"] is True
    assert "basis" not in schema["classes"]["GammaMechLink"]["slot_usage"]
    assert list(schema["enums"]["GammaMechLinkRelationEnum"]["permissible_values"]) == ["DERIVED_FROM"]
    assert schema["slots"]["gamma_sources"]["range"] == "GammaMechLink"
    assert schema["prefixes"]["betamech"] == "https://w3id.org/example-org/betamech/"
    assert schema["prefixes"]["gammamech"] == "https://w3id.org/example-org/gammamech/"


def test_a_mech_outside_a_fleet_has_none_of_it(tmp_path):
    dest = render(tmp_path / "m", SCENARIOS["minimal"])
    assert not (dest / "fleet").exists()
    assert not (dest / "src" / "minimalmech" / "fleet.py").exists()
    assert "check-fleet" not in (dest / "justfile").read_text()
    assert "CrossCorpusLink" not in (dest / "src" / "minimalmech" / "schema" / "minimalmech.yaml").read_text()


@pytest.mark.parametrize("links,message", [
    ({"slot": "betas"}, "needs slot, target, prefix and relations"),
    ({**FLEET_LINKS[0], "slot": "Betas"}, "snake_case"),
    ({**FLEET_LINKS[0], "slot": "evidence"}, "already a slot"),
    ({**FLEET_LINKS[0], "target": "betamech"}, "CamelCase"),
    ({**FLEET_LINKS[0], "prefix": "alphafleetmembermech"}, "another Mech's slug"),
    ({**FLEET_LINKS[0], "relations": {"part_of": "lower case"}}, "UPPER_SNAKE_CASE"),
    ({**FLEET_LINKS[0], "relations": ["PART_OF"]}, "map each NAME"),
    ({**FLEET_LINKS[0], "class": "Widget"}, "already in the schema"),
    ({**FLEET_LINKS[0], "slot": "target"}, "already a slot"),
    ({**FLEET_LINKS[0], "slot": "chemical_entities"}, "already an ontology's section"),
    ({**FLEET_LINKS[0], "class": "ChemicalEntityDescriptor"}, "already in the schema"),
    ({**FLEET_LINKS[0], "class": "SupportingReference"}, "already in the schema"),
    ({**FLEET_LINKS[0], "class": "beta-link"}, "CamelCase"),
])
def test_bad_fleet_links_rejected(tmp_path, links, message):
    with pytest.raises(Exception, match=message):
        render(tmp_path / "m", {**SCENARIOS["fleet-member"], "fleet_links": [links]})


def schema_names(dest: Path) -> dict[str, set[str]]:
    names: dict[str, set[str]] = {"slots": set(), "classes": set()}
    for f in (dest / "src").glob("*/schema/*.yaml"):
        schema = yaml.safe_load(f.read_text())
        names["slots"] |= set(schema.get("slots") or {})
        names["classes"] |= set(schema.get("classes") or {}) | set(schema.get("enums") or {})
    return names


def test_reserved_names_cover_every_name_a_mech_has(tmp_path):
    """fleet_reserved_names holds every slot, class and enum not made from the answers. A render with
    no ontologies, but causal graphs, a keyed record and every output, must hold no other."""
    data = {**SCENARIOS["disease"], "ontologies": [], "causal_graphs": True, "record_class": "Widget"}
    names = schema_names(render(tmp_path / "m", data))
    reserved = yaml.safe_load((ROOT / "copier.yml").read_text())["fleet_reserved_names"]["default"]
    assert names["slots"] - set(reserved["slots"]) == set()
    assert names["classes"] - set(reserved["classes"]) == {"Widget"}


def test_the_coordinator_reserves_the_same_names(coordinator):
    reserved = yaml.safe_load((ROOT / "copier.yml").read_text())["fleet_reserved_names"]["default"]
    manifest = coordinator_module(coordinator, "manifest")
    assert set(reserved["slots"]) == manifest.RESERVED_SLOTS
    assert set(reserved["classes"]) == manifest.RESERVED_CLASSES


@pytest.mark.parametrize("second,message", [
    ({**FLEET_LINKS[1], "slot": "betas"}, "Two links use the slot"),
    ({**FLEET_LINKS[0], "slot": "more_betas"}, "Two links make the class"),
])
def test_clashing_fleet_links_rejected(tmp_path, second, message):
    with pytest.raises(Exception, match=message):
        render(tmp_path / "m", {**SCENARIOS["fleet-member"], "fleet_links": [FLEET_LINKS[0], second]})


def test_an_update_leaves_the_coordinators_files(tmp_path):
    """In a member, the canon and the pin belong to the Coordinator: a later render skips them."""
    dest = render(tmp_path / "m", SCENARIOS["fleet-member"])
    schema = dest / "src" / "alphafleetmembermech" / "schema"
    for path in (dest / "fleet" / "pin.yaml", schema / "mech_shared.yaml", schema / "history.yaml"):
        path.write_text(path.read_text() + "# from the Coordinator\n")
    copier.run_copy(str(ROOT), str(dest), data=SCENARIOS["fleet-member"], defaults=True, unsafe=True,
                    quiet=True, vcs_ref="HEAD", overwrite=True)
    for path in (dest / "fleet" / "pin.yaml", schema / "mech_shared.yaml", schema / "history.yaml"):
        assert path.read_text().endswith("# from the Coordinator\n"), path
    other = render(tmp_path / "o", SCENARIOS["minimal"])
    shared = other / "src" / "minimalmech" / "schema" / "mech_shared.yaml"
    shared.write_text("# edited\n")
    copier.run_copy(str(ROOT), str(other), data=SCENARIOS["minimal"], defaults=True, unsafe=True, quiet=True,
                    vcs_ref="HEAD", overwrite=True)
    assert shared.read_bytes() == (CANON / "mech_shared.yaml").read_bytes()


# ---------------------------------------------------------------- the two together


FLEET = {
    "id": "testfleet", "name": "TestFleet", "description": "Two members.",
    "coordinator": "example-org/testfleet-coordinator",
    "members": {
        "alphamech": {"name": "AlphaMech", "github": "example-org/alphamech", "status": "active",
                      "owns": "One alpha.", "record_class": "Alpha", "records_dir": "data/alphas"},
        "betamech": {"name": "BetaMech", "github": "example-org/betamech", "status": "active",
                     "owns": "One beta.", "record_class": "Beta", "records_dir": "data/betas",
                     "identity_prefix": "CHEBI"},
    },
    "relationships": {
        "alphamech-betas": {
            "subject": "alphamech", "object": "betamech", "slot": "betas",
            "description": "Betas an alpha is part of.",
            "relations": {"PART_OF": {"description": "The alpha is part of the beta."}},
            "bases": {"LITERATURE": {"description": "A cited source says so."}},
        },
    },
}
MEMBER_EXTRA = {**BASE, "ontologies": [], "include_site": False, "workflows": []}


def member_data(coordinator: Path, key: str) -> dict:
    manifest = coordinator_module(coordinator, "manifest")
    answers = coordinator_module(coordinator, "answers")
    fleet = manifest.build(FLEET)
    data = {**MEMBER_EXTRA, **answers.member_answers(fleet, fleet.members[key])}
    if data.get("identity_prefix"):
        data["identity_root"] = "CHEBI:24431"
    return data


def test_a_member_made_from_its_fleet_answers_agrees_with_fleet_yaml(coordinator, tmp_path):
    """What the Coordinator prints, mechmaker takes; the Coordinator then accepts the member's answers."""
    manifest = coordinator_module(coordinator, "manifest")
    answers = coordinator_module(coordinator, "answers")
    fleet = manifest.build(FLEET)
    assert manifest.rule_errors(fleet) == []
    for key in fleet.members:
        dest = render(tmp_path / key, member_data(coordinator, key))
        assert answers.disagreements(fleet, fleet.members[key], dest) == []
    schema = (tmp_path / "alphamech" / "src" / "alphamech" / "schema" / "alphamech.yaml").read_text()
    assert "BetaMechLink:" in schema and "betamech: https://w3id.org/example-org/betamech/" in schema


# ---------------------------------------------------------------- slow: installed and run


NEEDS_TOOLS = pytest.mark.skipif(shutil.which("just") is None or shutil.which("uv") is None,
                                 reason="needs just and uv")


@pytest.mark.slow
@NEEDS_TOOLS
def test_generated_coordinator_passes_qc(tmp_path):
    long_name = {**COORDINATOR, "fleet_name": "AVeryLongMicrobialCommunitiesFleet"}
    dest = render(tmp_path / "coordinator", long_name)
    run(dest, "git", "init", "-q", check=True)
    run(dest, "just", "install", check=True)
    result = run(dest, "just", "qc")
    print(result.stdout[-3000:], result.stderr[-3000:])
    assert result.returncode == 0


@pytest.mark.slow
@NEEDS_TOOLS
def test_a_fleet_end_to_end(tmp_path):
    """A Coordinator and two members: sync the canon, link a record, and audit."""
    coord = render(tmp_path / "coordinator", COORDINATOR)
    (coord / "fleet.yaml").write_text(yaml.safe_dump(FLEET, sort_keys=False))
    run(coord, "git", "init", "-q", "-b", "main", check=True)
    commit(coord, "the Fleet")
    run(tmp_path, "git", "init", "-q", "--bare", "coordinator.git", check=True)
    run(coord, "git", "remote", "add", "origin", str(tmp_path / "coordinator.git"), check=True)
    run(coord, "git", "push", "-q", "origin", "main", check=True)
    run(coord, "git", "fetch", "-q", "origin", check=True)
    run(coord, "just", "install", check=True)

    members = {}
    for key in FLEET["members"]:
        members[key] = render(tmp_path / key, member_data(coord, key))
        run(members[key], "git", "init", "-q", "-b", "main", check=True)
        commit(members[key], "made")
    roots = [arg for key, path in members.items() for arg in ("--root", f"{key}={path}")]

    before = run(coord, "uv", "run", "fleet", "audit", *roots)
    assert before.returncode == 1 and "is not a full commit" in before.stdout

    for key, path in members.items():
        run(coord, "uv", "run", "fleet", "sync", key, "--root", str(path), "--apply", check=True)
        commit(path, "pin")
    audit = run(coord, "uv", "run", "fleet", "audit", *roots)
    assert audit.returncode == 0, audit.stdout + audit.stderr

    beta = members["betamech"]
    (beta / "data" / "betas").mkdir(parents=True, exist_ok=True)
    (beta / "data" / "betas" / "water.yaml").write_text("id: CHEBI:15377\nname: water\n")
    commit(beta, "a record")
    version = run(beta, "git", "rev-parse", "HEAD", check=True).stdout.strip()
    alpha = members["alphamech"]
    link = {"corpus": "BetaMech", "relation": "PART_OF", "basis": "LITERATURE", "source_version": version}
    (alpha / "data" / "alphas").mkdir(parents=True, exist_ok=True)
    (alpha / "data" / "alphas" / "first.yaml").write_text(yaml.safe_dump({
        "id": "alphamech:0f8fad5b-d9cb-469f-a165-70867728950e", "name": "first",
        "betas": [{**link, "identifier": "CHEBI:15377"}, {**link, "identifier": "CHEBI:00000"}]}))
    commit(alpha, "links")
    audit = run(coord, "uv", "run", "fleet", "audit", *roots)
    assert audit.returncode == 1
    assert "CHEBI:00000: no such record in BetaMech" in audit.stdout
    assert "CHEBI:15377" not in audit.stdout


def test_sync_mech_follows_the_coordinator_folder_for_a_coordinator():
    sys.path.insert(0, str(ROOT / "skills" / "sync-mech" / "scripts"))
    import sync_mech

    paths = sync_mech.template_paths({"kind": "coordinator"})
    assert "coordinator" in paths and "template" not in paths
    for path in paths:
        assert (ROOT / path).exists(), path
    assert sync_mech.template_paths({"mech_slug": "x"}) == sync_mech.TEMPLATE_PATHS
