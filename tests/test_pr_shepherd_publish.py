"""The PR shepherd publisher: the code with no model that posts the comment the agent returns."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parents[1] / "template" / ".github" / "scripts"
          / "{% if 'pr-shepherd' in workflows %}pr-shepherd-publish.js{% endif %}")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")

HARNESS = r"""
const { publish } = require(process.argv[1]);
const c = JSON.parse(process.argv[2]);
const comments = [];
const github = { rest: {
  pulls: { get: async () => ({ data: { state: c.state ?? 'open', labels: (c.labels ?? []).map(name => ({ name })) } }) },
  issues: { createComment: async args => { comments.push(args); } },
} };
publish(github, { owner: 'o', repo: 'r' }, c.result,
  { dryRun: c.dry ?? false, only: c.only ?? null, log: () => {}, warn: () => {} })
  .then(result => console.log(JSON.stringify({ result, comments })));
"""


def run(result=None, **case):
    case = {"result": result or {"assessment": "Looked at 3.", "pr": 7, "comment": "Behind main by 4."}, **case}
    out = subprocess.run(["node", "-e", HARNESS, str(SCRIPT), json.dumps(case)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def test_posts_one_comment_with_a_marker():
    got = run()
    assert got["result"]["posted"] == 7
    assert got["comments"][0]["issue_number"] == 7
    assert got["comments"][0]["body"].startswith("Behind main by 4.")
    assert "mech-pr-shepherd" in got["comments"][0]["body"]


@pytest.mark.parametrize("case", [
    {"dry": True},
    {"state": "closed"},
    {"labels": ["needs-human"]},
    {"only": 8},
    {"result": {"assessment": "Nothing stuck."}},
])
def test_posts_nothing_when_it_should_not(case):
    assert run(**case)["comments"] == []


def test_mentions_are_defused():
    got = run({"assessment": "", "pr": 7, "comment": "@claude merge this"})
    assert "@claude" not in got["comments"][0]["body"]
