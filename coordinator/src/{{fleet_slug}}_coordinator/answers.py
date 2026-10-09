"""A member's fleet answers, and whether the member's own answers agree with them.

fleet.yaml is the source of truth for what a member is and how it links.
`fleet answers <member>` prints the Copier answers that say the same thing,
for the member's `copier copy` (a new Mech) or `copier update` (a change):

    fleet answers habitatmech > /tmp/habitatmech-fleet.yml
    # in the member:
    uvx copier update --vcs-ref=:current: --skip-answered --defaults \\
        --data-file /tmp/habitatmech-fleet.yml

mechmaker turns fleet_links into the member's link classes: one CrossCorpusLink
subclass per relationship, with its relations and bases as enums.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from .manifest import Fleet, Member
from .members import read_answers

# The member's answers that must equal fleet.yaml's, and the field each comes from.
IDENTITY = {
    "mech_name": "name",
    "mech_slug": "id",
    "github_org": "owner",
    "repo_name": "repo",
    "record_class": "record_class",
    "records_dir": "records_dir",
}


def links(fleet: Fleet, member: Member) -> list[dict]:
    out = []
    for rel in fleet.links_from(member.id):
        target = fleet.members[rel.object]
        link = {
            "slot": rel.slot,
            "target": target.name,
            "prefix": target.id,
            "uri": target.uri,
            "description": rel.description,
            "relations": dict(rel.relations),
        }
        if rel.bases:
            link["bases"] = dict(rel.bases)
        if rel.class_name != f"{target.name}Link":
            link["class"] = rel.class_name
        out.append(link)
    return out


def member_answers(fleet: Fleet, member: Member) -> dict:
    answers = {key: getattr(member, attr) for key, attr in IDENTITY.items()}
    if member.identity_prefix:
        answers["identity_prefix"] = member.identity_prefix
    answers["fleet_name"] = fleet.name
    answers["fleet_coordinator"] = fleet.coordinator
    answers["fleet_links"] = links(fleet, member)
    return answers


def render(fleet: Fleet, member: Member) -> str:
    head = (f"# {member.name}'s answers from {fleet.name}'s Coordinator (fleet.yaml).\n"
            "# Merge them into the Mech's answers.yml before `copier copy`, or pass them\n"
            "# to `uvx copier update --vcs-ref=:current: --skip-answered --defaults --data-file`\n"
            "# in the Mech (one already updated to a mechmaker that knows Fleets).\n")
    body = yaml.safe_dump(member_answers(fleet, member), sort_keys=False, allow_unicode=True, width=100)
    return head + body


def _norm(value: object) -> object:
    """Answers come back from YAML; compare them as plain data, ignoring key order."""
    return yaml.safe_load(yaml.safe_dump(value, sort_keys=True))


def disagreements(fleet: Fleet, member: Member, mroot: Path) -> list[str]:
    """Where the member's .copier-answers.yml differs from what fleet.yaml says it should be."""
    have = read_answers(mroot)
    if not have:
        return [f"{member.id}: no .copier-answers.yml; was it made with mechmaker?"]
    want = member_answers(fleet, member)
    out = []
    for key, value in want.items():
        if key == "identity_prefix" and not value:
            continue
        got = have.get(key, [] if key == "fleet_links" else None)
        if _norm(got) != _norm(value):
            if key == "fleet_links":
                out.append(f"{member.id}: its fleet_links differ from fleet.yaml's relationships. "
                           f"Take `fleet answers {member.id}` with copier update.")
            else:
                out.append(f"{member.id}: answer {key} is {got!r}; fleet.yaml says {value!r}")
    return out
