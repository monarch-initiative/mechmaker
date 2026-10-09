"""Repository constants, written by mechmaker. Edit freely."""

from pathlib import Path

SLUG = "datmech"
MECH_NAME = "DaTMech"
RECORD_CLASS = "ZipArea"
RECORD_NOUN = "ZIP code area"
# The prefix of the ontology that keys records, or "" when every id is minted.
# A record whose id has it names the same term in `record_term`.
IDENTITY_PREFIX = ""
HAS_RECORD_TERM = bool(IDENTITY_PREFIX)
REPO_URL = "https://github.com/monarch-initiative/datmech"

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
SCHEMA_DIR = PACKAGE_DIR / "schema"
SCHEMA_PATH = SCHEMA_DIR / f"{SLUG}.yaml"
HISTORY_SCHEMA_PATH = SCHEMA_DIR / "history.yaml"
RECORDS_DIR = REPO_ROOT / "data/zip_areas"
HISTORY_DIR = REPO_ROOT / "history"
REFERENCES_DIR = REPO_ROOT / "references_cache"
BUILD_DIR = REPO_ROOT / "build"
PAGES_DIR = REPO_ROOT / "pages"
