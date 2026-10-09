"""Members' repositories: where each one is, fetching them, and reading them.

The audits read members from cache/members/<id>, a clone `just fetch` makes
and refreshes. The clones are anonymous and read-only: nothing here pushes to
a member, and nothing needs a token for a public one. `--root id=PATH` points
a command at a local checkout instead, such as one with unpushed work.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from pathlib import Path

import yaml

from .manifest import Fleet, Member
from .paths import ANSWERS_FILE, MEMBERS_CACHE


class MemberError(Exception):
    """A member's repository is missing or is not the one fleet.yaml names."""


def git(cwd: Path, *args: str, check: bool = True) -> str:
    out = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and out.returncode != 0:
        raise MemberError(f"git {' '.join(args)} in {cwd}: {out.stderr.strip()}")
    return out.stdout.strip() if out.returncode == 0 else ""


def parse_roots(pairs: list[str] | None) -> dict[str, Path]:
    roots = {}
    for pair in pairs or []:
        key, sep, path = pair.partition("=")
        if not sep or not key or not path:
            raise SystemExit(f"--root takes id=PATH, not {pair!r}")
        roots[key] = Path(path).expanduser().resolve()
    return roots


def member_root(root: Path, member: Member, overrides: dict[str, Path]) -> Path:
    return overrides.get(member.id) or root / MEMBERS_CACHE / member.id


def clone_url(member: Member) -> str:
    return f"https://github.com/{member.github}.git"


def fetch(fleet: Fleet, root: Path, only: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Clone or refresh each fetched member under cache/members/. Returns a line per member fetched,
    and an error per member that could not be: one failure does not stop the rest."""
    lines, errors = [], []
    for m in fleet.fetched():
        if only and m.id not in only:
            continue
        try:
            lines.append(_fetch_one(m, root / MEMBERS_CACHE / m.id, root))
        except MemberError as exc:
            errors.append(f"{m.id}: could not fetch {m.github}: {exc}")
    return lines, errors


def _fetch_one(m: Member, dest: Path, root: Path) -> str:
    if (dest / ".git").exists():
        # fleet.yaml may have moved the member to another repository since the clone.
        if not same_repository(git(dest, "remote", "get-url", "origin", check=False), m.github):
            git(dest, "remote", "set-url", "origin", clone_url(m))
        git(dest, "fetch", "--quiet", "--prune", "origin")
        git(dest, "remote", "set-head", "origin", "--auto", check=False)
        head = git(dest, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
        git(dest, "reset", "--quiet", "--hard", head or "origin/main")
        return f"{m.id}: updated to {git(dest, 'rev-parse', '--short', 'HEAD')}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    # A full clone: links pin a member's commit, and checking one reads
    # every record at that commit. A blobless clone would fetch each
    # record file in a request of its own.
    git(root, "clone", "--quiet", clone_url(m), str(dest))
    return f"{m.id}: cloned at {git(dest, 'rev-parse', '--short', 'HEAD')}"


def inside(mroot: Path, path: Path) -> bool:
    """Is path within mroot once symlinks are followed? Anyone can push a symlink to a member's
    repository: one could aim a sync's write at a file elsewhere, or the audit's read at /dev/zero."""
    return path.resolve().is_relative_to(mroot.resolve())


def readable(mroot: Path, path: Path) -> bool:
    """A regular file within mroot."""
    return path.is_file() and inside(mroot, path)


def read_answers(mroot: Path) -> dict:
    path = mroot / ANSWERS_FILE
    if not readable(mroot, path):
        return {}
    data = yaml.safe_load(path.read_text())
    return data if isinstance(data, dict) else {}


def same_repository(url: str, github: str) -> bool:
    """Does a git remote URL name the GitHub owner/repo? Any of the usual URL forms."""
    url = url.strip().removesuffix("/").removesuffix(".git").lower()
    for prefix in ("https://github.com/", "http://github.com/", "git@github.com:", "ssh://git@github.com/"):
        if url.startswith(prefix):
            return url[len(prefix):] == github.lower()
    return False


def identity_errors(member: Member, mroot: Path) -> list[str]:
    """Is mroot this member's repository? Its answers must name the member, and its origin, if any, too."""
    if not (mroot / ".git").exists():
        return [f"{mroot} is not a git checkout. Run `just fetch`, or pass --root {member.id}=PATH."]
    errors = []
    slug = read_answers(mroot).get("mech_slug")
    if slug != member.id:
        errors.append(f"{mroot}: its .copier-answers.yml names mech_slug {slug!r}, not {member.id!r}")
    origin = git(mroot, "remote", "get-url", "origin", check=False)
    if origin and not same_repository(origin, member.github):
        errors.append(f"{mroot}: origin is {origin}, not {member.github}")
    return errors


def record_files(mroot: Path, records_dir: str) -> list[Path]:
    base = mroot / records_dir
    if not (base.is_dir() and inside(mroot, base)):
        return []
    return sorted(p for p in base.rglob("*.yaml") if readable(mroot, p))


def iter_records(mroot: Path, records_dir: str) -> Iterator[tuple[str, dict]]:
    for path in record_files(mroot, records_dir):
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            yield str(path.relative_to(mroot)), data


def record_ids(mroot: Path, records_dir: str, rev: str | None = None) -> set[str]:
    """The ids of a member's records, in its working tree or at a commit."""
    if rev is None:
        return {str(d["id"]) for _, d in iter_records(mroot, records_dir) if "id" in d}
    # -z: names as they are. Without it git quotes a name with non-ASCII
    # characters ("b\303\251.yaml"), and cat-file would find no such file.
    names = git(mroot, "ls-tree", "-r", "-z", "--name-only", rev, "--", records_dir).split("\0")
    # cat-file --batch reads one name per line.
    names = [n for n in names if n.endswith(".yaml") and "\n" not in n]
    if not names:
        return set()
    # One git process for every file: `cat-file --batch` reads blobs by name.
    request = "".join(f"{rev}:{n}\n" for n in names)
    out = subprocess.run(["git", "cat-file", "--batch"], cwd=mroot, input=request.encode(),
                         capture_output=True, check=True).stdout
    ids, pos = set(), 0
    while pos < len(out):
        header_end = out.index(b"\n", pos)
        parts = out[pos:header_end].split()
        pos = header_end + 1
        if len(parts) < 3 or parts[1] != b"blob":
            continue
        size = int(parts[2])
        blob, pos = out[pos:pos + size], pos + size + 1
        try:
            data = yaml.safe_load(blob)
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and "id" in data:
            ids.add(str(data["id"]))
    return ids


def is_commit(mroot: Path, rev: str) -> bool:
    return bool(git(mroot, "rev-parse", "--verify", "--quiet", f"{rev}^{{commit}}", check=False))
