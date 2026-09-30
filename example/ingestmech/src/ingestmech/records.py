"""Writing records. Every write goes through validation first.

    python -m <slug>.records new --id <CURIE> --name "..." [--description "..."] [--apply]

Code that changes records should call `write_validated_record`, which refuses
to write an invalid record, and `append_curation_event`, which records the
change on the record itself.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import yaml

from .paths import RECORD_NOUN, RECORDS_DIR, REPO_ROOT
from .validate import evidence_errors, rule_errors, schema_errors, slugify


class _Dumper(yaml.SafeDumper):
    """Block-style YAML with multi-line strings as literal blocks.

    Lists are indented under their key ("  - item"), the layout `just
    add-evidence` keeps, so the two writers never reformat each other.
    """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def _str(dumper: yaml.SafeDumper, value: str):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str)


def dump(data: dict) -> str:
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=100)


def record_path(data: dict) -> Path:
    return RECORDS_DIR / f"{slugify(data['name'])}.yaml"


def write_validated_record(data: dict, path: Path | None = None, *, dry_run: bool = False) -> Path:
    """Validate, then write. Raises ValueError and writes nothing if invalid."""
    path = path or record_path(data)
    errors = schema_errors(data) + rule_errors(data, path) + evidence_errors(data)
    if errors:
        raise ValueError("record is invalid:\n  " + "\n  ".join(errors))
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dump(data))
    return path


def append_curation_event(
    data: dict,
    *,
    action: str,
    curator: str,
    description: str,
    llm_assisted: bool,
    model: str | None = None,
) -> dict:
    event = {
        "timestamp": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "curator": curator,
        "llm_assisted": llm_assisted,
    }
    if model:
        event["model"] = model
    event["action"] = action
    event["description"] = description
    data.setdefault("curation_history", []).append(event)
    data["updated_date"] = dt.date.today().isoformat()
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Scaffold a {RECORD_NOUN} record")
    sub = parser.add_subparsers(dest="cmd", required=True)
    new = sub.add_parser("new", help="scaffold a record (dry-run unless --apply)")
    new.add_argument("--id", required=True, help="CURIE for the record")
    new.add_argument("--name", required=True)
    new.add_argument("--description")
    new.add_argument("--curator", default="claude-code")
    new.add_argument("--model", help="model id when an agent drafts the record")
    new.add_argument("--human", action="store_true", help="a person, not a model, wrote it")
    new.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    today = dt.date.today().isoformat()
    data: dict = {"id": args.id, "name": args.name}
    if args.description:
        data["description"] = args.description
    data["status"] = "DRAFT"
    data["creation_date"] = today
    data["updated_date"] = today
    append_curation_event(
        data,
        action="CREATE",
        curator=args.curator,
        description="Scaffolded with `just new-record`.",
        llm_assisted=not args.human,
        model=args.model,
    )
    path = record_path(data)
    if path.exists():
        print(f"ERROR: {path.relative_to(REPO_ROOT)} exists")
        return 1
    try:
        write_validated_record(data, path, dry_run=not args.apply)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1
    if args.apply:
        print(path.relative_to(REPO_ROOT))
    else:
        print(dump(data))
        print(f"# dry run; would write {path.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
