"""Pages about the Fleet: a status table, and the documentation pages made from fleet.yaml."""

from __future__ import annotations

import shutil
from pathlib import Path

from .canon import CanonError, read_pin
from .manifest import Fleet
from .members import git, read_answers, record_files
from .paths import SCHEMA_PATH


def status(fleet: Fleet, roots: dict[str, Path], head: str) -> str:
    """One row per member: where it is, what it holds, and what it is pinned to."""
    rows = ["| Member | Status | Commit | Records | mechmaker | Canon pin |", "|---|---|---|---|---|---|"]
    for m in fleet.members.values():
        mroot = roots.get(m.id)
        if mroot is None or not (mroot / ".git").exists():
            rows.append(f"| {m.name} | {m.status} | not fetched | | | |")
            continue
        commit = git(mroot, "rev-parse", "--short=12", "HEAD", check=False)
        count = len(record_files(mroot, m.records_dir))
        made = str(read_answers(mroot).get("_commit", ""))
        try:
            ref = str((read_pin(mroot) or {}).get("ref") or "")
        except CanonError:
            ref = "unreadable"
        pin = "none" if not ref else (f"{ref[:12]} (current)" if ref == head else ref[:12])
        rows.append(f"| {m.name} | {m.status} | {commit} | {count} | {made} | {pin} |")
    return "\n".join(rows) + "\n"


def members_page(fleet: Fleet) -> str:
    out = [f"# Members of {fleet.name}", "",
           "Made from `fleet.yaml` by `just docs-pages`. Edit that file, not this page.", "",
           "| Mech | Status | One record is | Repository |", "|---|---|---|---|"]
    for m in fleet.members.values():
        out.append(f"| **{m.name}** (`{m.id}:`) | {m.status} | {m.owns} | "
                   f"[{m.github}](https://github.com/{m.github}) |")
    if not fleet.members:
        out.append("| none yet | | | |")
    notes = [m for m in fleet.members.values() if m.scope_notes]
    if notes:
        out += ["", "## Scope", ""]
        out += [f"- **{m.name}**: {m.scope_notes}" for m in notes]
    return "\n".join(out) + "\n"


def relationships_page(fleet: Fleet) -> str:
    out = [f"# Relationships in {fleet.name}", "",
           "Records of one Mech link to records of another only through a relationship declared here. "
           "Made from `fleet.yaml` by `just docs-pages`.", ""]
    if not fleet.relationships:
        return "\n".join(out + ["None declared yet."]) + "\n"
    out += ["```mermaid", "flowchart LR"]
    for m in fleet.members.values():
        out.append(f"  {m.id}[\"{m.name}\"]")
    for r in fleet.relationships.values():
        out.append(f"  {r.subject} -- \"{r.slot}\" --> {r.object}")
    out += ["```", ""]
    for r in fleet.relationships.values():
        s, o = fleet.members[r.subject], fleet.members[r.object]
        out += [f"## {r.id}", "", f"**{s.name}** `{r.slot}` → **{o.name}**, as `{r.class_name}`.", "",
                r.description, "", "| Relation | Meaning |", "|---|---|"]
        out += [f"| `{k}` | {v} |" for k, v in r.relations.items()]
        if r.bases:
            out += ["", "| Basis | Meaning |", "|---|---|"]
            out += [f"| `{k}` | {v} |" for k, v in r.bases.items()]
        out.append("")
    return "\n".join(out)


def schema_pages(docs: Path) -> list[Path]:
    """The Fleet model: an entity diagram (docs/model.md) and one page per element (docs/schema/)."""
    from linkml.generators.docgen import DocGenerator
    from linkml.generators.erdiagramgen import ERDiagramGenerator

    out = docs / "schema"
    shutil.rmtree(out, ignore_errors=True)
    DocGenerator(str(SCHEMA_PATH), subfolder_type_separation=True).serialize(directory=str(out))
    diagram = ERDiagramGenerator(str(SCHEMA_PATH), structural=True).serialize()
    model = docs / "model.md"
    model.write_text("# The Fleet model\n\nWhat fleet.yaml can hold, from the Fleet down. Each class has a "
                     "page under [Schema](schema/index.md).\n\n" + diagram + "\n", encoding="utf-8")
    return [model, out]


def write_pages(fleet: Fleet, docs: Path) -> list[Path]:
    pages = {docs / "members.md": members_page(fleet), docs / "relationships.md": relationships_page(fleet)}
    for path, text in pages.items():
        path.write_text(text, encoding="utf-8")
    return list(pages) + schema_pages(docs)
