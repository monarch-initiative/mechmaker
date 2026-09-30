"""Render the static record browser into pages/.

    python -m <slug>.render           # write pages/
    python -m <slug>.render --check   # fail if pages/ is stale

Output is deterministic, so pages/ is committed and checked byte for byte.
Edit the templates in src/<slug>/templates/, never the files in pages/.
Colors, title, columns and hidden sections come from conf/site.yaml.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from . import site
from .paths import MECH_NAME, PACKAGE_DIR, PAGES_DIR, RECORD_NOUN, REPO_ROOT, REPO_URL
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


def cell(value) -> str:
    """How a record field shows in the front-page table."""
    if isinstance(value, dict):
        named = value.get("label") or value.get("preferred_term") or value.get("id")
        if named:
            return str(named)
        # A small statement such as {"purpose": "DAIRY"}: show its first plain value.
        plain = [v for v in value.values() if isinstance(v, (str, int, float))]
        return str(plain[0]) if plain else ""
    if isinstance(value, list):
        return ", ".join(cell(v) for v in value)
    return "" if value is None else str(value)


def build() -> dict[Path, str]:
    settings = site.load()
    errors = site.problems(settings)
    if errors:
        raise SystemExit("conf/site.yaml: " + "; ".join(errors))
    env = Environment(
        loader=FileSystemLoader(PACKAGE_DIR / "templates"),
        autoescape=select_autoescape(["html"]),
        keep_trailing_newline=True,
    )
    env.filters["curie_url"] = curie_url
    env.filters["cell"] = cell
    records = []
    for path in iter_records():
        data = load(path) or {}
        records.append({"stem": path.stem, "data": data})
    records.sort(key=lambda r: str(r["data"].get("name", r["stem"])).lower())
    ctx = {"mech_name": MECH_NAME, "record_noun": RECORD_NOUN, "repo_url": REPO_URL, "site": settings}
    out = {PAGES_DIR / "index.html": env.get_template("index.html").render(records=records, **ctx)}
    tmpl = env.get_template("record.html")
    for r in records:
        out[PAGES_DIR / "records" / f"{r['stem']}.html"] = tmpl.render(record=r, **ctx)
    css = env.get_template("style.css").render(theme=settings["theme"], **site.colors(settings))
    out[PAGES_DIR / "style.css"] = css
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
