"""Commands read and write the checkout they run in, not the one the package came from.

Git worktrees share the primary checkout's virtualenv, whose editable install
points at the primary checkout. A path built from ``__file__`` would send a
worktree's reads and writes there, so ``repo_root()`` resolves from the
working directory.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from datmech.paths import PACKAGE_DIR, ROOT_ENV_VAR

SRC_DIR = PACKAGE_DIR


def root_seen_from(cwd: Path, **env: str) -> Path:
    code = (
        "from datmech.paths import REPO_ROOT, RECORDS_DIR\n"
        "print(REPO_ROOT)\n"
        "print(RECORDS_DIR)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=cwd, capture_output=True, text=True, check=True,
        env={k: v for k, v in env.items() if v is not None},
    )
    root, records = out.stdout.split()
    assert Path(records) == Path(root) / "data/zip_areas"
    return Path(root)


@pytest.fixture
def base_env():
    env = {k: v for k, v in os.environ.items() if k != ROOT_ENV_VAR}
    env["PYTHONPATH"] = str(PACKAGE_DIR.parent)
    return env


def make_tree(root: Path) -> Path:
    (root / "data/zip_areas").mkdir(parents=True)
    (root / "justfile").write_text("")
    return root.resolve()


def test_another_checkout_resolves_to_itself(tmp_path, base_env):
    tree = make_tree(tmp_path / "worktree")
    assert root_seen_from(tree, **base_env) == tree
    assert root_seen_from(tree / "data/zip_areas", **base_env) == tree


def test_the_env_var_wins(tmp_path, base_env):
    tree = make_tree(tmp_path / "chosen")
    other = make_tree(tmp_path / "other")
    assert root_seen_from(other, **base_env, **{ROOT_ENV_VAR: str(tree)}) == tree


def test_outside_any_checkout_falls_back_to_the_package_tree(tmp_path, base_env):
    assert root_seen_from(tmp_path, **base_env) == PACKAGE_DIR.parents[1]


def test_no_checkout_paths_from_file():
    """Only paths.py may climb out of the package from ``__file__``."""
    offenders = [
        f"{p.name}:{n}"
        for p in sorted(SRC_DIR.rglob("*.py"))
        if p.name != "paths.py"
        for n, line in enumerate(p.read_text().splitlines(), 1)
        if "__file__" in line and re.search(r"\.parents\[|\.parent\.parent", line)
    ]
    assert not offenders, f"build repository paths from REPO_ROOT, not __file__: {offenders}"
