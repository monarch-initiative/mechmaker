"""Repository constants, written by mechmaker. Edit freely."""

from pathlib import Path

SLUG = "ingestmech"
MECH_NAME = "IngestMech"
RECORD_CLASS = "Ingest"
RECORD_NOUN = "ingest"
# The prefix of the ontology that keys records, or "" when every id is minted.
# A record whose id has it names the same term in `record_term`.
IDENTITY_PREFIX = ""
HAS_RECORD_TERM = bool(IDENTITY_PREFIX)
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
