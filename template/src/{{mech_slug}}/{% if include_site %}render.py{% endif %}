"""Render the static record browser into pages/.

    python -m <slug>.render           # write pages/
    python -m <slug>.render --check   # fail if pages/ is stale

Output is deterministic, so pages/ is committed and checked byte for byte.
Edit the templates in src/<slug>/templates/, never the files in pages/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .paths import DOCS_URL, MECH_NAME, PACKAGE_DIR, PAGES_DIR, RECORD_NOUN, REPO_ROOT, REPO_URL
from .validate import iter_records, load

CURIE_BASES = {
    "PMID": "https://pubmed.ncbi.nlm.nih.gov/",
    "DOI": "https://doi.org/",
}


def curie_url(curie: str) -> str:
    prefix, _, local = curie.partition(":")
    if prefix in CURIE_BASES:
        return CURIE_BASES[prefix] + local
    return f"https://bioregistry.io/{curie}"


def build() -> dict[Path, str]:
    env = Environment(
        loader=FileSystemLoader(PACKAGE_DIR / "templates"),
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=True,
    )
    env.filters["curie_url"] = curie_url
    records = []
    for path in iter_records():
        data = load(path) or {}
        records.append({"stem": path.stem, "data": data})
    records.sort(key=lambda r: str(r["data"].get("name", r["stem"])).lower())
    ctx = {"mech_name": MECH_NAME, "record_noun": RECORD_NOUN, "repo_url": REPO_URL, "docs_url": DOCS_URL}
    out = {PAGES_DIR / "index.html": env.get_template("index.html").render(records=records, **ctx)}
    tmpl = env.get_template("record.html")
    for r in records:
        out[PAGES_DIR / "records" / f"{r['stem']}.html"] = tmpl.render(record=r, **ctx)
    out[PAGES_DIR / "style.css"] = (PACKAGE_DIR / "templates" / "style.css").read_text()
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    wanted = build()
    existing = set(PAGES_DIR.rglob("*.html")) | set(PAGES_DIR.rglob("*.css")) if PAGES_DIR.exists() else set()
    if args.check:
        if not PAGES_DIR.exists() and not iter_records():
            print("No records and no pages/ yet; nothing to check.")
            return 0
        stale = [p for p, text in wanted.items() if not p.exists() or p.read_text() != text]
        extra = sorted(existing - set(wanted))
        for p in stale + extra:
            print(f"STALE {p.relative_to(REPO_ROOT)}")
        if stale or extra:
            print("pages/ is out of date. Run `just render` and commit the result.")
            return 1
        print(f"pages/ is current ({len(wanted)} files).")
        return 0
    for p in existing - set(wanted):
        p.unlink()
    for p, text in wanted.items():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    print(f"Wrote {len(wanted)} files to {PAGES_DIR.relative_to(REPO_ROOT)}/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
