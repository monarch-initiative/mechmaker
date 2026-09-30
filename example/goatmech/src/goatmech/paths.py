"""Repository constants, written by mechmaker. Edit freely."""

from pathlib import Path

SLUG = "goatmech"
MECH_NAME = "GoatMech"
RECORD_CLASS = "GoatBreed"
RECORD_NOUN = "goat breed"
# Whether records are keyed to an ontology term in `record_term`.
HAS_RECORD_TERM = True
# GoatMech is an example inside mechmaker; issues and links go there.
REPO_URL = "https://github.com/monarch-initiative/mechmaker"

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
SCHEMA_DIR = PACKAGE_DIR / "schema"
SCHEMA_PATH = SCHEMA_DIR / f"{SLUG}.yaml"
HISTORY_SCHEMA_PATH = SCHEMA_DIR / "history.yaml"
RECORDS_DIR = REPO_ROOT / "data/goat_breeds"
HISTORY_DIR = REPO_ROOT / "history"
REFERENCES_DIR = REPO_ROOT / "references_cache"
BUILD_DIR = REPO_ROOT / "build"
PAGES_DIR = REPO_ROOT / "pages"
