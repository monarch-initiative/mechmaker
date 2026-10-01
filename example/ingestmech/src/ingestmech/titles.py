"""Fill missing reference_title values from the reference cache.

    python -m <slug>.titles                    # every record; dry run, prints the diff
    python -m <slug>.titles FILE [FILE...]      # some records
    python -m <slug>.titles --apply             # write

For each evidence item without a reference_title, the title comes from
references_cache/, where `just fetch-reference` and `just add-evidence` put
it. Nothing is fetched: a reference that is not cached is listed, with the
command that fetches it. A url: source with no title of its own reports its
URL, and that is not used.

Files are edited in place, layout and comments kept, and each changed record
gets one curation_history event. The whole record must still pass the schema,
the record rules and the evidence checks, or nothing is written.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import io
import sys
from pathlib import Path

from .evidence import _yaml
from .paths import REPO_ROOT
from .validate import cached_title, evidence_errors, iter_records, loads, rule_errors, schema_errors


def _items(node, where=""):
    """(location, mapping) for every evidence item, in the ruamel tree."""
    if isinstance(node, dict):
        if "reference" in node and "supports" in node:
            yield where, node
        for k, v in node.items():
            yield from _items(v, f"{where}.{k}" if where else str(k))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _items(v, f"{where}[{i}]")


def title_for(reference: str) -> str | None:
    title = cached_title(reference)
    if title and title != reference.removeprefix("url:"):
        return title
    return None


def fill(path: Path, event: dict) -> tuple[str, str, int, list[str], list[str]]:
    """(old text, new text, titles filled, references not cached, problems). Writes nothing."""
    y = _yaml()
    old = path.read_text()
    data = y.load(old)
    filled, uncached = 0, []
    for _, item in _items(data):
        if item.get("reference_title"):
            continue
        ref = str(item["reference"])
        title = title_for(ref)
        if title is None:
            if cached_title(ref) is None and ref not in uncached:
                uncached.append(ref)
            continue
        keys = list(item.keys())
        item.insert(keys.index("reference") + 1, "reference_title", title)
        filled += 1
    if not filled:
        return old, old, 0, uncached, []
    data.setdefault("curation_history", []).append(event)
    if "updated_date" in data:
        data["updated_date"] = dt.date.today().isoformat()
    buf = io.StringIO()
    y.dump(data, buf)
    new = buf.getvalue()
    parsed = loads(new)
    problems = schema_errors(parsed) + rule_errors(parsed, path) + evidence_errors(parsed)
    return old, new, filled, uncached, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="records; default every record")
    parser.add_argument("--curator", default="claude-code", help="GitHub login or harness name")
    parser.add_argument("--apply", action="store_true", help="write the files")
    args = parser.parse_args(argv)

    paths = [p.resolve() for p in args.files] or iter_records()
    event = {
        "timestamp": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "curator": args.curator,
        "llm_assisted": False,  # the titles come from the cache, not from a model
        "action": "EDIT",
        "description": "Filled reference_title from references_cache/ with `just fill-titles`.",
    }
    total, failed, uncached_all = 0, 0, {}
    for path in paths:
        rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
        old, new, filled, uncached, problems = fill(path, dict(event))
        for ref in uncached:
            uncached_all.setdefault(ref, []).append(str(rel))
        if problems:
            failed += 1
            for p in problems:
                print(f"ERROR {rel}: {p}")
            continue
        if not filled:
            continue
        total += filled
        if args.apply:
            path.write_text(new)
            print(f"{rel}: filled {filled} title(s)")
        else:
            sys.stdout.writelines(difflib.unified_diff(
                old.splitlines(keepends=True), new.splitlines(keepends=True), f"{rel}", f"{rel} (titles)"))
    if uncached_all:
        print("\nNot in references_cache/, so no title. Fetch each, then run this again:")
        for ref, files in sorted(uncached_all.items()):
            print(f"  just fetch-reference {ref}    # {', '.join(sorted(set(files)))}")
    verb = "Filled" if args.apply else "Would fill"
    print(f"\n{verb} {total} title(s)" + ("" if args.apply else "; pass --apply to write") + ".")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
