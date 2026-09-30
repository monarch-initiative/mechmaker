"""Bundle the records for release.

    python -m <slug>.export

Writes build/<slug>-records.jsonl (one JSON object per record) and
build/<slug>-records.zip (the YAML files as curated).
"""

from __future__ import annotations

import json
import sys
import zipfile

from .paths import BUILD_DIR, RECORDS_DIR, REPO_ROOT, SLUG
from .validate import iter_records, load


def main() -> int:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    paths = iter_records()
    jsonl = BUILD_DIR / f"{SLUG}-records.jsonl"
    with jsonl.open("w", encoding="utf-8") as fh:
        for p in paths:
            fh.write(json.dumps(load(p), ensure_ascii=False, sort_keys=False) + "\n")
    archive = BUILD_DIR / f"{SLUG}-records.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            zf.write(p, p.relative_to(RECORDS_DIR.parent))
    print(f"{len(paths)} record(s) -> {jsonl.relative_to(REPO_ROOT)}, {archive.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
