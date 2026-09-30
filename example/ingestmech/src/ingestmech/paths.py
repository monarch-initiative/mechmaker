"""Repository constants, written by mechmaker. Edit freely."""

from pathlib import Path

SLUG = "ingestmech"
MECH_NAME = "IngestMech"
RECORD_CLASS = "Ingest"
RECORD_NOUN = "ingest"
# Whether records are keyed to an ontology term in `record_term`.
HAS_RECORD_TERM = False
# IngestMech is an example inside mechmaker; issues and links go there.
REPO_URL = "https://github.com/monarch-initiative/mechmaker"

PACKAGE_DIR = Path(__file__).resolve().parent
REPO_ROOT = PACKAGE_DIR.parents[1]
SCHEMA_DIR = PACKAGE_DIR / "schema"
SCHEMA_PATH = SCHEMA_DIR / f"{SLUG}.yaml"
HISTORY_SCHEMA_PATH = SCHEMA_DIR / "history.yaml"
RECORDS_DIR = REPO_ROOT / "data/ingests"
HISTORY_DIR = REPO_ROOT / "history"
REFERENCES_DIR = REPO_ROOT / "references_cache"
BUILD_DIR = REPO_ROOT / "build"
PAGES_DIR = REPO_ROOT / "pages"
