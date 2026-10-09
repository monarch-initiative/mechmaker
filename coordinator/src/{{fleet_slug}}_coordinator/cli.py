"""The `fleet` command. Run `uv run fleet --help`, or use the justfile's recipes.

    fleet validate                 fleet.yaml against the Fleet schema and its rules
    fleet answers MEMBER           the member's Copier answers, from fleet.yaml
    fleet fetch [MEMBER...]        clone or refresh members under cache/members/
    fleet status                   one row per member
    fleet canon-check              the canon's sources match canon/manifest.yaml
    fleet canon-refresh            rewrite the manifest's sha256s after a deliberate change
    fleet sync MEMBER [--apply]    copy the canon into a member checkout (dry run by default)
    fleet check-links              every link between members' records
    fleet audit                    all of it, for every member: what the daily workflow runs
    fleet docs-pages               write docs/members.md and docs/relationships.md

Commands that read members take --root ID=PATH to use a local checkout in
place of cache/members/ID.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import answers, canon, links, report
from .manifest import FleetError, load
from .members import MemberError, fetch, git, member_root, parse_roots
from .paths import REPO_ROOT


def _roots(fleet, root: Path, pairs: list[str] | None) -> dict[str, Path]:
    overrides = parse_roots(pairs)
    unknown = set(overrides) - set(fleet.members)
    if unknown:
        raise SystemExit(f"--root names {', '.join(sorted(unknown))}, not in fleet.yaml")
    return {m.id: member_root(root, m, overrides) for m in fleet.fetched()}


def _checkouts(roots: dict[str, Path]) -> tuple[dict[str, Path], list[str]]:
    """The roots that are checkouts, and an error for each that is not."""
    present = {key: mroot for key, mroot in roots.items() if (mroot / ".git").exists()}
    errors = [f"{key}: no checkout at {mroot}. Run `just fetch`, or pass --root {key}=PATH."
              for key, mroot in roots.items() if key not in present]
    return present, errors


def _member(fleet, key: str):
    if key not in fleet.members:
        raise SystemExit(f"{key} is not a member. Members: {', '.join(fleet.members) or 'none'}")
    return fleet.members[key]


def _report(errors: list[str], warnings: list[str], what: str) -> int:
    for w in warnings:
        print(f"WARNING {w}")
    for e in errors:
        print(f"ERROR {e}")
    if errors:
        print(f"{what}: {len(errors)} error(s), {len(warnings)} warning(s).")
        return 1
    print(f"{what}: passed, {len(warnings)} warning(s).")
    return 0


def audit(root: Path, fleet, roots: dict[str, Path]) -> tuple[list[str], list[str]]:
    present, missing = _checkouts(roots)
    errors = [f"canon: {e}" for e in canon.canon_errors(root)] + missing
    warnings = [f"{m.id}: planned, so not checked" for m in fleet.members.values() if m.status == "planned"]
    for member in fleet.audited():
        if member.id in present:
            errors += answers.disagreements(fleet, member, present[member.id])
    e, w = canon.audit(root, fleet, present)
    errors, warnings = errors + e, warnings + w
    for f in links.check(fleet, present):
        (errors if f.level == "error" else warnings).append(str(f).split(" ", 1)[1])
    return errors, warnings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fleet", description=__doc__.splitlines()[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--repo", type=Path, default=REPO_ROOT,
                        help="the Coordinator's root (default: this one)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    p = sub.add_parser("answers")
    p.add_argument("member")
    p = sub.add_parser("fetch")
    p.add_argument("members", nargs="*")
    for name in ("status", "check-links", "audit"):
        p = sub.add_parser(name)
        p.add_argument("--root", action="append", metavar="ID=PATH")
    sub.add_parser("canon-check")
    sub.add_parser("canon-refresh")
    p = sub.add_parser("sync")
    p.add_argument("member")
    p.add_argument("--root", required=True, metavar="PATH", help="the member's checkout")
    p.add_argument("--ref", help="the Coordinator commit to sync "
                                 "(default origin/main; HEAD with --unpublished)")
    p.add_argument("--apply", action="store_true", help="write the files; without it, only show the plan")
    p.add_argument("--unpublished", action="store_true",
                   help="allow a commit not on origin/main (a local trial; the member's online check fails)")
    sub.add_parser("docs-pages")
    args = parser.parse_args(argv)
    root = args.repo.resolve()

    try:
        fleet = load(root)
        if args.command == "validate":
            print(f"fleet.yaml: {len(fleet.members)} member(s), "
                  f"{len(fleet.relationships)} relationship(s). Valid.")
            return 0
        if args.command == "answers":
            sys.stdout.write(answers.render(fleet, _member(fleet, args.member)))
            return 0
        if args.command == "fetch":
            for line in fetch(fleet, root, args.members):
                print(line)
            return 0
        if args.command == "status":
            head = git(root, "rev-parse", "HEAD", check=False)
            sys.stdout.write(report.status(fleet, _roots(fleet, root, args.root), head))
            return 0
        if args.command == "canon-check":
            return _report(canon.canon_errors(root), [], "canon")
        if args.command == "canon-refresh":
            changed = canon.refresh(root)
            print(f"updated the sha256 of {', '.join(changed)}" if changed
                  else "the manifest already matches")
            return 0
        if args.command == "sync":
            member = _member(fleet, args.member)
            mroot = Path(args.root).expanduser().resolve()
            for line in canon.sync(root, fleet, member, mroot, args.ref, args.apply, args.unpublished):
                print(line)
            if not args.apply:
                print("Dry run. Add --apply to write.")
            else:
                print(f"Next, in {mroot}: `just qc`, then commit on a branch and open a pull request.")
            return 0
        if args.command == "check-links":
            present, missing = _checkouts(_roots(fleet, root, args.root))
            found = links.check(fleet, present)
            return _report(missing + [str(f).split(" ", 1)[1] for f in found if f.level == "error"],
                           [str(f).split(" ", 1)[1] for f in found if f.level == "warning"], "links")
        if args.command == "audit":
            return _report(*audit(root, fleet, _roots(fleet, root, args.root)), "fleet audit")
        if args.command == "docs-pages":
            for path in report.write_pages(fleet, root / "docs"):
                print(f"wrote {path.relative_to(root)}")
            return 0
    except (FleetError, MemberError, canon.CanonError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
