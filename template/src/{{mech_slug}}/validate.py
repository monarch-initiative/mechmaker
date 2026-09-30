"""Closed-schema validation of records, plus the record-level rules a schema cannot state.

    python -m <slug>.validate                 # every record
    python -m <slug>.validate path/to/a.yaml  # some records

Closed mode matters. linkml-validate is open by default and accepts a
misspelled field without complaint. Here an unknown field is an error.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from collections.abc import Iterable
from functools import cache
from pathlib import Path

import yaml
from linkml.validator import Validator
from linkml.validator.plugins import JsonschemaValidationPlugin
from linkml.validator.report import Severity

from .paths import RECORD_CLASS, RECORDS_DIR, REPO_ROOT, SCHEMA_PATH


def slugify(name: str) -> str:
    """The filename stem a record's name implies: lowercase, underscores, no punctuation."""
    s = re.sub(r"[^A-Za-z0-9]+", "_", name.strip()).strip("_")
    return s.lower()


@cache
def _validator(schema_path: str) -> Validator:
    return Validator(
        schema_path,
        validation_plugins=[JsonschemaValidationPlugin(closed=True)],
    )


def schema_errors(data: object, target_class: str = RECORD_CLASS, schema: Path = SCHEMA_PATH) -> list[str]:
    report = _validator(str(schema)).validate(data, target_class)
    return [r.message for r in report.results if r.severity in (Severity.ERROR, Severity.FATAL)]


def rule_errors(data: dict, path: Path | None = None) -> list[str]:
    """Rules the schema cannot express. Add domain rules here."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["record is not a mapping"]

    name = data.get("name")
    if path is not None and isinstance(name, str) and path.stem != slugify(name):
        errors.append(f"filename stem {path.stem!r} should be {slugify(name)!r}, derived from name")

    nodes = data.get("mechanisms") or []
    names = [n.get("name") for n in nodes if isinstance(n, dict)]
    for dup, count in Counter(names).items():
        if count > 1:
            errors.append(f"mechanism node name {dup!r} is used {count} times")
    known = set(names)
    for node in nodes:
        for edge in (node or {}).get("downstream") or []:
            target = (edge or {}).get("target")
            if target not in known:
                errors.append(f"edge {node.get('name')!r} -> {target!r}: no node has that name")

    if data.get("status") == "REVIEWED":
        events = data.get("curation_history") or []
        if not any(e.get("action") == "REVIEW" and not e.get("llm_assisted") for e in events):
            errors.append("status is REVIEWED but no human REVIEW event is in curation_history")
    return errors


class _Loader(yaml.SafeLoader):
    """SafeLoader that leaves dates and times as strings, as the schema expects."""


_Loader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def loads(text: str) -> object:
    return yaml.load(text, Loader=_Loader)


def load(path: Path) -> object:
    return loads(path.read_text())


def iter_records(root: Path = RECORDS_DIR) -> list[Path]:
    return sorted(root.rglob("*.yaml")) if root.exists() else []


def validate_paths(paths: Iterable[Path]) -> dict[Path, list[str]]:
    failures: dict[Path, list[str]] = {}
    ids: dict[str, Path] = {}
    for path in paths:
        try:
            data = load(path)
        except yaml.YAMLError as exc:
            failures[path] = [f"YAML parse error: {exc}"]
            continue
        errors = schema_errors(data) + rule_errors(data, path)
        rid = data.get("id") if isinstance(data, dict) else None
        if rid in ids:
            errors.append(f"id {rid} is also used by {ids[rid]}")
        elif rid:
            ids[rid] = path
        if errors:
            failures[path] = errors
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", type=Path, help="records to check (default: all)")
    args = parser.parse_args(argv)
    paths = args.paths or iter_records()
    failures = validate_paths(paths)
    for path, errors in failures.items():
        shown = path.resolve().relative_to(REPO_ROOT) if path.resolve().is_relative_to(REPO_ROOT) else path
        for err in errors:
            print(f"ERROR {shown}: {err}")
    print(f"{len(paths)} record(s) checked, {len(failures)} with errors.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
