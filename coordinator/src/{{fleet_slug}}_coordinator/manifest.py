"""Load fleet.yaml, and refuse it unless it is right.

fleet.yaml is checked twice: against the Fleet schema (fields, types,
patterns), then against the rules a schema cannot state (a relationship's
ends are members, two members never share a name, one subject never uses a
slot twice). A repeated key in the YAML is an error too: the second value
would otherwise win without a word.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .paths import FLEET_FILE, SCHEMA_PATH


class FleetError(Exception):
    """fleet.yaml is wrong. The message lists every problem found."""


@dataclass(frozen=True)
class Member:
    id: str
    name: str
    github: str
    status: str
    owns: str
    record_class: str
    records_dir: str
    package_path: str
    uri: str
    identity_prefix: str = ""
    scope_notes: str = ""

    @property
    def owner(self) -> str:
        return self.github.split("/", 1)[0]

    @property
    def repo(self) -> str:
        return self.github.split("/", 1)[1]


@dataclass(frozen=True)
class Relationship:
    id: str
    subject: str
    object: str
    slot: str
    class_name: str
    description: str
    relations: dict[str, str] = field(default_factory=dict)
    bases: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Fleet:
    id: str
    name: str
    description: str
    coordinator: str
    members: dict[str, Member]
    relationships: dict[str, Relationship]

    def links_from(self, member_id: str) -> list[Relationship]:
        return [r for r in self.relationships.values() if r.subject == member_id]

    def by_name(self, name: str) -> Member | None:
        return next((m for m in self.members.values() if m.name == name), None)

    def checked(self) -> list[Member]:
        """Members the audits read: active ones, and retired ones, whose records links may still name."""
        return [m for m in self.members.values() if m.status in ("active", "retired")]


class _UniqueKeyLoader(yaml.SafeLoader):
    pass


def _no_duplicates(loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise FleetError(f"line {key_node.start_mark.line + 1}: the key {key!r} appears twice")
        seen.add(key)
    return loader.construct_mapping(node, deep=deep)


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_duplicates)


def read_yaml(path: Path) -> dict:
    data = yaml.load(path.read_text(), Loader=_UniqueKeyLoader)  # a SafeLoader that refuses repeated keys
    return data if isinstance(data, dict) else {}


def schema_errors(data: dict) -> list[str]:
    from linkml.validator import validate

    report = validate(data, str(SCHEMA_PATH), "Fleet", strict=False)
    return [r.message for r in report.results]


def _terms(raw: dict | None) -> dict[str, str]:
    return {name: (v or {}).get("description", "") for name, v in (raw or {}).items()}


def build(data: dict) -> Fleet:
    members = {}
    for key, m in (data.get("members") or {}).items():
        github = m["github"]
        members[key] = Member(
            id=key, name=m["name"], github=github, status=m["status"], owns=m["owns"],
            record_class=m["record_class"], records_dir=m["records_dir"].rstrip("/"),
            package_path=m.get("package_path") or f"src/{key}",
            uri=m.get("uri") or f"https://w3id.org/{github.split('/', 1)[0]}/{key}/",
            identity_prefix=m.get("identity_prefix") or "", scope_notes=m.get("scope_notes") or "",
        )
    relationships = {}
    for key, r in (data.get("relationships") or {}).items():
        obj = members.get(r["object"])
        relationships[key] = Relationship(
            id=key, subject=r["subject"], object=r["object"], slot=r["slot"],
            class_name=r.get("class_name") or (f"{obj.name}Link" if obj else ""),
            description=r["description"], relations=_terms(r.get("relations")), bases=_terms(r.get("bases")),
        )
    return Fleet(id=data["id"], name=data["name"], description=data.get("description") or "",
                 coordinator=data["coordinator"], members=members, relationships=relationships)


def rule_errors(fleet: Fleet) -> list[str]:
    errors = []
    names: dict[str, str] = {}
    repos: dict[str, str] = {}
    for m in fleet.members.values():
        if m.name in names:
            errors.append(f"members {names[m.name]} and {m.id} share the name {m.name}")
        names.setdefault(m.name, m.id)
        if m.github.lower() in repos:
            errors.append(f"members {repos[m.github.lower()]} and {m.id} share the repository {m.github}")
        repos.setdefault(m.github.lower(), m.id)
        if m.github.lower() == fleet.coordinator.lower():
            errors.append(f"member {m.id}'s repository is the Coordinator's")
    slots: dict[tuple[str, str], str] = {}
    classes: dict[tuple[str, str], str] = {}
    for r in fleet.relationships.values():
        for end in ("subject", "object"):
            if getattr(r, end) not in fleet.members:
                errors.append(f"relationship {r.id}: {end} {getattr(r, end)} is not a member")
        if r.subject == r.object:
            errors.append(f"relationship {r.id}: subject and object are both {r.subject}; "
                          "links within one Mech belong to its own schema")
        if not r.relations:
            errors.append(f"relationship {r.id}: give at least one relation")
        key = (r.subject, r.slot)
        if key in slots:
            errors.append(f"relationships {slots[key]} and {r.id} both use {r.subject}'s slot {r.slot}")
        slots.setdefault(key, r.id)
        ckey = (r.subject, r.class_name)
        if r.class_name and ckey in classes:
            errors.append(f"relationships {classes[ckey]} and {r.id} both make {r.subject}'s class "
                          f"{r.class_name}; give one a class_name")
        classes.setdefault(ckey, r.id)
    return errors


def load(root: Path, path: Path | None = None) -> Fleet:
    """The Fleet in root/fleet.yaml (or path). Raises FleetError listing every problem."""
    path = path or root / FLEET_FILE
    if not path.exists():
        raise FleetError(f"{path} does not exist")
    data = read_yaml(path)
    errors = schema_errors(data)
    if errors:
        raise FleetError("\n".join(f"{path.name}: {e}" for e in errors))
    fleet = build(data)
    errors = rule_errors(fleet)
    if errors:
        raise FleetError("\n".join(f"{path.name}: {e}" for e in errors))
    return fleet
