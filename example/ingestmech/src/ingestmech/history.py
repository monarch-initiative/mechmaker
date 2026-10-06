"""The append-only curation history layer under history/.

One record per session per target, written once and never edited, at
history/<kind-dir>/<slug>/<TIMESTAMP>-<actor>-<shortid>.yaml. Concurrent
sessions never write the same file, so the layer cannot conflict in a merge.

    python -m <slug>.history new --kind record --slug example --event CREATE \\
        --outcome changed --summary "..." --details "..." [--apply]
    python -m <slug>.history validate [history/]

The schema is the vendored history.yaml, byte-identical to the fleet canon.
Do not hand-write records or their filenames. Use `just new-history`.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import sys
from pathlib import Path

import yaml

from .paths import HISTORY_DIR, HISTORY_SCHEMA_PATH, RECORDS_DIR, REPO_ROOT, REPO_URL
from .validate import load, schema_errors

# The fleet's directory names for each target kind. The pluralization is
# uneven on purpose; it matches the canonical scaffolder.
KIND_DIRS = {
    "record": "records",
    "schema": "schema",
    "mapping": "mappings",
    "report": "reports",
    "infrastructure": "infrastructure",
    "other": "other",
}
EVENTS = ("GENERAL", "CREATE", "EDIT", "REVIEW", "AUDIT")
OUTCOMES = ("changed", "no_change", "needs_followup", "blocked")
ACTOR_TYPES = ("human", "ai_agent", "automation", "other")

# The schema rejects details that start with this exact string, so an
# unfilled scaffold cannot be committed. Keep it byte-identical.
PLACEHOLDER = (
    "TODO: replace this placeholder before committing.\n"
    "What was done, what evidence or provider was used, how it was validated, "
    "and anything deliberately left undone."
)


def _url(kind: str, value: str) -> str:
    return value if value.startswith("http") else f"{REPO_URL}/{kind}/{value.lstrip('#')}"


def _target_path(kind: str, slug: str | None, path: str | None) -> str:
    if path:
        return path
    if kind == "record" and slug:
        matches = sorted(RECORDS_DIR.rglob(f"{slug}.yaml"))
        if matches:
            return str(matches[0].relative_to(REPO_ROOT))
        return str((RECORDS_DIR / f"{slug}.yaml").relative_to(REPO_ROOT))
    raise SystemExit(f"--path is required for kind {kind!r}")


def build(args: argparse.Namespace) -> tuple[Path, dict]:
    now = dt.datetime.now(dt.UTC).replace(microsecond=0)
    stamp = now.strftime("%Y-%m-%dT%H%M%SZ")
    actor = args.agent_tool or args.actor
    target_path = _target_path(args.kind, args.slug, args.path)
    slug = args.slug or Path(target_path).stem
    seed = "|".join([stamp, actor, args.kind, slug, args.summary])
    short = hashlib.sha256(seed.encode()).hexdigest()[:6]
    session_id = f"{stamp}-{actor}-{short}"

    actor_rec: dict = {"type": args.actor_type, "name": args.actor}
    if args.model:
        actor_rec["model"] = args.model
    if args.agent_tool:
        actor_rec["agent_tool"] = args.agent_tool

    record: dict = {
        "history_version": 1,
        "target": {"kind": args.kind, "slug": slug, "path": target_path},
        "session": {
            "id": session_id,
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "actors": [actor_rec],
        },
    }
    links = {}
    if args.issue:
        links["issues"] = [_url("issues", i) for i in args.issue]
    if args.pr:
        links["prs"] = [_url("pull", p) for p in args.pr]
    if links:
        record["links"] = links
    event: dict = {"type": args.event, "outcome": args.outcome}
    if args.section:
        event["sections"] = args.section
    event["summary"] = args.summary
    event["details"] = args.details or PLACEHOLDER
    record["events"] = [event]

    out = HISTORY_DIR / KIND_DIRS[args.kind] / slug / f"{session_id}.yaml"
    return out, record


def validate_history(target: Path) -> dict[Path, list[str]]:
    files = sorted(target.rglob("*.yaml")) if target.is_dir() else [target]
    failures: dict[Path, list[str]] = {}
    for f in files:
        try:
            data = load(f)
        except yaml.YAMLError as exc:
            failures[f] = [f"YAML parse error: {exc}"]
            continue
        errors = schema_errors(data, "HistoryRecord", HISTORY_SCHEMA_PATH)
        session = data.get("session") if isinstance(data, dict) else None
        sid = session.get("id") if isinstance(session, dict) else None
        if sid and sid != f.stem:
            errors.append(f"session.id {sid!r} does not match filename stem {f.stem!r}")
        if errors:
            failures[f] = errors
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Curation history records")
    sub = parser.add_subparsers(dest="cmd", required=True)

    new = sub.add_parser("new", help="scaffold a record (dry-run unless --apply)")
    new.add_argument("--kind", choices=list(KIND_DIRS), required=True)
    new.add_argument("--slug", help="target slug; for records, the record filename stem")
    new.add_argument("--path", help="repo-relative target path (derived for records)")
    new.add_argument("--event", choices=EVENTS, required=True)
    new.add_argument("--outcome", choices=OUTCOMES, required=True)
    new.add_argument("--summary", required=True)
    new.add_argument("--details", help="what was done, with what evidence, what was left undone")
    new.add_argument("--section", action="append", help="record section touched; repeatable")
    new.add_argument("--actor", default="claude-code", help="GitHub login or harness name")
    new.add_argument("--actor-type", choices=ACTOR_TYPES, default="ai_agent")
    new.add_argument("--model", help="model id, e.g. claude-opus-5-5")
    new.add_argument("--agent-tool", help="harness, e.g. claude-code")
    new.add_argument("--issue", action="append", help="issue number or URL; repeatable")
    new.add_argument("--pr", action="append", help="PR number or URL; repeatable")
    new.add_argument("--apply", action="store_true", help="write the file")

    val = sub.add_parser("validate", help="validate history records")
    val.add_argument("target", nargs="?", type=Path, default=HISTORY_DIR)

    args = parser.parse_args(argv)
    if args.cmd == "validate":
        if not args.target.exists():
            print(f"{args.target} does not exist; nothing to validate.")
            return 0
        failures = validate_history(args.target)
        for f, errs in failures.items():
            for e in errs:
                print(f"ERROR {f}: {e}")
        print(f"{len(failures)} history record(s) with errors.")
        return 1 if failures else 0

    out, record = build(args)
    errors = schema_errors(record, "HistoryRecord", HISTORY_SCHEMA_PATH)
    text = yaml.safe_dump(record, sort_keys=False, allow_unicode=True, width=100)
    if not args.apply:
        print(text)
        print(f"# dry run; would write {out.relative_to(REPO_ROOT)}")
        if errors:
            print("# not yet valid: " + "; ".join(errors))
        return 0
    if errors:
        for e in errors:
            print(f"ERROR: {e}")
        return 1
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        print(f"ERROR: {out} exists; history records are never overwritten")
        return 1
    out.write_text(text, encoding="utf-8")
    print(out.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
