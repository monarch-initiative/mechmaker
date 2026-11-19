"""Writing records. Every write goes through validation first.

    python -m <slug>.records new --name "..." [--description "..."] [--apply]
    python -m <slug>.records new --id <CURIE> --name "..." [--apply]
    python -m <slug>.records new --id <TERM> --name "..." --term-label "<the ontology's label>" [--apply]

The record class's other top-level slots come from the schema, as flags named
for them (`--slot-name`): a slot the schema requires takes a required flag, an
enum's values are its choices, and a boolean is a switch. A required slot that
holds an object or a list of them takes YAML (`--license '{name: MIT}'`).
`python -m <slug>.records new --help` lists this Mech's.

Without --id, the record gets a minted id, `<slug>:<uuid>`: unique, and
unchanged when the record is renamed. Pass --id when something better keys
the record: an ontology term, or a stable identifier from a source.

Code that changes records should call `write_validated_record`, which refuses
to write an invalid record, and `append_curation_event`, which records the
change on the record itself.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import uuid
from functools import cache
from pathlib import Path
from typing import NamedTuple

import yaml

from .paths import IDENTITY_PREFIX, RECORD_CLASS, RECORD_NOUN, RECORDS_DIR, REPO_ROOT, SCHEMA_PATH, SLUG
from .validate import evidence_errors, loads, record_ids, rule_errors, schema_errors, slugify


class _Dumper(yaml.SafeDumper):
    """Block-style YAML with multi-line strings as literal blocks.

    Lists are indented under their key ("  - item") and long lines are never
    folded: the layout `just add-evidence` keeps, so the two writers never
    reformat each other.
    """

    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def _str(dumper: yaml.SafeDumper, value: str):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str)


def dump(data: dict) -> str:
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=4096)


def mint_id() -> str:
    """A new id in the Mech's own namespace, for a record nothing else keys."""
    return f"{SLUG}:{uuid.uuid4()}"


# Slots the scaffold sets itself, whatever the schema says.
SCAFFOLD_SLOTS = {"id", "name", "description", "record_term", "status", "creation_date", "updated_date",
                  "curation_history"}
# The scaffold's own flags. A slot whose flag would be one of these is offered as --slot-<name>.
OWN_FLAGS = {"id", "name", "description", "term-label", "curator", "model", "human", "apply", "help"}
NUMBERS = {"integer": int, "float": float, "double": float, "decimal": float}


class SlotFlag(NamedTuple):
    slot: str
    flag: str  # without the leading --
    required: bool
    multivalued: bool
    kind: str  # enum, boolean, integer, float, string or object (YAML)
    choices: tuple[str, ...]  # an enum's permissible values; empty for a dynamic enum
    help: str


@cache
def _view(schema: str):
    from linkml_runtime.utils.schemaview import SchemaView

    return SchemaView(schema)


def slot_flags(schema: Path = SCHEMA_PATH, record_class: str = RECORD_CLASS) -> list[SlotFlag]:
    """A flag for each top-level slot of the record class that the scaffold does not set.

    Every slot whose range is a type or an enum gets one, so a domain rule that
    needs an optional value can be met at scaffolding. A slot whose range is a
    class gets one only when the schema requires it, and takes YAML.
    """
    view = _view(str(schema))
    enums, classes = set(view.all_enums()), set(view.all_classes())
    flags = []
    for slot in view.class_induced_slots(record_class):
        if slot.name in SCAFFOLD_SLOTS:
            continue
        rng = slot.range or view.schema.default_range or "string"
        choices: tuple[str, ...] = ()
        if rng in enums:
            kind = "enum"
            choices = tuple(view.get_enum(rng).permissible_values or ())
        elif rng in classes:
            if not slot.required:
                continue
            kind = "object"
        else:
            base = set(view.type_ancestors(rng)) if rng in view.all_types() else {rng}
            kind = next((k for k in ("boolean", *NUMBERS) if k in base), "string")
            kind = "float" if kind in ("double", "decimal") else kind
        flag = slot.name.replace("_", "-")
        if flag in OWN_FLAGS:
            flag = f"slot-{flag}"
        # argparse formats help with %, so a literal one is doubled.
        text = (slot.description or "").strip().split("\n")[0].replace("%", "%%")
        flags.append(SlotFlag(slot.name, flag, bool(slot.required), bool(slot.multivalued), kind, choices,
                              f"{text} [{slot.name}: {rng}{', required' if slot.required else ''}]".strip()))
    return flags


def id_pattern(schema: Path = SCHEMA_PATH, record_class: str = RECORD_CLASS) -> str | None:
    """The pattern the schema sets on the record's id, if any."""
    return _view(str(schema)).induced_slot("id", record_class).pattern


def description_required(schema: Path = SCHEMA_PATH, record_class: str = RECORD_CLASS) -> bool:
    view = _view(str(schema))
    return any(s.name == "description" and s.required for s in view.class_induced_slots(record_class))


def _add_flag(parser, f: SlotFlag) -> None:
    kw: dict = {"dest": f"slot__{f.slot}", "help": f.help, "required": f.required,
                "metavar": f.slot.upper()}
    if f.multivalued:
        kw["help"] = f"{f.help} (repeat for more)"
    if f.kind == "boolean" and not f.multivalued:
        if f.required:
            kw["choices"] = ("true", "false")
            kw["type"] = str.lower
            del kw["metavar"]
        else:
            kw["action"] = "store_true"
            del kw["required"], kw["metavar"]
            kw["default"] = None
        parser.add_argument(f"--{f.flag}", **kw)
        return
    if f.kind == "object":
        kw["type"] = loads  # dates stay strings, as in a record file
        kw["metavar"] = "YAML"
    elif f.kind in NUMBERS:
        kw["type"] = NUMBERS[f.kind]
    elif f.kind == "boolean":
        kw["choices"] = ("true", "false")
        kw["type"] = str.lower
        del kw["metavar"]
    elif f.choices:
        kw["choices"] = f.choices
        del kw["metavar"]
    if f.multivalued and f.kind != "object":
        kw["action"] = "append"
    parser.add_argument(f"--{f.flag}", **kw)


def _slot_value(f: SlotFlag, value):
    if f.kind == "boolean":
        return [v == "true" for v in value] if f.multivalued else value in (True, "true")
    return value


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
        path.write_text(dump(data), encoding="utf-8")
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
    new.add_argument("--id", help=f"CURIE for the record (default: a minted {SLUG}:<uuid>)")
    new.add_argument("--name", required=True)
    new.add_argument("--description", required=description_required())
    new.add_argument("--term-label", help="the ontology's label for --id, from `just term-info`; "
                     "required when --id is an ontology term")
    new.add_argument("--curator", default="claude-code")
    new.add_argument("--model", help="model id when an agent drafts the record")
    new.add_argument("--human", action="store_true", help="a person, not a model, wrote it")
    new.add_argument("--apply", action="store_true")
    flags = slot_flags()
    slots = new.add_argument_group(f"{RECORD_CLASS} slots, from the schema")
    for f in flags:
        _add_flag(slots, f)
    args = parser.parse_args(argv)

    today = dt.date.today().isoformat()
    rid = args.id or mint_id()
    pattern = id_pattern()
    if not args.id and pattern and not re.search(pattern, rid):
        print(f"ERROR: a minted id ({SLUG}:<uuid>) does not match this Mech's id pattern {pattern!r}. "
              "Pass --id.")
        return 1
    data: dict = {"id": rid, "name": args.name}
    if args.description:
        data["description"] = args.description
    if IDENTITY_PREFIX and rid.startswith(f"{IDENTITY_PREFIX}:"):
        if not args.term_label:
            print(f"ERROR: {rid} has the {IDENTITY_PREFIX} prefix. Pass --term-label with its label: "
                  f"`just term-info {IDENTITY_PREFIX} {rid}`")
            return 1
        data["record_term"] = {"id": rid, "label": args.term_label}
    data["status"] = "DRAFT"
    for f in flags:
        value = getattr(args, f"slot__{f.slot}")
        if value is not None:
            data[f.slot] = _slot_value(f, value)
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
        print(f"ERROR: {_rel(path)} exists")
        return 1
    taken = record_ids(path.parent).get(rid)
    if taken:
        print(f"ERROR: id {rid} is already used by {_rel(taken)}")
        return 1
    try:
        write_validated_record(data, path, dry_run=not args.apply)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 1
    if args.apply:
        print(_rel(path))
    else:
        print(dump(data))
        print(f"# dry run; would write {_rel(path)}")
    return 0


def _rel(path: Path) -> Path:
    return path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path


if __name__ == "__main__":
    sys.exit(main())
