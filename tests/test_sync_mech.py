"""sync_mech.py, on a Mech made from a small template history built here.

The history: 0.1.0, then pull request #7 (merged) changes report.py, then
#8 (squash-merged) adds a docs page, a justfile recipe and two upgrade
notes, then a README-only commit, then 0.2.0. The Mech is rendered at 0.1.0
and changes its own justfile.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import copier
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "sync-mech" / "scripts" / "sync_mech.py"
sys.path.insert(0, str(SCRIPT.parent))

import sync_mech  # noqa: E402
from test_template import SCENARIOS  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="needs git")

IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.org",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.org"}
ENV = {**os.environ, **IDENTITY}
REPORT = "template/src/{{mech_slug}}/report.py"
NOTES = [
    {"id": "new-page", "pr": 8, "summary": "A new page.", "action": "Read it."},
    {"id": "loose", "summary": "No pull request named.", "action": "Do the thing."},
    {"id": "old", "pr": 3, "summary": "Older than the Mech.", "action": "Never shown."},
    {"id": "site-only", "pr": 8, "when": "include_site", "summary": "Needs a site.", "action": "-"},
]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
                          env=ENV).stdout.strip()


def sync(*args: str) -> tuple[int, str, str]:
    out = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True, env=ENV)
    return out.returncode, out.stdout, out.stderr


@pytest.fixture(scope="module")
def template(tmp_path_factory) -> Path:
    repo = tmp_path_factory.mktemp("mechmaker")
    shutil.copy(ROOT / "copier.yml", repo / "copier.yml")
    shutil.copytree(ROOT / "template", repo / "template", symlinks=True)
    (repo / "README.md").write_text("mechmaker\n")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "Initial")
    git(repo, "tag", "0.1.0")

    git(repo, "switch", "-qc", "report")
    with (repo / REPORT).open("a") as fh:
        fh.write("# Counted upstream.\n")
    git(repo, "commit", "-qam", "Count more")
    git(repo, "switch", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "report", "-m",
        "Merge pull request #7 from org/report\n\nCount more in the report")

    (repo / "template" / "docs" / "NEW.md").write_text("# New\n")
    with (repo / "template" / "justfile.jinja").open("a") as fh:
        fh.write("\n\n# Added upstream\nnew-thing:\n    echo hi\n")
    (repo / "upgrade-notes.yml").write_text(yaml.safe_dump(NOTES, sort_keys=False))
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "Add a new page (#8)")

    (repo / "README.md").write_text("mechmaker, again\n")
    git(repo, "commit", "-qam", "Touch only the README")
    git(repo, "tag", "0.2.0")
    return repo


@pytest.fixture(scope="module")
def made(template, tmp_path_factory) -> Path:
    """The minimal Mech at 0.1.0, with a change of its own to the justfile, committed."""
    dest = tmp_path_factory.mktemp("made") / "minimalmech"
    copier.run_copy(str(template), str(dest), data=SCENARIOS["minimal"], defaults=True, quiet=True,
                    vcs_ref="0.1.0")
    git(dest, "init", "-q", "-b", "main")
    git(dest, "add", "-A")
    git(dest, "commit", "-qm", "Copier output")
    justfile = dest / "justfile"
    justfile.write_text("# This Mech's own line.\n" + justfile.read_text())
    git(dest, "commit", "-qam", "Local change")
    return dest


@pytest.fixture
def mech(made, tmp_path) -> Path:
    dest = tmp_path / "minimalmech"
    shutil.copytree(made, dest, symlinks=True)
    return dest


@pytest.fixture(scope="module")
def plan(made) -> dict:
    code, out, err = sync("plan", str(made), "--json")
    assert code == 1, err
    return json.loads(out)


def test_check_lists_template_changes_only(made):
    code, out, _ = sync("check", str(made), "--json")
    assert code == 1
    data = json.loads(out)
    assert data["target"] == "0.2.0"
    assert [u["id"] for u in data["updates"]] == ["#7", "#8"]
    assert [u["title"] for u in data["updates"]] == ["Count more in the report", "Add a new page"]


def test_plan_ties_each_file_to_its_pull_request(plan):
    assert plan["target_commit"] == "0.2.0"
    assert [u["id"] for u in plan["updates"]] == ["#7", "#8"]
    files = {f["path"]: f for f in plan["files"]}
    assert files["src/minimalmech/report.py"] == {
        "path": "src/minimalmech/report.py", "status": "take", "area": "tools", "updates": ["#7"]}
    assert files["docs/NEW.md"]["status"] == "add"
    assert files["docs/NEW.md"]["area"] == "documentation"
    # The Mech changed its justfile, so the new recipe must be merged in.
    assert files["justfile"]["status"] == "merge"
    assert set(files) == {"src/minimalmech/report.py", "docs/NEW.md", "justfile"}
    assert plan["questions"] == {} and plan["dropped_questions"] == []


def test_plan_shows_the_notes_that_reach_this_mech(plan):
    notes = {n["id"]: n["update"] for n in plan["notes"]}
    # "old" names a pull request outside the range; "site-only" needs a site the Mech lacks.
    assert notes == {"new-page": "#8", "loose": "#8"}
    assert next(u for u in plan["updates"] if u["id"] == "#8")["notes"] == ["new-page", "loose"]


def test_plan_text_names_updates_files_and_notes(made):
    code, out, _ = sync("plan", str(made))
    assert code == 1
    assert "## #7  Count more in the report" in out
    assert "take    src/minimalmech/report.py  [tools]" in out
    assert "merge   justfile  [tools]" in out
    assert "- new-page (#8): A new page." in out


def test_apply_takes_only_the_accepted_update(mech):
    report = (mech / "src/minimalmech/report.py").read_text()
    code, out, err = sync("apply", str(mech), "--accept", "#8", "--json")
    assert code == 0, err
    result = json.loads(out)
    assert result["accepted"] == ["#8"] and result["declined"] == ["#7"]
    assert result["restored"] == ["src/minimalmech/report.py"]
    assert result["conflicts"] == [] and result["partial"] == {} and result["unplanned"] == []
    assert [n["id"] for n in result["notes"]] == ["new-page", "loose"]
    assert (mech / "src/minimalmech/report.py").read_text() == report
    assert (mech / "docs/NEW.md").is_file()
    justfile = (mech / "justfile").read_text()
    assert justfile.startswith("# This Mech's own line.\n") and "new-thing:" in justfile
    assert yaml.safe_load((mech / ".copier-answers.yml").read_text())["_commit"] == "0.2.0"
    # Up to date now: nothing is offered again, declined or not.
    git(mech, "add", "-A")
    git(mech, "commit", "-qm", "Sync")
    code, out, _ = sync("plan", str(mech))
    assert code == 0 and "up to date" in out


def test_apply_keep_leaves_a_path_alone(mech):
    justfile = (mech / "justfile").read_text()
    code, out, err = sync("apply", str(mech), "--all", "--keep", "justfile", "--json")
    assert code == 0, err
    assert "justfile" in json.loads(out)["restored"]
    assert (mech / "justfile").read_text() == justfile
    assert "Counted upstream" in (mech / "src/minimalmech/report.py").read_text()


def test_apply_refuses_a_dirty_mech(mech):
    (mech / "scratch.txt").write_text("unsaved\n")
    code, _, err = sync("apply", str(mech), "--all")
    assert code == 2 and "uncommitted changes" in err


def test_unknown_update_is_a_usage_error(mech):
    code, _, err = sync("apply", str(mech), "--accept", "#99")
    assert code == 64 and "no update named #99" in err


def test_a_folder_without_answers_is_not_a_mech(tmp_path):
    code, _, err = sync("check", str(tmp_path))
    assert code == 2 and ".copier-answers.yml" in err


def test_areas():
    assert sync_mech.area("src/m/schema/m.yaml", "m") == "data model"
    assert sync_mech.area("src/m/schema/mech_shared.yaml", "m") == "shared schema"
    assert sync_mech.area("src/m/templates/record.html", "m") == "site and browser"
    assert sync_mech.area(".github/workflows/review.yaml", "m") == "workflows"
    assert sync_mech.area("CLAUDE.md", "m") == "agent guidance"
    assert sync_mech.area("README.md", "m") == "documentation"
    assert sync_mech.area("pyproject.toml", "m") == "dependencies"


def test_source_urls():
    assert sync_mech.source_url("gh:monarch-initiative/mechmaker") == \
        "https://github.com/monarch-initiative/mechmaker.git"
    assert sync_mech.source_url("/home/me/mechmaker") is None


def test_upgrade_notes_are_well_formed():
    notes = yaml.safe_load((ROOT / "upgrade-notes.yml").read_text())
    ids = [n["id"] for n in notes]
    assert len(ids) == len(set(ids))
    questions = yaml.safe_load((ROOT / "copier.yml").read_text())
    for note in notes:
        assert set(note) <= {"id", "pr", "when", "summary", "action"}, note["id"]
        assert note["summary"].strip() and note["action"].strip(), note["id"]
        assert "pr" not in note or isinstance(note["pr"], int), note["id"]
        assert "when" not in note or note["when"] in questions, note["id"]
