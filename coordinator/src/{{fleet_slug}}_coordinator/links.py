"""Check every link between members' records against the relationships fleet.yaml declares.

A link is any object in a record with `corpus` and `identifier`: the shape of
CrossCorpusLink in mech_shared. For each one, in each checked member:

  - `corpus` names a member, and fleet.yaml declares a relationship from this
    member to it through the slot that holds the link;
  - `relation`, and `basis` when the relationship lists bases, are allowed values;
  - `source_version` is a full commit of the target member;
  - the target record exists at that commit, and on the target's main.

A target that existed at the pinned commit and is gone from main is a warning:
the link was right when made and needs a look now. Everything else is an error.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .canon import FULL_SHA
from .manifest import Fleet, Member, Relationship
from .members import is_commit, iter_records, record_ids


@dataclass(frozen=True)
class Finding:
    level: str  # "error" or "warning"
    member: str
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.level.upper()} {self.member} {self.where}: {self.message}"


def find_links(obj: object, key: str = "") -> Iterator[tuple[str, dict]]:
    """Each link in a record, with the name of the slot that holds it."""
    if isinstance(obj, dict):
        if "corpus" in obj and "identifier" in obj:
            yield key, obj
            return
        for k, v in obj.items():
            yield from find_links(v, str(k))
    elif isinstance(obj, list):
        for v in obj:
            yield from find_links(v, key)


def _relationship(fleet: Fleet, member: Member, target: Member, slot: str) -> Relationship | str:
    options = [r for r in fleet.links_from(member.id) if r.object == target.id]
    if not options:
        return f"fleet.yaml declares no relationship from {member.id} to {target.id}"
    match = [r for r in options if r.slot == slot]
    if len(match) == 1:
        return match[0]
    slots = ", ".join(sorted(r.slot for r in options))
    return (f"held in {slot!r}, but links from {member.id} to {target.id} go through "
            f"{'the slot' if len(options) == 1 else 'one of the slots'} {slots}")


class _Ids:
    """Record ids per member and commit, read once."""

    def __init__(self, roots: dict[str, Path], fleet: Fleet):
        self.roots, self.fleet, self.cache = roots, fleet, {}

    def get(self, member: Member, rev: str | None) -> set[str]:
        key = (member.id, rev)
        if key not in self.cache:
            self.cache[key] = record_ids(self.roots[member.id], member.records_dir, rev)
        return self.cache[key]


def check(fleet: Fleet, roots: dict[str, Path]) -> list[Finding]:
    """Findings for every link in every member with a root. roots maps member id to its checkout."""
    findings: list[Finding] = []
    ids = _Ids(roots, fleet)
    for member in fleet.audited():
        if member.id not in roots:
            continue
        for path, record in iter_records(roots[member.id], member.records_dir):
            for slot, link in find_links(record):
                where = f"{path} {slot}"
                for level, message in _check_one(fleet, member, slot, link, roots, ids):
                    findings.append(Finding(level, member.id, where, message))
    return findings


def _check_one(fleet: Fleet, member: Member, slot: str, link: dict, roots: dict[str, Path],
               ids: _Ids) -> list[tuple[str, str]]:
    corpus, identifier = str(link.get("corpus")), str(link.get("identifier"))
    label = f"{corpus} {identifier}"
    target = fleet.by_name(corpus)
    if target is None:
        return [("error", f"{label}: {corpus} is not a member of {fleet.name}")]
    rel = _relationship(fleet, member, target, slot)
    if isinstance(rel, str):
        return [("error", f"{label}: {rel}")]
    out = []
    relation = link.get("relation")
    if relation not in rel.relations:
        out.append(("error", f"{label}: relation {relation!r} is not one of {rel.id}'s "
                             f"({', '.join(rel.relations)})"))
    basis = link.get("basis")
    if rel.bases and basis not in rel.bases:
        out.append(("error", f"{label}: basis {basis!r} is not one of {rel.id}'s ({', '.join(rel.bases)})"))
    if target.status == "planned":
        out.append(("error", f"{label}: {target.id} is planned; it has no records to link to yet"))
        return out
    if target.status == "retired":
        out.append(("warning", f"{label}: {target.id} is retired"))
    if target.id not in roots:
        out.append(("warning", f"{label}: {target.id} was not read, so the target is unchecked"))
        return out
    version = str(link.get("source_version") or "")
    if not FULL_SHA.match(version):
        out.append(("error", f"{label}: source_version must be the full commit of {target.name} that was "
                             f"checked, not {version!r}"))
        at_pin = None
    elif not is_commit(roots[target.id], version):
        out.append(("error", f"{label}: {version[:12]} is not a commit of {target.github}"))
        at_pin = None
    else:
        at_pin = identifier in ids.get(target, version)
        if not at_pin:
            out.append(("error", f"{label}: no such record in {target.name} at {version[:12]}"))
    on_main = identifier in ids.get(target, None)
    if not on_main and at_pin:
        out.append(("warning", f"{label}: gone from {target.name} since {version[:12]}; review the link"))
    elif not on_main and at_pin is None:
        out.append(("error", f"{label}: no such record in {target.name}"))
    return out
