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


def converted(name: str, status: str) -> str:
    return yaml.safe_dump({"name": name, "status": status, "curation_history": [
        {"action": "CREATE", "description": f"Converted from Old KB, entry {name}."}]})


def test_converted_drafts_are_work_left_not_missing(mech):
    records = mech / "data" / "habitats"
    for stem in ("hot_spring", "soil"):
        (records / f"{stem}.yaml").write_text(converted(stem, "DRAFT"))
    (records / "gut.yaml").write_text(converted("gut", "PROPOSED"))
    _, items = audit(mech)
    seeds = items["Seed records marked PROPOSED until a person reviews them"]
    assert (seeds["status"], seeds["found"]) == ("done", "1 PROPOSED")
    found = items["Converted records curated to PROPOSED"]
    assert found["status"] == "check"
    assert found["found"] == "2 of 3 converted record(s) still DRAFT"
    assert "curate-record" in found["fix"]

    (records / "hot_spring.yaml").write_text(converted("hot_spring", "PROPOSED"))
    (records / "soil.yaml").write_text(converted("soil", "REVIEWED"))
    _, items = audit(mech)
    assert status(items, "Converted records curated to PROPOSED") == "done"


def test_a_draft_not_converted_is_still_missing(mech):
    records = mech / "data" / "habitats"
    (records / "hot_spring.yaml").write_text(converted("hot_spring", "DRAFT"))
    (records / "soil.yaml").write_text("name: soil\nstatus: DRAFT\n")
    (records / "gut.yaml").write_text(converted("gut", "unset-ish"))
    _, items = audit(mech)
    seeds = items["Seed records marked PROPOSED until a person reviews them"]
    assert seeds["status"] == "missing"
    assert seeds["found"] == "1 DRAFT, 1 unset-ish"
    assert status(items, "Converted records curated to PROPOSED") == "check"


def test_markdown_lists_what_is_missing(fresh):
    out = subprocess.run([sys.executable, str(SCRIPT), str(fresh)], capture_output=True, text=True)
    assert out.stdout.startswith("# Audit: SampleHabitatMech")
    assert "## Not implemented" in out.stdout
    assert "- [ ] **Domain model written in docs/DOMAIN.md**" in out.stdout


def test_not_a_mech(tmp_path):
    out = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path)], capture_output=True, text=True)
    assert out.returncode == 2


def test_todo_in_a_table_cell_is_not_filled_in(mech):
    domain = mech / "docs" / "DOMAIN.md"
    domain.write_text("# Domain\n\n| Section | Rule |\n|---|---|\n| `ph` | TODO |\n")
    _, items = audit(mech)
    assert status(items, "Domain model") == "missing"
    assert "1 TODO(s) left" in items["Domain model written in docs/DOMAIN.md"]["found"]
    domain.write_text("# Domain\n\n| Section | Rule |\n|---|---|\n| `ph` | one value per sample |\n")
    _, items = audit(mech)
    assert status(items, "Domain model") == "done"


def test_records_in_subfolders_count(mech):
    sub = mech / "data" / "habitats" / "aquatic"
    sub.mkdir(parents=True)
    for stem in ("hot_spring", "lake", "river"):
        (sub / f"{stem}.yaml").write_text(f"name: {stem}\nstatus: PROPOSED\n")
    _, items = audit(mech)
    assert status(items, "3 to 5 seed records") == "done"


def test_xmech_collection_is_x_mech_suite(mech):
    answers = mech / ".copier-answers.yml"
    answers.write_text(answers.read_text() + "collection: xmech\n")
    registry = mech / "registry" / "samplehabitatmech.md"
    _, items = audit(mech)
    assert status(items, "Joins the X-Mech suite") == "missing"
    entry = registry.read_text().replace("\ndomains:", "\ncollection:\n  - x-mech-suite\ndomains:", 1)
    registry.write_text(entry)
    _, items = audit(mech)
    assert status(items, "Joins the X-Mech suite") == "done"


@pytest.mark.parametrize("text, says", [
    ("- feature: Countries\n  check: countries\n", "`check` is 'countries'"),
    ("- feature: Seeds\n  check: {records: five}\n", "`records` takes a whole number"),
    ("- feature: A page\n  check: {contains: docs/x.md}\n", "`contains` takes"),
    ("- [a, list]\n", "request 1 is"),
    ("feature: Countries\ncheck: {slot: countries}\n", "no `requests:` key"),
    ("requests: {feature: x}\n", "must be a list"),
    ("- feature: [unclosed\n", "not valid YAML"),
])
def test_unreadable_requests_are_a_usage_error(tmp_path, text, says):
    requests = tmp_path / "requests.yml"
    requests.write_text(text)
    with pytest.raises(audit_mech.RequestsError) as exc:
        audit_mech.load_requests(requests)
    assert says in str(exc.value)


def test_unreadable_requests_exit_64_without_a_traceback(fresh, tmp_path):
    requests = tmp_path / "requests.yml"
    requests.write_text("- feature: Countries\n  check: countries\n")
    out = subprocess.run([sys.executable, str(SCRIPT), str(fresh), "--requests", str(requests)],
                         capture_output=True, text=True)
    assert out.returncode == 64
    assert "Traceback" not in out.stderr and "request 1" in out.stderr


def test_requests_under_a_key_and_strings_still_read(tmp_path):
    requests = tmp_path / "requests.yml"
    requests.write_text("requests:\n  - A plain ask\n  - feature: Seeds\n    check: {records: 3}\n")
    assert [r["feature"] for r in audit_mech.load_requests(requests)] == ["A plain ask", "Seeds"]
    requests.write_text("")
    assert audit_mech.load_requests(requests) == []
