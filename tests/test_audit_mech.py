"""audit_mech.py, run on a freshly rendered Mech and on the same Mech changed."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "audit-mech" / "scripts" / "audit_mech.py"
sys.path.insert(0, str(SCRIPT.parent))

import audit_mech  # noqa: E402
from test_template import SCENARIOS, render  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.org", *args],
                   cwd=cwd, check=True, capture_output=True)


@pytest.fixture(scope="module")
def fresh(tmp_path_factory) -> Path:
    """The habitat Mech, untouched, committed as make-mech says."""
    dest = render(tmp_path_factory.mktemp("audit") / "habitatmech", SCENARIOS["habitat"])
    git(dest, "init", "-q", "-b", "main")
    git(dest, "add", "-A")
    git(dest, "commit", "-q", "-m", "Copier output")
    return dest


@pytest.fixture
def mech(fresh, tmp_path) -> Path:
    dest = tmp_path / "habitatmech"
    shutil.copytree(fresh, dest, symlinks=True)
    return dest


def audit(mech: Path, *args: str) -> tuple[int, dict[str, dict]]:
    out = subprocess.run([sys.executable, str(SCRIPT), str(mech), "--json", *args],
                         capture_output=True, text=True)
    items = json.loads(out.stdout)["items"] if out.stdout else []
    return out.returncode, {i["feature"]: i for i in items}


def status(items: dict[str, dict], start: str) -> str:
    hits = [i["status"] for f, i in items.items() if f.startswith(start)]
    assert len(hits) == 1, f"{start!r} matched {len(hits)} items"
    return hits[0]


def test_catalog_matches_copier():
    catalog = yaml.safe_load(yaml.safe_load((ROOT / "copier.yml").read_text())["ontology_catalog"]["default"])
    want = {k: (o["prefix"], o["slot"], o["enum"], o["root"], o["adapter"]) for k, o in catalog.items()}
    assert want == audit_mech.CATALOG


def test_fresh_copy_has_every_answer_and_none_of_the_curation(fresh):
    code, items = audit(fresh)
    assert code == 1
    answered = [i for i in items.values() if not i["asked"].startswith("make-mech")]
    assert answered and all(i["status"] == "done" for i in answered), \
        [i for i in answered if i["status"] != "done"]
    # The scaffold is not a design, and an empty Mech has no seeds.
    assert status(items, "Domain model") == "missing"
    assert status(items, "Schema shaped") == "missing"
    assert status(items, "3 to 5 seed records") == "missing"
    assert status(items, "Git history") == "done"


def test_cut_section_and_removed_workflow_are_missing(mech):
    schema = mech / "src" / "samplehabitatmech" / "schema" / "samplehabitatmech.yaml"
    data = yaml.safe_load(schema.read_text())
    data["classes"]["Habitat"]["slots"].remove("chemical_entities")
    del data["slots"]["chemical_entities"]
    del data["enums"]["ChemicalEntityTerm"]
    schema.write_text(yaml.safe_dump(data, sort_keys=False))
    (mech / ".github" / "workflows" / "sweep.yaml").unlink()
    _, items = audit(mech)
    assert status(items, "CHEBI terms") == "missing"
    assert status(items, "Workflow `sweep`") == "missing"
    assert status(items, "Schema shaped") == "done"


def test_renamed_section_still_counts(mech):
    schema = mech / "src" / "samplehabitatmech" / "schema" / "samplehabitatmech.yaml"
    text = schema.read_text().replace("chemical_entities", "nutrients")
    schema.write_text(text)
    _, items = audit(mech)
    assert status(items, "CHEBI terms") == "done"


def test_requests_are_checked_or_left_to_judge(mech, tmp_path):
    for stem in ("hot_spring", "soil", "gut"):
        (mech / "data" / "habitats" / f"{stem}.yaml").write_text(f"name: {stem}\nstatus: PROPOSED\n")
    requests = tmp_path / "requests.yml"
    requests.write_text(yaml.safe_dump([
        {"feature": "A habitat class", "check": {"class": "Habitat"}},
        {"feature": "A pH section", "said": "pH matters most", "check": {"slot": "ph_values"}},
        {"feature": "An export recipe", "check": {"recipe": "export"}},
        {"feature": "Ten records", "check": {"records": 10}},
        {"feature": "Records read well"},
    ]))
    code, items = audit(mech, "--requests", str(requests))
    assert code == 1
    assert status(items, "A habitat class") == "done"
    assert status(items, "A pH section") == "missing"
    assert items["A pH section"]["asked"] == 'requested: "pH matters most"'
    assert status(items, "An export recipe") == "done"
    assert status(items, "Ten records") == "missing"
    assert status(items, "Records read well") == "check"
    assert status(items, "3 to 5 seed records") == "done"
    assert status(items, "Seed records marked PROPOSED") == "done"


def test_markdown_lists_what_is_missing(fresh):
    out = subprocess.run([sys.executable, str(SCRIPT), str(fresh)], capture_output=True, text=True)
    assert out.stdout.startswith("# Audit: SampleHabitatMech")
    assert "## Not implemented" in out.stdout
    assert "- [ ] **Domain model written in docs/DOMAIN.md**" in out.stdout


def test_not_a_mech(tmp_path):
    out = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)], capture_output=True, text=True)
    assert out.returncode == 2
