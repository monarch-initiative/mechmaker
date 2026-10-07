"""Closed-schema validation of records, plus the record-level rules a schema cannot state.

    python -m <slug>.validate                 # every record
    python -m <slug>.validate path/to/a.yaml  # some records

Closed mode matters. linkml-validate is open by default and accepts a
misspelled field without complaint. Here an unknown field is an error.
"""

from __future__ import annotations

import argparse
import difflib
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

from .paths import IDENTITY_PREFIX, RECORD_CLASS, RECORDS_DIR, REPO_ROOT, SCHEMA_PATH

REF_CONFIG = REPO_ROOT / ".linkml-reference-validator.yaml"

# How alike an evidence item's reference_title must be to the cached title.
TITLE_SIMILARITY = 0.85


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

    # The term check reaches the identity root through record_term only, so a
    # record keyed by an ontology term must name that term there too.
    rid = str(data.get("id", ""))
    if IDENTITY_PREFIX and rid.startswith(f"{IDENTITY_PREFIX}:"):
        term = data.get("record_term")
        term_id = term.get("id") if isinstance(term, dict) else None
        if term_id is None:
            errors.append(f"id {rid} has the {IDENTITY_PREFIX} prefix, so record_term must name it, "
                          "with the ontology's label")
        elif term_id != rid:
            errors.append(f"record_term.id {term_id} is not the record's id {rid}")

    nodes = data.get("mechanisms") or []
    names = [n.get("name") for n in nodes if isinstance(n, dict)]
    for dup, count in Counter(names).items():
        if count > 1:
            errors.append(f"mechanism node name {dup!r} is used {count} times")
    known = set(names)
    for node in (n for n in nodes if isinstance(n, dict)):  # the schema check reports the rest
        for edge in node.get("downstream") or []:
            if not isinstance(edge, dict):
                continue
            target = edge.get("target")
            if target not in known:
                errors.append(f"edge {node.get('name')!r} -> {target!r}: no node has that name")

    if data.get("status") == "REVIEWED":
        events = data.get("curation_history") or []
        if not any(isinstance(e, dict) and e.get("action") == "REVIEW" and not e.get("llm_assisted")
                   for e in events):
            errors.append("status is REVIEWED but no human REVIEW event is in curation_history")
    return errors


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps dates as strings and rejects duplicate keys."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    None, None, f"duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


_Loader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def loads(text: str) -> object:
    return yaml.load(text, Loader=_Loader)


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", str(text).lower()).split())


@cache
def _fetcher():
    """linkml-reference-validator's fetcher, configured as `just validate-references` runs it.

    Used only for its cache paths, which never touch the network.
    """
    from linkml_reference_validator.cli.shared import load_validation_config
    from linkml_reference_validator.etl.reference_fetcher import ReferenceFetcher

    config = load_validation_config(REF_CONFIG if REF_CONFIG.exists() else None, load_custom_sources=False)
    config.cache_dir = REPO_ROOT / config.cache_dir  # relative to the repository, not the working directory
    return ReferenceFetcher(config)


def cached_title(reference: str) -> str | None:
    """The title linkml-reference-validator cached for a reference, if any.

    The validator's own normalization finds the file: pmid:1 is cached as PMID_1.md.
    """
    fetcher = _fetcher()
    path = fetcher.get_cache_path(fetcher.normalize_reference_id(reference))
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---"):
        return None
    front = text.split("---", 2)[1]
    try:
        meta = yaml.safe_load(front) or {}
    except yaml.YAMLError:
        return None
    title = meta.get("title")
    return str(title) if title else None


def _evidence_items(obj, where: str = ""):
    if isinstance(obj, dict):
        if "reference" in obj and "supports" in obj:
            yield where, obj
        for k, v in obj.items():
            yield from _evidence_items(v, f"{where}.{k}" if where else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _evidence_items(v, f"{where}[{i}]")


def evidence_errors(data: dict) -> list[str]:
    """Checks on evidence that need the reference cache but not the network.

    A snippet that only repeats the paper's title overstates what the paper
    showed. A reference_title that does not match the cached title usually
    means the wrong reference, or a title written from memory.
    """
    errors: list[str] = []
    for where, ev in _evidence_items(data):
        title = cached_title(str(ev.get("reference", "")))
        if title is None:
            continue
        t = _norm(title)
        snippet = _norm(ev.get("snippet", "")) if ev.get("snippet") else ""
        if snippet and len(snippet) >= 15 and snippet in t:
            errors.append(f"{where}: snippet only quotes the title of {ev['reference']}; "
                          "quote the abstract or text")
        given = ev.get("reference_title")
        if given:
            g = _norm(given)
            close = difflib.SequenceMatcher(None, g, t).ratio() >= TITLE_SIMILARITY
            if not (close or g in t or t in g):
                errors.append(f"{where}: reference_title does not match the cached title of "
                              f"{ev['reference']}: {title!r}")
    return errors


def load(path: Path) -> object:
    return loads(path.read_text(encoding="utf-8"))


def iter_records(root: Path = RECORDS_DIR) -> list[Path]:
    return sorted(root.rglob("*.yaml")) if root.exists() else []


def record_ids(root: Path = RECORDS_DIR) -> dict[str, Path]:
    """The id of every record under root. A file that does not parse is left to `just validate`."""
    ids: dict[str, Path] = {}
    for path in iter_records(root):
        try:
            data = load(path)
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and data.get("id"):
            ids.setdefault(str(data["id"]), path)
    return ids


def validate_paths(paths: Iterable[Path]) -> dict[Path, list[str]]:
    failures: dict[Path, list[str]] = {}
    ids: dict[str, Path] = {}
    stems: dict[str, Path] = {}
    for path in paths:
        try:
            data = load(path)
        except yaml.YAMLError as exc:
            failures[path] = [f"YAML parse error: {exc}"]
            continue
        errors = schema_errors(data) + rule_errors(data, path)
        if isinstance(data, dict):
            errors += evidence_errors(data)
        rid = data.get("id") if isinstance(data, dict) else None
        if rid in ids:
            errors.append(f"id {rid} is also used by {ids[rid]}")
        elif rid:
            ids[rid] = path
        # The record browser, history and research name a record by its stem alone.
        if path.stem in stems:
            errors.append(f"filename stem {path.stem!r} is also used by {stems[path.stem]}")
        else:
            stems[path.stem] = path
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
