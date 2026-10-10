---
reference_id: url:https://raw.githubusercontent.com/monarch-initiative/zfin-ingest/19eb80855c67406acb2deac36ad18967d643fed8/src/versions.py
extractor_version: 1
url_source_version: 1
title: "https://raw.githubusercontent.com/monarch-initiative/zfin-ingest/19eb80855c67406acb2deac36ad18967d643fed8/src/versions.py"
content_type: url
---

# https://raw.githubusercontent.com/monarch-initiative/zfin-ingest/19eb80855c67406acb2deac36ad18967d643fed8/src/versions.py

## Content

"""Upstream source version fetcher for zfin-ingest.

ZFIN's downloads have no in-band version. Use HTTP Last-Modified.
The id_map_zfin.tsv mapping is tracked from a github master branch
(zebrafish-phenotype-ontology) and reported as a separate source.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kozahub_metadata_schema import (
    now_iso,
    urls_from_download_yaml,
    version_from_github_branch,
    version_from_http_last_modified,
)

INGEST_DIR = Path(__file__).resolve().parents[1]
DOWNLOAD_YAML = INGEST_DIR / "download.yaml"


def get_source_versions() -> list[dict[str, Any]]:
    zfin_urls = urls_from_download_yaml(DOWNLOAD_YAML, contains=["zfin.org"])
    zpo_urls = urls_from_download_yaml(DOWNLOAD_YAML, contains=["zebrafish-phenotype-ontology"])
    now = now_iso()

    sources: list[dict[str, Any]] = []

    if zfin_urls:
        ver, method = version_from_http_last_modified(zfin_urls[0])
        sources.append({
            "id": "infores:zfin",
            "name": "Zebrafish Information Network (ZFIN)",
            "urls": zfin_urls,
            "version": ver,
            "version_method": method,
            "retrieved_at": now,
        })

    if zpo_urls:
        ver, method = version_from_github_branch("obophenotype/zebrafish-phenotype-ontology", branch="master")
        sources.append({
            "id": "infores:zp",
            "name": "Zebrafish Phenotype Ontology id_map",
            "urls": zpo_urls,
            "version": ver,
            "version_method": method,
            "retrieved_at": now,
        })

    return sources
