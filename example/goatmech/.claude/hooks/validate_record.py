#!/usr/bin/env python3
"""PreToolUse hook: validate a record before an edit to it lands.

Intercepts Edit, MultiEdit and Write calls on data/goat_breeds/*.yaml,
builds the file as it would be after the edit, and runs closed-schema and
record-rule validation on it. Exit code 2 blocks the edit and shows the
errors to the agent.

Only the offline, deterministic checks block here. Terms and quotes need
the network and are checked by `just validate` and CI.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

RECORDS_DIR = "data/goat_breeds"
MODULE = "goatmech.validate"


def after_edit(tool: str, inp: dict, path: Path) -> str | None:
    if tool == "Write":
        return inp.get("content", "")
    text = path.read_text() if path.exists() else ""
    edits = inp.get("edits") if tool == "MultiEdit" else [inp]
    for e in edits or []:
        old, new = e.get("old_string", ""), e.get("new_string", "")
        if old not in text:
            return None  # the edit tool will reject it; nothing to check
        text = text.replace(old, new) if e.get("replace_all") else text.replace(old, new, 1)
    return text


def main() -> int:
    payload = json.load(sys.stdin)
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input", {})
    file_path = inp.get("file_path")
    if tool not in ("Edit", "MultiEdit", "Write") or not file_path:
        return 0
    path = Path(file_path).resolve()
    if path.suffix != ".yaml":
        return 0
    # The repository root is the ancestor that holds the records directory,
    # so the hook validates in the worktree being edited.
    root = next((p for p in path.parents if path.is_relative_to(p / RECORDS_DIR)), None)
    if root is None:
        return 0
    text = after_edit(tool, inp, path)
    if text is None:
        return 0
    with tempfile.TemporaryDirectory() as tmp:
        candidate = Path(tmp) / path.name
        candidate.write_text(text)
        result = subprocess.run(
            ["uv", "run", "--quiet", "python", "-m", MODULE, str(candidate)],
            cwd=root, capture_output=True, text=True,
        )
    if result.returncode == 0:
        return 0
    print(f"Blocked: {path.name} would not validate after this edit.", file=sys.stderr)
    print((result.stdout + result.stderr).replace(str(candidate), path.name), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
