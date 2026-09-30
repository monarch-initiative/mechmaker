#!/usr/bin/env python3
"""Check that this machine has what making and curating a Mech needs.

    python3 check_env.py              # tools
    python3 check_env.py --network    # tools, and the services a Mech uses

Standard library only, so it runs before anything else is installed. Without
a mechmaker checkout:

    curl -fsSLO \
https://raw.githubusercontent.com/monarch-initiative/mechmaker/main/skills/make-mech/scripts/check_env.py
    python3 check_env.py                      # or: uv run --no-project check_env.py

Exit 0 when every required tool is present (and, with --network, every
service answers); exit 1 otherwise. Each problem comes with the command that
fixes it on this operating system.
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request

# The oldest Copier the template accepts (copier.yml `_min_copier_version`).
MIN_COPIER = (9, 3, 0)

OS = platform.system()  # "Linux", "Darwin" or "Windows"


def uv_install() -> str:
    if OS == "Windows":
        return 'powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    return "curl -LsSf https://astral.sh/uv/install.sh | sh"


def git_install() -> str:
    if OS == "Darwin":
        return "xcode-select --install"
    if OS == "Windows":
        return "winget install --id Git.Git -e"
    return "install git with your package manager, e.g. sudo apt install git"


# name, command, required, why, how to install
TOOLS = [
    ("git", ["git", "--version"], True, "keeps the Mech's history", git_install),
    ("uv", ["uv", "--version"], True, "installs Python and the Mech's packages", uv_install),
    ("just", ["just", "--version"], True, "runs the Mech's commands", lambda: "uv tool install rust-just"),
    ("copier", ["copier", "--version"], True, "copies the template", lambda: "uv tool install copier"),
    ("claude", ["claude", "--version"], False, "the AI agent that curates",
     lambda: "see https://docs.claude.com/en/docs/claude-code/setup"),
    ("gh", ["gh", "--version"], False, "publishes to GitHub and opens pull requests",
     lambda: "see https://cli.github.com"),
]

SERVICES = [
    ("GitHub", "https://github.com", "the template, and publishing"),
    ("OLS (ontology lookups)", "https://www.ebi.ac.uk/ols4/api/ontologies/go", "term checks"),
    ("PubMed", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?retmode=json", "reference checks"),
    ("PyPI", "https://pypi.org/simple/", "installing packages"),
]


def version_of(cmd: list[str]) -> str | None:
    """The first version-like string the command prints, or None if it will not run."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"\d+\.\d+(?:\.\d+)?", out.stdout + out.stderr)
    return m.group(0) if m else "unknown version"


def as_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", version)[:3])


def uv_tool_bin() -> str | None:
    """Where `uv tool install` puts commands, if uv is here to say."""
    try:
        out = subprocess.run(["uv", "tool", "dir", "--bin"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() or None


def check_tools() -> tuple[list[tuple[str, str, str]], list[str]]:
    rows, problems = [], []
    tool_bin = None
    for name, cmd, required, why, how in TOOLS:
        path = shutil.which(cmd[0])
        version = version_of(cmd) if path else None
        if version is None:
            status = "MISSING" if required else "not found (optional)"
            fix = how()
            if name in ("just", "copier"):
                tool_bin = tool_bin or uv_tool_bin()
                exe = cmd[0] + (".exe" if OS == "Windows" else "")
                if tool_bin and os.path.exists(os.path.join(tool_bin, exe)):
                    status = "MISSING from PATH"
                    fix = (f"installed in {tool_bin}, which is not on your PATH: "
                           "run `uv tool update-shell` and open a new terminal")
            rows.append((name, status, why))
            if required:
                problems.append(f"{name}: {fix}")
            else:
                rows[-1] = (name, status, f"{why}; {fix}")
            continue
        status = version
        if name == "copier" and as_tuple(version) < MIN_COPIER:
            status = f"{version} (too old)"
            problems.append(f"copier: {version} is older than {'.'.join(map(str, MIN_COPIER))}; "
                            "run `uv tool upgrade copier`")
        rows.append((name, status, why))
    return rows, problems


def check_services() -> tuple[list[tuple[str, str, str]], list[str]]:
    rows, problems = [], []
    for name, url, why in SERVICES:
        req = urllib.request.Request(url, headers={"User-Agent": "mechmaker-check-env/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                status = f"ok ({resp.status})"
        except Exception as exc:  # any failure means the service did not answer
            status = "NO ANSWER"
            problems.append(f"{name} did not answer ({type(exc).__name__}); {why} will fail until it does. "
                            "This is often a passing outage: try again in a few minutes")
        rows.append((name, status, why))
    return rows, problems


def table(title: str, rows: list[tuple[str, str, str]]) -> str:
    w0 = max(len(r[0]) for r in rows)
    w1 = max(len(r[1]) for r in rows)
    lines = [title]
    lines += [f"  {a:<{w0}}  {b:<{w1}}  {c}" for a, b, c in rows]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--network", action="store_true", help="also check the services a Mech uses")
    args = parser.parse_args(argv)

    print(f"System: {OS} {platform.release()}, Python {platform.python_version()}\n")
    rows, problems = check_tools()
    print(table("Tools", rows))
    if args.network:
        srows, sproblems = check_services()
        print()
        print(table("Services", srows))
        problems += sproblems
    print()
    if problems:
        print("To fix:")
        for p in problems:
            print(f"  - {p}")
        needs_uv = any(p.startswith(("just:", "copier:")) and "PATH" not in p for p in problems)
        if needs_uv and shutil.which("uv") is None:
            print("  Install uv first; just and copier are installed with it.")
        return 1
    print("Ready." + ("" if args.network else " (Run with --network to check the services too.)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
