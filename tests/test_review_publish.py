"""The review publisher: the code with no model that posts what the review agent returns."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parents[1] / "template" / ".github" / "scripts"
          / "{% if 'review' in workflows %}review-publish.js{% endif %}")
SHA = "a" * 40

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")

# A fake GitHub: the PR's state comes from the case, and every createReview
# call is recorded. `refuse` lists events GitHub rejects; `bad_lines` rejects
# any review with inline comments, as GitHub does for a line outside the diff.
HARNESS = r"""
// With node -e, argv[1] is the first argument: there is no script path.
const { publish } = require(process.argv[1]);
const c = JSON.parse(process.argv[2]);
const calls = [];
const fail = msg => { const e = new Error(msg); e.status = 422; throw e; };
const github = {
  paginate: async (fn, args) => (await fn(args)).data,
  rest: { pulls: {
    get: async () => ({ data: { state: c.state ?? 'open', head: { sha: c.head ?? c.sha,
      repo: { full_name: c.fork ? 'someone/fork' : 'o/r' } } } }),
    listFiles: async () => ({ data: (c.files ?? []).map(filename => ({ filename })) }),
    createReview: async args => {
      calls.push({ event: args.event, comments: args.comments.length, body: args.body });
      if ((c.refuse ?? []).includes(args.event)) fail(`Can not ${args.event}`);
      if (c.bad_lines && args.comments.length) fail('Line could not be resolved');
    },
  } },
};
publish(github, { owner: 'o', repo: 'r' }, c.review, { pr: 7, sha: c.sha, log: () => {}, warn: () => {} })
  .then(result => console.log(JSON.stringify({ result, calls })));
"""


def run(**case):
    case = {"sha": SHA, **case}
    out = subprocess.run(["node", "-e", HARNESS, str(SCRIPT), json.dumps(case)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def review(verdict="approve", findings=(), **checks):
    checklist = {k: checks.get(k, True) for k in ("qc", "quotes", "terms", "scope", "history")}
    return {"verdict": verdict, "checklist": checklist, "summary": "Adds one record.",
            "findings": list(findings)}


def test_clean_review_approves_with_the_checklist():
    got = run(review=review())
    assert got["result"]["posted"] == "APPROVE"
    body = got["calls"][0]["body"]
    assert "- [x] `just qc` would pass" in body and "Adds one record." in body


def test_a_warning_requests_changes_whatever_the_verdict():
    got = run(review=review("approve", [{"severity": "warning", "body": "Quote is off."}]))
    assert got["result"]["posted"] == "REQUEST_CHANGES"
    assert "**warning**: Quote is off." in got["calls"][0]["body"]


def test_findings_on_changed_lines_go_inline():
    f = {"severity": "error", "path": "data/x.yaml", "line": 4, "body": "Wrong term."}
    got = run(review=review("request_changes", [f]), files=["data/x.yaml"])
    assert got["calls"][0]["comments"] == 1
    assert "Wrong term." not in got["calls"][0]["body"]


def test_a_rejected_inline_comment_moves_into_the_body():
    f = {"severity": "error", "path": "data/x.yaml", "line": 999, "body": "Wrong term."}
    got = run(review=review("request_changes", [f]), files=["data/x.yaml"], bad_lines=True)
    assert [c["comments"] for c in got["calls"]] == [1, 0]
    assert got["result"]["posted"] == "REQUEST_CHANGES" and "Wrong term." in got["calls"][1]["body"]


def test_a_refused_approval_posts_as_a_comment_and_says_why():
    got = run(review=review(), refuse=["APPROVE"])
    assert got["result"]["posted"] == "COMMENT"
    assert "GitHub refused APPROVE" in got["calls"][-1]["body"]


@pytest.mark.parametrize("case", [
    {"head": "b" * 40},  # new commits since the review
    {"fork": True},
    {"state": "closed"},
    {"sha": "not-a-sha"},
])
def test_nothing_is_posted_when_the_pr_is_not_what_was_reviewed(case):
    got = run(review=review(), **case)
    assert got["result"]["posted"] is None and got["calls"] == []


def test_mentions_are_defused():
    got = run(review={**review(), "summary": "cc @someone"})
    assert "@someone" not in got["calls"][0]["body"]
