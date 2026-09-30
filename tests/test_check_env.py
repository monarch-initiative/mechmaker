"""check_env.py, run against fake tools on a controlled PATH."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "make-mech" / "scripts" / "check_env.py"

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="fake tools are shell scripts")


def fake(bin_dir: Path, name: str, output: str) -> None:
    path = bin_dir / name
    path.write_text(f"#!/bin/sh\n{output}\n")
    path.chmod(0o755)


def run(path_dirs: list[Path]) -> subprocess.CompletedProcess:
    env = {**os.environ, "PATH": os.pathsep.join(str(d) for d in path_dirs)}
    return subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, env=env)


@pytest.fixture
def tools(tmp_path: Path) -> Path:
    """Every required tool present, optional ones absent."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake(bin_dir, "git", 'echo "git version 2.43.0"')
    fake(bin_dir, "uv", 'echo "uv 0.11.29"')
    fake(bin_dir, "just", 'echo "just 1.42.4"')
    fake(bin_dir, "copier", 'echo "copier 9.10.1"')
    return bin_dir


def test_ready_without_optional_tools(tools):
    result = run([tools])
    assert result.returncode == 0, result.stdout
    assert "Ready." in result.stdout
    assert "not found (optional)" in result.stdout


def test_missing_required_tool_fails_with_fix(tools):
    (tools / "just").unlink()
    result = run([tools])
    assert result.returncode == 1
    assert re.search(r"^\s+just\s+MISSING\s", result.stdout, re.M)
    assert "uv tool install rust-just" in result.stdout


def test_tool_installed_but_not_on_path(tools, tmp_path):
    hidden = tmp_path / "uvbin"
    hidden.mkdir()
    (tools / "just").rename(hidden / "just")
    fake(tools, "uv", f'if [ "$1" = tool ]; then echo "{hidden}"; else echo "uv 0.11.29"; fi')
    result = run([tools])
    assert result.returncode == 1
    assert "MISSING from PATH" in result.stdout
    assert "uv tool update-shell" in result.stdout


def test_old_copier_fails(tools):
    fake(tools, "copier", 'echo "copier 9.1.0"')
    result = run([tools])
    assert result.returncode == 1
    assert "too old" in result.stdout
    assert "uv tool upgrade copier" in result.stdout


def test_copier_minimum_matches_the_template():
    import importlib.util

    import yaml

    spec = importlib.util.spec_from_file_location("check_env", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    declared = yaml.safe_load((SCRIPT.parents[3] / "copier.yml").read_text())["_min_copier_version"]
    assert tuple(int(p) for p in declared.split(".")) == mod.MIN_COPIER


def _load():
    import importlib.util

    spec = importlib.util.spec_from_file_location("check_env", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("down,required", [
    ("ebi.ac.uk", False),
    ("eutils.ncbi.nlm.nih.gov", False),
    ("github.com", True),
    ("pypi.org", True),
])
def test_only_github_and_pypi_are_required(monkeypatch, down, required):
    mod = _load()

    class Resp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        if down in req.full_url:
            raise OSError("unreachable")
        return Resp()

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    rows, problems, warnings = mod.check_services()
    assert bool(problems) == required
    assert bool(warnings) == (not required)
