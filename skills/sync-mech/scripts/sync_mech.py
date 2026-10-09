#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Show what a Mech would gain from a newer mechmaker, and take the parts chosen.

    uv run sync_mech.py check <mech>                    # how far behind, without rendering
    uv run sync_mech.py plan <mech>                     # every update, file by file
    uv run sync_mech.py plan <mech> --to HEAD --json    # against mechmaker's main, as JSON
    uv run sync_mech.py apply <mech> --accept '#63' '#65'   # take those, leave the rest
    uv run sync_mech.py apply <mech> --decline '#64'        # take all but that one

The Mech's `.copier-answers.yml` names the template (`_src_path`) and the
commit it last matched (`_commit`). `plan` renders the Mech's answers at that
commit, at each mechmaker pull request merged since, and at the target (the
latest release tag unless --to says otherwise). Each pull request whose render
differs is one update, and each file it changes is compared three ways: the
template then, the template now, and the Mech's own copy.

    take      the Mech never changed the file; the new version can replace it
    merge     the Mech changed the file too; the two changes must be combined
    add       a new file
    clash     a new file, at a path where the Mech already has a different one
    remove    the template dropped the file, and the Mech never changed it
    edited    the template dropped the file, but the Mech changed it
    deleted   the template changed a file the Mech had deleted

An answer changed with --data is rendered only at the end, as one more update
named `answers`, which apply always takes.

It also lists new Copier questions, with the defaults they would take, and the
upgrade notes (mechmaker's `upgrade-notes.yml`) added since: changes a Mech
must act on beyond taking files, such as records to migrate.

`apply` needs a clean git tree. It runs `copier update` to the same target,
then puts back every file that only declined updates touched. A file touched by
both an accepted and a declined update is left updated and listed: keep only
the accepted part by hand. Copier writes conflict markers where a merge did not
resolve; the report lists those files. `_commit` moves to the target either way,
so a declined update counts as a local change and is not offered again.

Exit 0 when the Mech is up to date (check, plan) or the update ran (apply),
1 when updates are waiting (check, plan) or apply left conflicts to resolve,
2 when the folder is not a Mech or the template cannot be read, 64 on a usage
error.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

ANSWERS = ".copier-answers.yml"
NOTES = "upgrade-notes.yml"
# Paths in the template repository whose changes can reach a Mech.
TEMPLATE_PATHS = ["template", "copier.yml", NOTES]
# And a Fleet's Coordinator (kind: coordinator), which also links to the shared
# schema modules, the license and AGENTS.md in template/.
COORDINATOR_PATHS = ["coordinator", "template/src/{{mech_slug}}/schema/mech_shared.yaml",
                     "template/src/{{mech_slug}}/schema/history.yaml", "template/LICENSE.jinja",
                     "template/AGENTS.md", "copier.yml", NOTES]
WORKING_TREE = "working-tree"
# The update that holds the effect of changed answers (--data). It is always taken.
ANSWERS_UPDATE = "answers"
STATUSES = ["take", "merge", "add", "clash", "remove", "edited", "deleted"]
SAFE = {"take", "add", "remove"}


class Failure(Exception):
    """The Mech or the template cannot be read; exit 2."""


@dataclass
class Update:
    id: str
    title: str
    commit: str
    files: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class FileChange:
    path: str
    status: str
    area: str
    updates: list[str] = field(default_factory=list)


@dataclass
class Plan:
    mech: str
    src: str
    base: str
    target: str
    target_commit: str
    updates: list[Update]
    files: list[FileChange]
    questions: dict[str, object]
    dropped_questions: list[str]
    notes: list[dict]
    skipped: list[str]
    uncommitted: bool = False
    # A Fleet member's canon and pin: changed in the template, but the Coordinator's to write.
    coordinator_owned: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- reading


def run(cmd: list[str], cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    # No prompts: a clone that wants a password fails instead of waiting for one.
    out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, stdin=subprocess.DEVNULL,
                         env={**os.environ, "GIT_TERMINAL_PROMPT": "0"})
    if check and out.returncode != 0:
        raise Failure(f"{' '.join(cmd[:3])} ... failed:\n{(out.stderr or out.stdout).strip()}")
    return out


def git(repo: Path, *args: str, check: bool = True) -> str:
    return run(["git", "-C", str(repo), *args], check=check).stdout.strip()


def copier_cmd() -> list[str]:
    if shutil.which("copier"):
        return ["copier"]
    if shutil.which("uvx"):
        return ["uvx", "copier"]
    raise Failure("Copier is not installed: `uv tool install copier`, or install uv for uvx")


def read_answers(mech: Path) -> dict:
    path = mech / ANSWERS
    if not path.is_file():
        raise Failure(f"{mech} has no {ANSWERS}: it was not made with Copier, or the file was removed")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("_src_path", "_commit"):
        if not data.get(key):
            raise Failure(f"{path} has no {key}; Copier cannot tell which template it came from")
    return data


def source_url(src: str) -> str | None:
    """A clonable URL for a Copier source, or None for a local path."""
    for short, host in (("gh:", "https://github.com/"), ("gl:", "https://gitlab.com/")):
        if src.startswith(short):
            return host + src[len(short):].removesuffix(".git") + ".git"
    if re.match(r"^(https?|git|ssh)://|^git@", src):
        return src
    return None


def open_source(src: str, tmp: Path) -> Path:
    """A local git repository holding the template: the checkout itself, or a fresh clone."""
    url = source_url(src)
    if url is None:
        path = Path(src).expanduser()
        if not path.is_absolute():
            raise Failure(f"_src_path is the relative path {src!r}, which `copier update` cannot follow. "
                          "Set it to gh:monarch-initiative/mechmaker or an absolute path, commit, and rerun.")
        if not (path / ".git").exists():
            raise Failure(f"_src_path {src} is not a git checkout")
        return path
    dest = tmp / "template-src"
    run(["git", "clone", "--quiet", url, str(dest)])
    return dest


def latest_tag(repo: Path) -> str | None:
    """The newest release tag, as Copier picks it: the highest version."""
    for tag in git(repo, "tag", "--sort=-v:refname").splitlines():
        if re.fullmatch(r"v?\d+(\.\d+)*", tag):
            return tag
    return None


def resolve(repo: Path, ref: str) -> str:
    out = run(["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], check=False)
    if out.returncode != 0:
        raise Failure(f"{ref!r} is not a commit or tag in the template")
    return out.stdout.strip()


def describe(repo: Path, ref: str) -> str:
    return git(repo, "describe", "--tags", "--always", ref)


def is_ancestor(repo: Path, a: str, b: str) -> bool:
    return run(["git", "-C", str(repo), "merge-base", "--is-ancestor", a, b], check=False).returncode == 0


def endpoints(repo: Path, stored: dict, target: str | None) -> tuple[str, str, str]:
    """(the Mech's commit, the target ref, the target's commit). The target is the latest release
    tag unless named. A Mech already past it is an error, not "up to date": its updates are on main."""
    base = resolve(repo, str(stored["_commit"]))
    ref = target or latest_tag(repo) or "HEAD"
    target_commit = resolve(repo, ref)
    if base != target_commit and is_ancestor(repo, target_commit, base):
        raise Failure(f"The Mech is at {stored['_commit']}, newer than {ref}. "
                      "Use --to HEAD for mechmaker's main branch.")
    return base, ref, target_commit


def template_paths(answers: dict) -> list[str]:
    return COORDINATOR_PATHS if answers.get("kind") == "coordinator" else TEMPLATE_PATHS


def coordinator_owned(answers: dict) -> set[str]:
    """In a Fleet member, the files its Coordinator writes. copier.yml's _skip_if_exists keeps an
    update from replacing them once they exist; keep in step with it."""
    if answers.get("kind", "mech") != "mech" or not answers.get("fleet_name"):
        return set()
    slug = answers.get("mech_slug", "")
    return {"fleet/pin.yaml", f"src/{slug}/schema/mech_shared.yaml", f"src/{slug}/schema/history.yaml"}


def commits_between(repo: Path, base: str, target: str,
                    paths: list[str] | None = None) -> list[tuple[str, str, str]]:
    """(sha, id, title) for each first-parent commit after base that touched the template, oldest first.
    A merged pull request is identified by its number, anything else by its short sha."""
    out = git(repo, "log", "--first-parent", "--reverse", "--format=%H%x00%s%x00%b%x1e",
              f"{base}..{target}", "--", *(paths or TEMPLATE_PATHS))
    found = []
    for entry in filter(None, (e.strip("\n") for e in out.split("\x1e"))):
        sha, subject, body = (entry.split("\x00") + ["", ""])[:3]
        merge = re.match(r"Merge pull request #(\d+)", subject)
        squash = re.search(r"\(#(\d+)\)$", subject)
        if merge:
            title = next((line for line in body.splitlines() if line.strip()), subject)
            found.append((sha, f"#{merge.group(1)}", title.strip()))
        elif squash:
            found.append((sha, f"#{squash.group(1)}", subject[: squash.start()].strip()))
        else:
            found.append((sha, sha[:7], subject))
    return found


def parse_notes(text: str) -> dict[str, dict]:
    """The upgrade notes in TEXT, by id."""
    items = yaml.safe_load(text) or []
    return {str(n["id"]): n for n in items if isinstance(n, dict) and n.get("id")}


def notes_at(repo: Path, ref: str) -> dict[str, dict]:
    out = run(["git", "-C", str(repo), "show", f"{ref}:{NOTES}"], check=False)
    return parse_notes(out.stdout) if out.returncode == 0 else {}


def notes_in_tree(repo: Path) -> dict[str, dict]:
    path = repo / NOTES
    return parse_notes(path.read_text(encoding="utf-8")) if path.is_file() else {}


def applies(note: dict, answers: dict) -> bool:
    """A note is for one kind of repository (`kind:`, a Mech unless it says coordinator). With
    `when: <answer>`, it applies only where that answer is set and not false or empty."""
    if note.get("kind", "mech") != answers.get("kind", "mech"):
        return False
    when = note.get("when")
    return not when or bool(answers.get(str(when)))


# ---------------------------------------------------------------- rendering


@contextmanager
def answers_file(data: dict) -> Iterator[str]:
    """DATA in a temporary YAML file, for Copier's --data-file."""
    with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False, encoding="utf-8") as fh:
        yaml.safe_dump(data, fh)
    try:
        yield fh.name
    finally:
        Path(fh.name).unlink()


def render(repo: Path, ref: str, data: dict, dest: Path) -> Path:
    """The Mech's answers rendered with the template at REF ("HEAD" on a checkout: its working tree)."""
    with answers_file(data) as path:
        run([*copier_cmd(), "copy", "--quiet", "--defaults", "--overwrite", "--vcs-ref", ref,
             "--data-file", path, str(repo), str(dest)])
    return dest


def tree(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file() and p.relative_to(root).parts[0] != ".git"}


def area(path: str, slug: str) -> str:
    """Which part of a Mech a rendered path belongs to, for grouping a choice."""
    schema = f"src/{slug}/schema/"
    if path in (f"{schema}mech_shared.yaml", f"{schema}history.yaml"):
        return "shared schema"
    if path.startswith(schema):
        return "data model"
    if (path.startswith(f"src/{slug}/templates/") or path in (
            f"src/{slug}/render.py", f"src/{slug}/site.py", f"src/{slug}/docs.py",
            "mkdocs.yml", "conf/site.yaml")):
        return "site and browser"
    if path.startswith(".github/"):
        return "workflows"
    if path.startswith(".claude/") or path in ("CLAUDE.md", "AGENTS.md"):
        return "agent guidance"
    if path.startswith("docs/") or path.endswith(".md") and "/" not in path:
        return "documentation"
    if path.startswith("tests/"):
        return "tests"
    if path in ("pyproject.toml", "uv.lock"):
        return "dependencies"
    if path.startswith(("src/", "conf/")) or path == "justfile":
        return "tools"
    return "other"


def status(path: str, before: dict[str, bytes], after: dict[str, bytes], mech: Path) -> str | None:
    """How a file the template changed stands in the Mech; None when nothing needs doing."""
    here = mech / path
    mine = here.read_bytes() if here.is_file() else None
    old, new = before.get(path), after.get(path)
    if mine == new:
        return None
    if old is None:
        return "add" if mine is None else "clash"
    if new is None:
        return None if mine is None else ("remove" if mine == old else "edited")
    if mine is None:
        return "deleted"
    return "take" if mine == old else "merge"


def make_plan(mech: Path, target: str | None, data: dict, tmp: Path) -> Plan:
    stored = read_answers(mech)
    # The past is rendered with the answers the Mech was made with; --data enters only at the end.
    answers = {k: v for k, v in stored.items() if not k.startswith("_")}
    slug = str(answers.get("mech_slug", ""))
    src = str(stored["_src_path"])
    repo = open_source(src, tmp)
    base, ref, target_commit = endpoints(repo, stored, target)
    # HEAD on a local checkout renders its working tree, which may differ from the commit.
    local_head = ref == "HEAD" and source_url(src) is None
    # Copier renders a dirty checkout's working tree, untracked files included, as a temporary commit.
    uncommitted = local_head and bool(git(repo, "status", "--porcelain"))
    if data:  # typed in place: apply passes the same answers to Copier
        if local_head:
            spec = (repo / "copier.yml").read_text()
        else:
            spec = git(repo, "show", f"{target_commit}:copier.yml")
        type_data(data, yaml.safe_load(spec) or {})

    steps = commits_between(repo, base, target_commit, template_paths(stored))
    if uncommitted:
        steps.append(("HEAD", WORKING_TREE, "Uncommitted changes in the template checkout"))
    changed = [k for k in data if k not in answers or answers[k] != data[k]]
    if changed:
        title = "Changed answers: " + ", ".join(f"{k}={json.dumps(data[k])}" for k in changed)
        steps.append(("HEAD" if uncommitted else target_commit, ANSWERS_UPDATE, title))

    def render_at(job: tuple[int, str, bool]) -> tuple[dict[str, bytes], dict, dict] | Failure:
        """One version's files, the answers Copier writes there, and its upgrade notes; or the failure."""
        i, r, with_data = job
        try:
            files = tree(render(repo, r, answers | data if with_data else answers, tmp / f"render{i}"))
        except Failure as err:
            return err
        written = yaml.safe_load(files.pop(ANSWERS, b"")) or {}
        return files, written, notes_in_tree(repo) if r == "HEAD" else notes_at(repo, r)

    # The renders do not depend on each other: each reads one commit and writes its own folder, and
    # Copier clones the template for each. Run them together; read the results in order below.
    jobs = [(0, base, False)] + [(i + 1, sha, uid == ANSWERS_UPDATE) for i, (sha, uid, _) in enumerate(steps)]
    with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 1)) as pool:
        rendered = list(pool.map(render_at, jobs))

    first = rendered[0]
    if isinstance(first, Failure):
        raise Failure(f"The template at the Mech's _commit ({stored['_commit']}) does not render with its "
                      f"answers, so there is nothing to compare against.\n{first}") from first
    start, final_answers, base_notes = first
    known_notes = set(base_notes)
    updates: list[Update] = []
    touched: dict[str, list[str]] = {}
    note_owner: dict[str, str] = {}
    skipped: list[str] = []
    pending: list[tuple[str, str]] = []
    prev = start
    for i, ((sha, uid, title), result) in enumerate(zip(steps, rendered[1:], strict=True)):
        if isinstance(result, Failure):
            if i == len(steps) - 1:
                raise result
            # This commit does not render with today's answers; its changes join the next one's.
            skipped.append(uid)
            pending.append((uid, title))
            continue
        now, final_answers, step_notes = result
        update = Update(id=" + ".join([u for u, _ in pending] + [uid]),
                        title="; ".join([t for _, t in pending] + [title]), commit=sha)
        pending = []
        for path in sorted(set(prev) | set(now)):
            if prev.get(path) != now.get(path):
                update.files.append(path)
                touched.setdefault(path, []).append(update.id)
        for nid in step_notes:
            if nid not in known_notes and nid not in note_owner:
                note_owner[nid] = update.id
        updates.append(update)
        prev = now

    files = []
    owned = []
    for path, ids in touched.items():
        # A change undone later in the range is no change: the template's file ends as it began.
        if start.get(path) == prev.get(path):
            continue
        if path in coordinator_owned(stored) and (mech / path).exists():
            owned.append(path)
            continue
        st = status(path, start, prev, mech)
        if st:
            files.append(FileChange(path, st, area(path, slug), ids))
    files.sort(key=lambda f: (STATUSES.index(f.status), f.path))
    live = {f.path for f in files}
    for update in updates:
        update.files = [p for p in update.files if p in live]

    questions = {k: v for k, v in final_answers.items() if not k.startswith("_") and k not in stored}
    dropped = sorted(k for k in stored if not k.startswith("_") and k not in final_answers)
    # A note naming its pull request applies when that pull request is in this range: a note
    # written after the change it describes still reaches only the Mechs that lack the change.
    # A note without one applies when it is new since the Mech's commit.
    owner_of = {part: u.id for u in updates for part in u.id.split(" + ")}
    in_range = {uid for _, uid, _ in steps}
    last_notes = notes_in_tree(repo) if uncommitted else notes_at(repo, target_commit)
    notes = []
    for nid, note in last_notes.items():
        pr = f"#{note['pr']}" if note.get("pr") else None
        if (pr not in in_range) if pr else (nid in known_notes):
            continue
        # The answers the Mech will have: new questions at their defaults, and --data.
        if applies(note, final_answers):
            notes.append({**note, "update": owner_of.get(pr, "") if pr else note_owner.get(nid, "")})
    for update in updates:
        update.notes = [n["id"] for n in notes if n["update"] == update.id]
    updates = [u for u in updates if u.files or u.notes]
    shown = describe(repo, target_commit) + (" + uncommitted changes" if uncommitted else "")
    return Plan(mech=str(mech), src=src, base=str(stored["_commit"]), target=ref, target_commit=shown,
                updates=updates, files=files, questions=questions, dropped_questions=dropped,
                notes=notes, skipped=skipped, uncommitted=uncommitted, coordinator_owned=sorted(owned))


# ---------------------------------------------------------------- reporting

MEANING = {
    "take": "the Mech never changed it: the new version replaces it",
    "merge": "the Mech changed it too: the two changes must be combined",
    "add": "a new file",
    "clash": "a new file where the Mech already has a different one",
    "remove": "the template dropped it, and the Mech never changed it",
    "edited": "the template dropped it, but the Mech changed it",
    "deleted": "the Mech had deleted it, and the template changed it",
}


def plan_text(plan: Plan) -> str:
    name = Path(plan.mech).name
    if not plan.updates and not plan.questions:
        return f"{name} is up to date with mechmaker {plan.target_commit} (it is at {plan.base}).\n"
    by_path = {f.path: f for f in plan.files}
    head = f"# {name}: {len(plan.updates)} update(s) from mechmaker, {plan.base} -> {plan.target_commit}"
    lines = [head, ""]
    for update in plan.updates:
        lines += [f"## {update.id}  {update.title}", ""]
        for path in update.files:
            f = by_path[path]
            also = [u for u in f.updates if u != update.id]
            shared = f"  (also {', '.join(also)})" if also else ""
            lines.append(f"    {f.status:<8}{path}  [{f.area}]{shared}")
        for nid in update.notes:
            note = next((n for n in plan.notes if str(n["id"]) == nid), None)
            if note:
                lines.append(f"    note    {nid}: {note.get('summary', '').strip()}")
        lines.append("")
    if plan.questions:
        lines += ["## New questions, at their defaults", ""]
        lines += [f"    {k}: {json.dumps(v)}" for k, v in plan.questions.items()]
        lines += ["", "Give another answer with --data KEY=VALUE on apply.", ""]
    if plan.dropped_questions:
        lines += [f"Questions the template no longer asks: {', '.join(plan.dropped_questions)}", ""]
    if plan.notes:
        lines += ["## Upgrade notes: act on these beyond taking files", ""]
        for note in plan.notes:
            owner = note.get("update") or "no update"
            lines.append(f"- {note['id']} ({owner}): {note.get('summary', '').strip()}")
            lines += [f"    {line}" for line in str(note.get("action", "")).strip().splitlines()]
        lines.append("")
    counts = {s: sum(1 for f in plan.files if f.status == s) for s in STATUSES}
    lines += ["## Files", ""]
    lines += [f"    {counts[s]:>3} {s:<8}{MEANING[s]}" for s in STATUSES if counts[s]]
    if plan.coordinator_owned:
        lines += ["", "Left alone: the Fleet's Coordinator writes these (its change-canon skill), "
                      f"and the update keeps this Mech's copies: {', '.join(plan.coordinator_owned)}"]
    if plan.skipped:
        lines += ["", f"Did not render alone with these answers, so folded into the next update: "
                      f"{', '.join(plan.skipped)}"]
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------- applying


def chosen(plan: Plan, accept: list[str] | None, decline: list[str] | None) -> set[str]:
    """The ids of the accepted updates. An id names a pull request (#65), a commit, or a combined update."""
    def match(token: str) -> list[str]:
        token = token.strip()
        return [u.id for u in plan.updates
                if any(part == token or (len(token) >= 7 and part.startswith(token))
                       for part in [u.id, u.commit, *u.id.split(" + ")])]
    named = accept if accept is not None else decline or []
    unknown = [t for t in named if not match(t)]
    if unknown:
        raise ValueError(f"no update named {', '.join(unknown)}; "
                         f"the updates are {', '.join(u.id for u in plan.updates) or 'none'}")
    picked = {uid for t in named for uid in match(t)}
    every = {u.id for u in plan.updates}
    taken = picked if accept is not None else every - picked
    # The answers the person gave are not an update to decline: to undo one, drop its --data.
    return taken | ({ANSWERS_UPDATE} & every)


def restore(mech: Path, path: str) -> None:
    """Put PATH back as it was at the Mech's last commit, or remove it if it is new. `HEAD:./` reads
    PATH from the Mech's folder, which need not be the top of its repository."""
    if run(["git", "-C", str(mech), "cat-file", "-e", f"HEAD:./{path}"], check=False).returncode == 0:
        git(mech, "checkout", "HEAD", "--", path)
    elif (mech / path).is_file():
        (mech / path).unlink()


def require_clean(mech: Path) -> None:
    # Only the Mech's own folder counts: it may sit in a larger repository.
    if git(mech, "status", "--porcelain", "--", "."):
        raise Failure(f"{mech} has uncommitted changes. Commit or stash them first: "
                      "the update must be a diff you can read and undo.")


def apply(mech: Path, plan: Plan, accepted: set[str], data: dict,
          keep: list[str] | None = None) -> tuple[dict, int]:
    require_clean(mech)
    if plan.uncommitted:
        raise Failure("The template checkout has uncommitted changes. Copier would record a temporary "
                      "commit as the Mech's _commit, and the next sync could not find it. Commit them "
                      "in the template first.")
    cmd = [*copier_cmd(), "update", "--quiet", "--skip-answered", "--defaults", "--conflict", "inline",
           "--vcs-ref", plan.target]
    with answers_file(data) as path:
        run([*cmd, *(["--data-file", path] if data else []), str(mech)])

    def held(path: str) -> bool:
        return any(fnmatch.fnmatch(path, pattern) for pattern in keep or [])

    restored, partial, kept = [], {}, []
    for f in plan.files:
        took = [u for u in f.updates if u in accepted]
        if not took or held(f.path):
            restore(mech, f.path)
            restored.append(f.path)
        elif len(took) < len(f.updates):
            partial[f.path] = {"keep": took, "undo": [u for u in f.updates if u not in accepted]}
        else:
            kept.append(f.path)
    # A file Copier left outside the plan stays, and is listed.
    # Paths relative to the Mech's folder, as the plan has them.
    changed = git(mech, "diff", "--name-only", "--relative", "HEAD").splitlines()
    changed += git(mech, "ls-files", "--others", "--exclude-standard").splitlines()
    changed = sorted(set(changed) - {ANSWERS})
    for path in [p for p in changed if held(p) and p not in restored]:
        restore(mech, path)
        restored.append(path)
    changed = [p for p in changed if p not in restored]
    conflicts = [p for p in changed if (mech / p).is_file() and _has_markers(mech / p)]
    planned = {f.path for f in plan.files}
    result = {
        "target": plan.target_commit,
        "accepted": sorted(accepted),
        "declined": sorted({u.id for u in plan.updates} - accepted),
        "kept": kept,
        "restored": restored,
        "partial": partial,
        "conflicts": conflicts,
        "unplanned": [p for p in changed if p not in planned],
        "notes": [n for n in plan.notes if n.get("update") in accepted or not n.get("update")],
        "questions": {k: data.get(k, v) for k, v in plan.questions.items()},
    }
    return result, 1 if conflicts or partial else 0


def _has_markers(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return bool(re.search(r"(?m)^<<<<<<< ", text)) and bool(re.search(r"(?m)^>>>>>>> ", text))


def apply_text(result: dict) -> str:
    lines = [f"Updated to mechmaker {result['target']}.",
             f"Accepted: {', '.join(result['accepted']) or 'none'}",
             f"Declined: {', '.join(result['declined']) or 'none'}", ""]
    if result["conflicts"]:
        lines += ["Conflict markers to resolve:"] + [f"    {p}" for p in result["conflicts"]] + [""]
    if result["partial"]:
        lines.append("Touched by accepted and declined updates; keep only the accepted part:")
        lines += [f"    {p}  keep {', '.join(v['keep'])}; undo {', '.join(v['undo'])}"
                  for p, v in result["partial"].items()]
        lines.append("")
    if result["restored"]:
        lines += [f"Put back, declined: {len(result['restored'])} file(s)"]
    if result["unplanned"]:
        lines += ["Changed by Copier outside the plan; look at these:"] + \
                 [f"    {p}" for p in result["unplanned"]]
    if result["questions"]:
        lines += ["New answers:"] + [f"    {k}: {json.dumps(v)}" for k, v in result["questions"].items()]
    if result["notes"]:
        lines += ["", "Upgrade notes for the accepted updates:"]
        for note in result["notes"]:
            lines.append(f"- {note['id']}: {note.get('summary', '').strip()}")
            lines += [f"    {line}" for line in str(note.get("action", "")).strip().splitlines()]
    lines += ["", "Next: resolve what is listed, then `just install` and `just qc` in the Mech."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- command line


def parse_data(items: list[str]) -> dict:
    """KEY=VALUE pairs, the values as written; type_data reads them once the questions are known."""
    data = {}
    for item in items:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise ValueError(f"--data takes KEY=VALUE, not {item!r}")
        data[key] = value
    return data


class UsageError(ValueError):
    pass


def type_data(data: dict, questions: dict) -> None:
    """Check each --data key is a question of the target template, and read a value as YAML
    unless its question takes one piece of text, so `description=Goats: origin and use` stays a sentence."""
    unknown = sorted(k for k in data if k.startswith("_") or not isinstance(questions.get(k), dict))
    if unknown:
        raise UsageError(f"--data names no question of the target template: {', '.join(unknown)}")
    for key, value in data.items():
        q = questions[key]
        if (q.get("type", "str") == "str" and not q.get("multiselect")) or value == "":
            continue
        try:
            data[key] = yaml.safe_load(value)
        except yaml.YAMLError as err:
            raise UsageError(f"--data {key}: not valid YAML: {err}") from err


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "plan", "apply"):
        p = sub.add_parser(name)
        p.add_argument("mech", type=Path, help="the Mech's folder")
        p.add_argument("--to", metavar="REF", help="template tag or commit to compare against "
                       "(default: the latest release tag; HEAD for main)")
        p.add_argument("--json", action="store_true", help="print JSON")
        if name != "check":
            p.add_argument("--data", action="append", default=[], metavar="KEY=VALUE",
                           help="an answer for a new or changed question (repeatable)")
        if name == "apply":
            group = p.add_mutually_exclusive_group(required=True)
            group.add_argument("--accept", nargs="+", metavar="ID", help="take only these updates")
            group.add_argument("--decline", nargs="+", metavar="ID", help="take all but these updates")
            group.add_argument("--all", action="store_true", help="take every update")
            p.add_argument("--keep", nargs="+", default=[], metavar="GLOB",
                           help="leave files matching these paths as they are, whichever update "
                                "changes them (e.g. 'src/*/templates/*')")
    args = parser.parse_args(argv)
    mech = args.mech.resolve()
    try:
        data = parse_data(getattr(args, "data", []))
    except ValueError as err:
        parser.error(str(err))
    try:
        with tempfile.TemporaryDirectory() as tmp:
            if args.command == "check":
                return check(mech, args.to, args.json, Path(tmp))
            if args.command == "apply":
                read_answers(mech)  # "not a Mech" before any git message
                require_clean(mech)  # before the plan's renders, not after
            try:
                plan = make_plan(mech, args.to, data, Path(tmp))
            except UsageError as err:
                print(err, file=sys.stderr)
                return 64
            if args.command == "plan":
                print(json.dumps(plan.to_dict(), indent=2) if args.json else plan_text(plan), end="")
                return 1 if plan.updates or plan.questions else 0
            try:
                # --all names nothing to decline, so chosen() takes every update.
                accepted = chosen(plan, args.accept, args.decline)
            except ValueError as err:
                print(err, file=sys.stderr)
                return 64
            result, code = apply(mech, plan, accepted, data, args.keep)
            print(json.dumps(result, indent=2) if args.json else apply_text(result), end="")
            return code
    except Failure as err:
        print(err, file=sys.stderr)
        return 2


def check(mech: Path, target: str | None, as_json: bool, tmp: Path) -> int:
    """How far behind the Mech is, from the template's history alone. Some listed updates may not
    reach this Mech (a workflow it does not use); `plan` renders and knows."""
    stored = read_answers(mech)
    repo = open_source(str(stored["_src_path"]), tmp)
    base, ref, target_commit = endpoints(repo, stored, target)
    steps = commits_between(repo, base, target_commit, template_paths(stored))
    out = {"base": str(stored["_commit"]), "target": describe(repo, ref),
           "updates": [{"id": uid, "title": title} for _, uid, title in steps]}
    if as_json:
        print(json.dumps(out, indent=2))
    elif not steps:
        print(f"Up to date with mechmaker {out['target']} (at {out['base']}).")
    else:
        print(f"{len(steps)} template change(s) between {out['base']} and {out['target']}:")
        print("".join(f"    {u['id']}  {u['title']}\n" for u in out["updates"]), end="")
        print("Run `plan` to see which reach this Mech.")
    return 1 if steps else 0


if __name__ == "__main__":
    sys.exit(main())
