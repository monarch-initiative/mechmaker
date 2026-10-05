"""The literature-scan publisher: the code with no model that files the leads the agent returns."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parents[1] / "template" / ".github" / "scripts"
          / "{% if 'literature-scan' in workflows %}literature-publish.js{% endif %}")

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")

# A fake GitHub: `open` lists paper ids an open issue already has, and every
# issue created is recorded.
HARNESS = r"""
const { publish } = require(process.argv[1]);
const c = JSON.parse(process.argv[2]);
const created = [];
const github = { rest: {
  search: { issuesAndPullRequests: async ({ q }) =>
    ({ data: { total_count: (c.open ?? []).some(id => q.includes(`"${id}"`)) ? 1 : 0 } }) },
  issues: { create: async args => { created.push(args); return { data: { number: 100 + created.length } }; } },
} };
publish(github, { owner: 'o', repo: 'r' }, c.result, c.packet, { max: c.max ?? 5, log: () => {}, warn: () => {} })
  .then(result => console.log(JSON.stringify({ result, created })));
"""


def paper(pid="PMID:1", preprint=False, record="data/a.yaml", **kw):
    return {"id": pid, "title": "Goats and hay", "date": "2026-09-01", "venue": "J Goats", "doi": "10.1/x",
            "link": "https://europepmc.org/article/MED/1", "preprint": preprint,
            "matches": [{"record": record}] if record else [], "abstract": "Goats eat hay.", **kw}


def run(leads, papers=None, **case):
    case = {"result": {"leads": leads}, "packet": {"papers": papers or [paper()]}, **case}
    out = subprocess.run(["node", "-e", HARNESS, str(SCRIPT), json.dumps(case)],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def lead(pid="PMID:1", record="data/a.yaml", **kw):
    return {"paper": pid, "record": record, "name": "Alpine goat", "assessment": "Adds diet.", **kw}


def test_a_lead_on_a_record_is_filed_with_packet_facts():
    got = run([lead()])
    issue = got["created"][0]
    assert issue["labels"] == ["curation", "low_effort", "literature"]
    assert issue["title"] == "[lit-scan] Alpine goat: Goats and hay"
    assert "Goats eat hay." in issue["body"] and "10.1/x" in issue["body"]
    assert "Augment only the existing record." in issue["body"]


def test_a_new_thing_is_high_effort_and_a_preprint_says_so():
    got = run([lead(record="")], papers=[paper(preprint=True, record=None)])
    issue = got["created"][0]
    assert issue["labels"] == ["curation", "high_effort", "literature", "preprint"]
    assert issue["title"].startswith("[lit-scan:new] Alpine goat")
    assert "not been peer reviewed" in issue["body"]


def test_papers_outside_the_packet_and_unmatched_records_are_refused():
    got = run([lead(pid="PMID:999"), lead(record="data/other.yaml")])
    assert got["created"] == []


def test_a_paper_with_an_open_issue_is_skipped():
    assert run([lead()], open=["PMID:1"])["created"] == []


def test_the_limit_and_duplicates_hold():
    papers = [paper(f"PMID:{i}") for i in range(1, 5)]
    got = run([lead("PMID:1"), lead("PMID:1"), lead("PMID:2"), lead("PMID:3")], papers=papers, max=2)
    assert [i["body"].split("**")[1] for i in got["created"]] == ["PMID:1", "PMID:2"]


def test_mentions_in_agent_or_abstract_text_are_defused():
    got = run([lead(assessment="ping @claude please", name="@someone")],
              papers=[paper(abstract="cc @maintainer")])
    issue = got["created"][0]
    assert "@claude" not in issue["body"] and "@maintainer" not in issue["body"]
    assert "@someone" not in issue["title"]
