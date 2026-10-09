"""The canon: the files every member carries byte for byte, and the pins that say which version.

canon/manifest.yaml lists each artifact, its source here, its target in a
member, and the source's sha256. A member holds a copy of each artifact and
fleet/pin.yaml, which names the Coordinator commit it was synced from (`ref`,
a full 40-character commit, never a branch or tag) and the sha256 of each copy.

    canon-check   the sources here match the manifest
    sync          copy the canon at one commit (default origin/main) into a member
                  checkout; a dry run unless --apply. The commit must be on the
                  Coordinator's origin/main, where the member's own check can fetch it
    audit         every checked member: pinned to one commit, the same commit,
                  one of this Coordinator's, with files that match it
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

from .manifest import Fleet, Member
from .members import git, identity_errors, inside, readable
from .paths import CANON_MANIFEST, PIN_FILE

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class CanonError(Exception):
    """The canon, a ref, or a member refuses a sync."""


@dataclass(frozen=True)
class Artifact:
    id: str
    source: str
    target: str
    sha256: str

    def target_for(self, member: Member) -> str:
        return self.target.format(package_path=member.package_path)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_manifest(text: str) -> list[Artifact]:
    data = yaml.safe_load(text) or {}
    arts = [Artifact(a["id"], a["source"], a["target"], str(a["sha256"]))
            for a in data.get("artifacts") or []]
    ids = [a.id for a in arts]
    if len(set(ids)) != len(ids):
        raise CanonError(f"{CANON_MANIFEST}: an artifact id appears twice")
    return arts


def load_manifest(root: Path, rev: str | None = None) -> list[Artifact]:
    """The manifest in the working tree, or at a commit."""
    if rev is None:
        return _parse_manifest((root / CANON_MANIFEST).read_text())
    return _parse_manifest(git(root, "show", f"{rev}:{CANON_MANIFEST}"))


def read_source(root: Path, art: Artifact, rev: str | None = None) -> bytes:
    if rev is None:
        return (root / art.source).read_bytes()
    return subprocess.run(["git", "show", f"{rev}:{art.source}"], cwd=root, capture_output=True,
                          check=True).stdout


def canon_errors(root: Path) -> list[str]:
    errors = []
    for art in load_manifest(root):
        path = root / art.source
        if not path.exists():
            errors.append(f"{art.id}: {art.source} does not exist")
        elif sha256(path.read_bytes()) != art.sha256:
            errors.append(f"{art.id}: {art.source} does not match its sha256 in {CANON_MANIFEST}. "
                          "If the change is meant, run `just canon-refresh` and release it (change-canon).")
    return errors


def refresh(root: Path) -> list[str]:
    """Rewrite each sha256 in the manifest from its source, keeping the comments. Returns the ids changed."""
    path = root / CANON_MANIFEST
    text = path.read_text()
    changed = []
    for art in load_manifest(root):
        new = sha256((root / art.source).read_bytes())
        if new == art.sha256:
            continue
        block = re.compile(rf"(- id: {re.escape(art.id)}\n(?:[ \t]+\S.*\n)*?[ \t]+sha256: )([0-9a-f]+)")
        text, n = block.subn(lambda m, new=new: m.group(1) + new, text, count=1)
        if n != 1:
            raise CanonError(f"could not find the sha256 line of {art.id} in {CANON_MANIFEST}")
        changed.append(art.id)
    if changed:
        path.write_text(text)
    return changed


def resolve(root: Path, ref: str) -> str:
    sha = git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    if not sha:
        raise CanonError(f"{ref} is not a commit of this Coordinator")
    return sha


def _ok(root: Path, *args: str) -> bool:
    return subprocess.run(["git", *args], cwd=root, capture_output=True).returncode == 0


def is_commit(root: Path, sha: str) -> bool:
    return _ok(root, "cat-file", "-e", f"{sha}^{{commit}}")


def is_ancestor(root: Path, a: str, b: str) -> bool:
    return _ok(root, "merge-base", "--is-ancestor", a, b)


def published_main(root: Path) -> bool:
    return _ok(root, "rev-parse", "--verify", "--quiet", "refs/remotes/origin/main")


def published(root: Path, sha: str) -> bool:
    """Is the commit on origin/main, where members' own checks fetch the canon from?"""
    return published_main(root) and is_ancestor(root, sha, "origin/main")


def pin_text(fleet: Fleet, member: Member, sha: str, arts: list[Artifact], data: dict[str, bytes]) -> str:
    lines = [
        f"# Written by {fleet.name}'s Coordinator (`fleet sync {member.id}`). Do not edit it by hand:",
        "# `just check-fleet` compares these files with the Coordinator at `ref`.",
        f"coordinator: {fleet.coordinator}",
        f'ref: "{sha}"',
        "artifacts:",
    ]
    for art in arts:
        lines += [f"  - id: {art.id}", f"    target: {art.target_for(member)}",
                  f"    sha256: {sha256(data[art.id])}"]
    return "\n".join(lines) + "\n"


def read_pin(mroot: Path) -> dict | None:
    path = mroot / PIN_FILE
    if not path.exists():
        return None
    if not readable(mroot, path):
        raise CanonError(f"{PIN_FILE} in {mroot} is not a file in that checkout")
    data = yaml.safe_load(path.read_text())
    return data if isinstance(data, dict) else {}


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def sync(root: Path, fleet: Fleet, member: Member, mroot: Path, ref: str | None = None,
         apply: bool = False, unpublished: bool = False) -> list[str]:
    """Plan, and with apply write, the canon at ref into a member checkout. Returns the plan.

    ref defaults to origin/main, the published canon; with unpublished, to HEAD."""
    errors = identity_errors(member, mroot)
    if errors:
        raise CanonError("\n".join(errors))
    if ref is None and not unpublished and not published_main(root):
        raise CanonError("this Coordinator has no origin/main. Push it to GitHub first: a member's "
                         "`just check-fleet` reads the canon from there. (--unpublished syncs HEAD, "
                         "for a local trial.)")
    sha = resolve(root, ref or ("HEAD" if unpublished else "origin/main"))
    if not unpublished and not published(root, sha):
        raise CanonError(f"{sha[:12]} is not on this Coordinator's origin/main. Merge and push it first: "
                         "a member's `just check-fleet` reads the canon from GitHub. "
                         "(--unpublished writes it anyway, for a local trial.)")
    arts = load_manifest(root, sha)
    data = {a.id: read_source(root, a, sha) for a in arts}
    bad = [a.id for a in arts if sha256(data[a.id]) != a.sha256]
    if bad:
        raise CanonError(f"at {sha[:12]} the manifest's sha256 does not match {', '.join(bad)}")
    plan = []
    writes: list[tuple[Path, bytes]] = []
    outside = [str(p) for p in [mroot / a.target_for(member) for a in arts] + [mroot / PIN_FILE]
               if not inside(mroot, p) or (p.exists() and not p.is_file())]
    if outside:
        raise CanonError(f"{member.id}: will not write {', '.join(outside)}: not a file within {mroot}. "
                         "Check its package_path in fleet.yaml, and the checkout for symlinks.")
    for art in arts:
        target = mroot / art.target_for(member)
        same = target.exists() and target.read_bytes() == data[art.id]
        plan.append(f"{'UNCHANGED' if same else 'WOULD WRITE':<11}  {art.target_for(member)}  ({art.id})")
        if not same:
            writes.append((target, data[art.id]))
    pin = pin_text(fleet, member, sha, arts, data).encode()
    pin_path = mroot / PIN_FILE
    same = pin_path.exists() and pin_path.read_bytes() == pin
    plan.append(f"{'UNCHANGED' if same else 'WOULD WRITE':<11}  {PIN_FILE}  (ref {sha[:12]})")
    if not same:
        writes.append((pin_path, pin))
    if apply:
        for path, content in writes:
            _write_atomic(path, content)
        plan = [line.replace("WOULD WRITE", "WROTE      ", 1) for line in plan]
    return plan


def audit(root: Path, fleet: Fleet, roots: dict[str, Path]) -> tuple[list[str], list[str]]:
    """Errors and warnings for the canon across every checked member. roots maps member id to its checkout."""
    errors, warnings = [], []
    refs: dict[str, list[str]] = {}
    head = git(root, "rev-parse", "HEAD", check=False)
    manifests: dict[str, list[Artifact] | None] = {}
    for member in fleet.checked():
        if member.id not in roots:
            continue
        who, mroot = member.id, roots[member.id]
        ident = identity_errors(member, mroot)
        if ident:
            errors += [f"{who}: {e}" for e in ident]
            continue
        try:
            pin = read_pin(mroot)
        except CanonError as exc:
            errors.append(f"{who}: {exc}")
            continue
        if pin is None:
            errors.append(f"{who}: no {PIN_FILE}. Run `fleet sync {who} --root <its checkout>`.")
            continue
        if str(pin.get("coordinator", "")).lower() != fleet.coordinator.lower():
            errors.append(f"{who}: {PIN_FILE} names coordinator {pin.get('coordinator')!r}, "
                          f"not {fleet.coordinator}")
        sha = str(pin.get("ref") or "")
        if not FULL_SHA.match(sha):
            errors.append(f"{who}: {PIN_FILE} ref {sha!r} is not a full commit. Run `fleet sync {who}`.")
            continue
        refs.setdefault(sha, []).append(who)
        if sha not in manifests:
            manifests[sha] = load_manifest(root, sha) if is_commit(root, sha) else None
        arts = manifests[sha]
        if arts is None:
            errors.append(f"{who}: pinned to {sha[:12]}, which is not a commit of this Coordinator")
            continue
        pinned = {a.get("id"): a for a in pin.get("artifacts") or [] if isinstance(a, dict)}
        for art in arts:
            target = mroot / art.target_for(member)
            if not target.exists():
                errors.append(f"{who}: {art.target_for(member)} is missing")
                continue
            if not readable(mroot, target):
                errors.append(f"{who}: {art.target_for(member)} is not a file within the checkout")
                continue
            got = sha256(target.read_bytes())
            if got != art.sha256:
                errors.append(f"{who}: {art.target_for(member)} differs from the canon at {sha[:12]}")
            if (pinned.get(art.id) or {}).get("sha256") != art.sha256:
                errors.append(f"{who}: {PIN_FILE} records the wrong sha256 for {art.id}")
        if head and not is_ancestor(root, sha, head):
            errors.append(f"{who}: pinned to {sha[:12]}, which is not in this Coordinator's history")
    if len(refs) > 1:
        spread = "; ".join(f"{sha[:12]}: {', '.join(who)}" for sha, who in refs.items())
        errors.append(f"members are pinned to {len(refs)} different commits ({spread}). Sync them to one.")
    elif refs and head:
        sha = next(iter(refs))
        if sha != head and load_manifest(root, sha) != load_manifest(root, head):
            warnings.append(f"the canon changed after {sha[:12]}, the members' pin. Sync every member.")
    return errors, warnings

