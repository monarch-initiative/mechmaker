"""Create or update the repository's labels from .github/labels.yaml.

    uv run --no-project --with pyyaml python .github/scripts/sync_labels.py [--dry-run]

Uses the `gh` CLI, so it acts as whoever `gh` is logged in as. Labels not in
the file are left alone.
"""

import subprocess
import sys
from pathlib import Path

import yaml

LABELS = Path(__file__).resolve().parents[1] / "labels.yaml"


def main() -> int:
    dry = "--dry-run" in sys.argv
    labels = yaml.safe_load(LABELS.read_text()) or []
    for lab in labels:
        cmd = ["gh", "label", "create", lab["name"], "--force",
               "--color", str(lab.get("color", "ededed")),
               "--description", lab.get("description", "")]
        print(" ".join(cmd[:4]))
        if not dry:
            subprocess.run(cmd, check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
