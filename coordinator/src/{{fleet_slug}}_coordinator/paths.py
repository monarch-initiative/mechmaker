"""Where the Coordinator keeps things. Every command takes the repository root, so tests can use another."""

from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
SCHEMA_PATH = PACKAGE_DIR / "schema" / "fleet_schema.yaml"

# Relative to a repository root.
FLEET_FILE = "fleet.yaml"
CANON_MANIFEST = "canon/manifest.yaml"
MEMBERS_CACHE = "cache/members"

# Relative to a member's root: the pin `fleet sync` writes.
PIN_FILE = "fleet/pin.yaml"
ANSWERS_FILE = ".copier-answers.yml"
