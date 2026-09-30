---
reference_id: url:https://raw.githubusercontent.com/monarch-initiative/omim-ingest/de31fd083c8fd894eda3767085fa0452f581298c/src/versions.py
title: "https://raw.githubusercontent.com/monarch-initiative/omim-ingest/de31fd083c8fd894eda3767085fa0452f581298c/src/versions.py"
content_type: url
---

# https://raw.githubusercontent.com/monarch-initiative/omim-ingest/de31fd083c8fd894eda3767085fa0452f581298c/src/versions.py

## Content

"""Upstream source version fetcher for omim-ingest.

OMIM's morbidmap.txt has a `# Generated: YYYY-MM-DD` header line. Read
from the local file (downloading requires the MONARCH_OMIM_DOWNLOAD_KEY
env var, so a remote HEAD isn't usable).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kozahub_metadata_schema import (
    now_iso,
    urls_from_download_yaml,
    version_from_file_header,
)


INGEST_DIR = Path(__file__).resolve().parents[1]
DOWNLOAD_YAML = INGEST_DIR / "download.yaml"
MORBIDMAP = INGEST_DIR / "data" / "morbidmap.txt"


def get_source_versions() -> list[dict[str, Any]]:
    if MORBIDMAP.is_file():
        ver, method = version_from_file_header(
            MORBIDMAP, pattern=r"# Generated:\s*(\S+)", comment_prefix="#"
        )
    else:
        ver, method = "unknown", "unavailable"
    return [
        {
            "id": "infores:omim",
            "name": "OMIM (Online Mendelian Inheritance in Man)",
            "urls": urls_from_download_yaml(DOWNLOAD_YAML),
            "version": ver,
            "version_method": method,
            "retrieved_at": now_iso(),
        }
    ]
