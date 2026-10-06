"""The example Mechs stay in step with the template.

Each example's answers are rendered with this checkout's template. Every
file the render writes must be in the example byte for byte, except the
files the Mech owns (OWN in scripts/sync_examples.py). When this fails, run
`just sync-examples`, then the example's own `just qc`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import sync_examples  # noqa: E402
from sync_examples import ANSWERS, EXAMPLES, OWN, answers, compare  # noqa: E402


@pytest.fixture(scope="module", params=sorted(OWN))
def example(request, tmp_path_factory) -> tuple[str, Path]:
    name = request.param
    return name, sync_examples.render(name, tmp_path_factory.mktemp(name) / name)


def test_every_example_is_listed():
    assert sorted(OWN) == sorted(p.parent.name for p in EXAMPLES.glob(f"*/{ANSWERS}"))


def test_answers_are_complete(example):
    """A question added to the template since has its answer in the example."""
    name, fresh = example
    assert answers(EXAMPLES / name / ANSWERS) == answers(fresh / ANSWERS)


def test_template_files_match(example):
    name, fresh = example
    drifted, _ = compare(name, fresh)
    assert not drifted, f"example/{name} has drifted from the template; run `just sync-examples`: {drifted}"


def test_owned_files_are_still_template_files(example):
    """An entry for a file the template no longer writes is stale."""
    name, fresh = example
    stale = [rel for rel in OWN[name] if not (fresh / rel).is_file()]
    assert not stale, stale
