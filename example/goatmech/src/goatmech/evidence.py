"""Add an evidence item to a record, checked before it is written.

    python -m <slug>.evidence FILE --at PLACE --ref REFERENCE --snippet "QUOTE" [options] [--apply]

PLACE is where the evidence goes: `record` for the record's own `evidence`
list, `description` for the facts in the record's description (its
`description_evidence`), or a path such as `distinguishing_features[0]`,
`measurements[2]` or `mechanisms[0].downstream[1]`.

Before anything is written:
  - the reference is fetched into references_cache/ if it is not there yet;
  - the snippet is checked against it with linkml-reference-validator, the
    same check `just validate` runs;
  - reference_title is filled from the fetched source;
  - the whole record, with the new item and a curation_history event, must
    pass closed-schema validation and the record rules.

The file is edited in place with its layout, comments and quoting kept, so
the diff shows only what was added. Dry run by default: it prints that diff.
"""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import io
import os
import re
import sys
from pathlib import Path

from ruamel.yaml import YAML

from .paths import REPO_ROOT
from .validate import evidence_errors, loads, rule_errors, schema_errors

CONFIG = REPO_ROOT / ".linkml-reference-validator.yaml"
PLACE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)(?:\[(\d+)\])?")


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096  # never fold a long snippet across lines
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def resolve(data, place: str):
    """The mapping at PLACE, or raise ValueError saying what is there instead."""
    if place in ("", "record", "."):
        return data
    node = data
    walked = []
    for part in place.split("."):
        m = PLACE.fullmatch(part)
        if not m:
            raise ValueError(f"cannot read {part!r} in {place!r}; write e.g. measurements[0]")
        key, index = m.group(1), m.group(2)
        if not isinstance(node, dict) or key not in node:
            keys = ", ".join(k for k in node) if isinstance(node, dict) else "nothing"
            raise ValueError(f"{'.'.join(walked) or 'the record'} has no {key!r}; it has: {keys}")
        node = node[key]
        walked.append(key)
        if index is not None:
            i = int(index)
            if not isinstance(node, list) or i >= len(node):
                size = len(node) if isinstance(node, list) else 0
                raise ValueError(f"{'.'.join(walked)} has {size} item(s); [{i}] is out of range")
            node = node[i]
            walked[-1] += f"[{i}]"
    if not isinstance(node, dict):
        raise ValueError(f"{place} is not an object that can carry evidence")
    return node


def fetch_and_check(reference: str, snippet: str) -> tuple[bool, str, str | None]:
    """(quote found, message, source title). Fetches into references_cache/ if needed."""
    from linkml_reference_validator.cli.shared import load_validation_config
    from linkml_reference_validator.validation.supporting_text_validator import SupportingTextValidator

    config = load_validation_config(CONFIG if CONFIG.exists() else None)
    validator = SupportingTextValidator(config)
    content = validator.fetcher.fetch(reference)
    if content is None:
        return False, f"{reference} could not be fetched; check the identifier", None
    result = validator.validate(snippet, reference)
    return bool(result.is_valid), str(result.message or ""), getattr(content, "title", None)


def add(path: Path, place: str, item: dict, event: dict, check=fetch_and_check) -> tuple[str, str, list[str]]:
    """(old text, new text, problems). Writes nothing."""
    y = _yaml()
    old = path.read_text(encoding="utf-8")
    data = y.load(old)
    if place == "description":
        if not data.get("description"):
            raise ValueError("the record has no description to support")
        target, key = data, "description_evidence"
    else:
        target, key = resolve(data, place), "evidence"

    problems = []
    ok, message, title = check(item["reference"], item["snippet"])
    if not ok:
        problems.append(f"the snippet was not found in {item['reference']}: {message}")
    # A url: source with no title of its own reports the URL; that says nothing new.
    if title and title != item["reference"].removeprefix("url:") and "reference_title" not in item:
        item = {"reference": item["reference"], "reference_title": str(title),
                **{k: v for k, v in item.items() if k != "reference"}}
    existing = target.get(key) or []
    if any(e.get("reference") == item["reference"] and e.get("snippet") == item["snippet"] for e in existing):
        problems.append("this reference and snippet are already on that item")
    if problems:
        return old, old, problems

    if key not in target:
        if key == "description_evidence":
            # Right after the description, where a reader looks for it.
            target.insert(list(target.keys()).index("description") + 1, key, [])
        else:
            target[key] = []
    target[key].append(item)
    data.setdefault("curation_history", []).append(event)
    if "updated_date" in data:
        data["updated_date"] = dt.date.today().isoformat()

    buf = io.StringIO()
    y.dump(data, buf)
    new = buf.getvalue()
    parsed = loads(new)
    problems = schema_errors(parsed) + rule_errors(parsed, path) + evidence_errors(parsed)
    return old, new, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", type=Path)
    parser.add_argument("--at", required=True, help="record, description, or a path such as measurements[0]")
    parser.add_argument("--ref", required=True, help="e.g. PMID:12345678, DOI:10..., WIKIPEDIA:Title")
    parser.add_argument("--snippet", required=True, help="a verbatim quote from the source")
    parser.add_argument("--supports", default="SUPPORT")
    parser.add_argument("--source", help="evidence_source value")
    parser.add_argument("--explanation", help="how the quote bears on the claim")
    parser.add_argument("--curator", default="claude-code")
    parser.add_argument("--model", help="model id, when an agent adds the evidence")
    parser.add_argument("--human", action="store_true", help="a person, not a model, chose this evidence")
    parser.add_argument("--apply", action="store_true", help="write the file")
    args = parser.parse_args(argv)

    path = args.file.resolve()  # before the chdir, so a relative path means what the user meant
    os.chdir(REPO_ROOT)  # the validator finds its config and custom sources here
    item = {"reference": args.ref, "supports": args.supports}
    if args.source:
        item["evidence_source"] = args.source
    item["snippet"] = args.snippet
    if args.explanation:
        item["explanation"] = args.explanation
    event = {
        "timestamp": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "curator": args.curator,
        "llm_assisted": not args.human,
        **({"model": args.model} if args.model else {}),
        "action": "EDIT",
        "description": f"Added evidence from {args.ref} to {args.at}.",
    }
    try:
        old, new, problems = add(path, args.at, item, event)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1
    if problems:
        for p in problems:
            print(f"ERROR: {p}")
        print("Nothing was written.")
        return 1
    rel = path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path
    if not args.apply:
        sys.stdout.writelines(difflib.unified_diff(
            old.splitlines(keepends=True), new.splitlines(keepends=True), f"{rel}", f"{rel} (with evidence)"))
        print(f"\n# dry run; the quote was found. Pass --apply to write {rel}.")
        return 0
    path.write_text(new, encoding="utf-8")
    print(f"Added evidence from {args.ref} to {args.at} in {rel}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
