"""Converting an existing knowledge base into records.

A conversion script reads one source and says, entry by entry, what record it
would make. This module does the rest the same way for every source:

  - every converted record starts as DRAFT, with a CREATE event that names
    the source and the entry it came from;
  - every record goes through `write_validated_record`, so an invalid one is
    reported and never written;
  - a record that already exists is left alone and reported;
  - it is a dry run unless --apply, and --apply writes one history record
    for the batch.

A script for one source, scripts/convert_<source>.py:

    from <slug>.convert import Entry, Skip, run

    def entries():
        for row in read_the_source():
            if not row["name"]:
                yield Skip(row["key"], "no name")
                continue
            yield Entry(row["key"], {"id": ..., "name": row["name"], ...})

    if __name__ == "__main__":
        raise SystemExit(run(entries(), source="Old KB", script=__file__))

Run it with `--limit 5` first. The convert-knowledge-base skill in mechmaker
says how to plan the mapping, and what to do with evidence.
"""

from __future__ import annotations

import argparse
import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .history import HISTORY_SCHEMA_PATH, build
from .paths import RECORDS_DIR, REPO_ROOT
from .records import append_curation_event, write_validated_record
from .validate import schema_errors, slugify


@dataclass
class Entry:
    """One source entry and the record it becomes."""

    key: str  # the entry's identifier in the source, kept in the CREATE event
    record: dict


@dataclass
class Skip:
    """One source entry that cannot be converted, and why."""

    key: str
    reason: str


@dataclass
class Report:
    written: list[tuple[str, Path]] = field(default_factory=list)
    exists: list[tuple[str, Path]] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)

    def print(self, applied: bool) -> None:
        verb = "Wrote" if applied else "Would write"
        for key, path in self.written:
            print(f"  {'written' if applied else 'ok     '}  {key} -> {_rel(path)}")
        for key, path in self.exists:
            print(f"  exists   {key} -> {_rel(path)} (left alone)")
        for key, reason in self.skipped:
            print(f"  SKIPPED  {key}: {reason}")
        print(f"\n{verb} {len(self.written)} record(s); {len(self.exists)} already existed; "
              f"{len(self.skipped)} could not be converted.")


def _rel(path: Path) -> Path:
    return path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path


def convert(
    entries: Iterable[Entry | Skip],
    *,
    source: str,
    curator: str = "claude-code",
    llm_assisted: bool = True,
    model: str | None = None,
    apply: bool = False,
    limit: int | None = None,
    only: set[str] | None = None,
    records_dir: Path = RECORDS_DIR,
) -> Report:
    """Validate each entry's record and, with apply, write it. Never overwrites."""
    report = Report()
    seen: dict[Path, str] = {}
    for entry in entries:
        if only and str(entry.key) not in only:
            continue
        if limit is not None and len(report.written) >= limit:
            break
        if isinstance(entry, Skip):
            report.skipped.append((entry.key, entry.reason))
            continue
        data = dict(entry.record)
        if not data.get("name"):
            report.skipped.append((entry.key, "the record has no name"))
            continue
        today = dt.date.today().isoformat()
        data["status"] = "DRAFT"
        data.setdefault("creation_date", today)
        append_curation_event(
            data, action="CREATE", curator=curator, llm_assisted=llm_assisted, model=model,
            description=f"Converted from {source}, entry {entry.key}.",
        )
        path = records_dir / f"{slugify(data['name'])}.yaml"
        if path in seen:
            report.skipped.append((entry.key, f"same record file as entry {seen[path]}: {_rel(path)}"))
            continue
        seen[path] = entry.key
        if path.exists():
            report.exists.append((entry.key, path))
            continue
        try:
            write_validated_record(data, path, dry_run=not apply)
        except ValueError as exc:
            report.skipped.append((entry.key, str(exc)))
            continue
        report.written.append((entry.key, path))
    return report


def history_record(report: Report, *, source: str, script: Path, actor: str,
                   model: str | None, human: bool) -> tuple[Path, dict]:
    """One history record for the batch, targeting the conversion script."""
    keys = ", ".join(k for k, _ in report.written)
    skips = "; ".join(f"{k} ({r.splitlines()[0]})" for k, r in report.skipped)
    details = (
        f"Converted {len(report.written)} entries of {source} with {_rel(script)}: {keys}. "
        f"Every record is DRAFT and passed closed-schema validation and the record rules. "
        f"{len(report.exists)} already existed and were left alone. "
        f"{len(report.skipped)} could not be converted{': ' + skips if skips else ''}. "
        "Evidence carried over from the source still needs review."
    )
    args = argparse.Namespace(
        kind="other", slug=f"convert-{slugify(source).replace('_', '-')}",
        path=str(_rel(script)), agent_tool=None if human else actor, actor=actor,
        actor_type="human" if human else "ai_agent", model=model, issue=None, pr=None,
        event="CREATE", outcome="changed", section=None,
        summary=f"Converted {len(report.written)} record(s) from {source}.", details=details,
    )
    return build(args)


def run(entries: Iterable[Entry | Skip], *, source: str, script: str | Path,
        argv: list[str] | None = None) -> int:
    """The command line every conversion script shares."""
    parser = argparse.ArgumentParser(description=f"Convert {source} into records")
    parser.add_argument("--apply", action="store_true", help="write the records and a history record")
    parser.add_argument("--limit", type=int, help="convert at most this many (a trial)")
    parser.add_argument("--only", action="append", help="convert only this source key; repeatable")
    parser.add_argument("--curator", default="claude-code")
    parser.add_argument("--model", help="model id, when an agent runs the conversion")
    parser.add_argument("--human", action="store_true", help="a person, not a model, ran it")
    args = parser.parse_args(argv)

    report = convert(
        entries, source=source, curator=args.curator, llm_assisted=not args.human,
        model=args.model, apply=args.apply, limit=args.limit,
        only=set(args.only) if args.only else None,
    )
    report.print(args.apply)
    if not args.apply:
        print("# dry run; pass --apply to write.")
        return 1 if report.skipped else 0
    if report.written:
        out, record = history_record(report, source=source, script=Path(script).resolve(),
                                     actor=args.curator, model=args.model, human=args.human)
        errors = schema_errors(record, "HistoryRecord", HISTORY_SCHEMA_PATH)
        if errors:
            print("ERROR: the history record is invalid: " + "; ".join(errors))
            return 1
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(yaml.safe_dump(record, sort_keys=False, allow_unicode=True, width=100),
                       encoding="utf-8")
        print(f"History: {_rel(out)}")
    return 1 if report.skipped else 0
