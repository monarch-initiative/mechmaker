"""Generate the reference pages of the mechmaker docs from the source.

    uv run python scripts/gen_docs.py

Writes, and does not commit:
  docs/reference/questions.md    every Copier question, from copier.yml
  docs/reference/ontologies.md   the ontology catalog, from copier.yml
  docs/skills/*.md               one page per mechmaker skill, from skills/
  docs/reference/mech-skills.md  the skills a generated Mech carries
  docs/workflows.md              the workflow catalog a Mech gets, defaults marked

These pages are generated so they cannot drift from the template.
"""

from __future__ import annotations

import re
import shutil
import sys
import urllib.parse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
REPO = "https://github.com/monarch-initiative/mechmaker/blob/main/"

# Skill descriptions are templates. Show them filled in for an example Mech.
PLACEHOLDERS = {
    "mech_name": "HabitatMech",
    "record_noun": "habitat",
    "records_dir": "data/habitats",
    "mech_slug": "habitatmech",
    "record_article": "a",
}


def source_link(path: Path) -> str:
    rel = path.relative_to(ROOT).as_posix()
    return REPO + urllib.parse.quote(rel)


def md_cell(text: object) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def fill(text: str) -> str:
    text = re.sub(r"\{\{\s*(\w+)[^}]*\}\}", lambda m: PLACEHOLDERS.get(m.group(1), m.group(1)), text)
    return re.sub(r"\{%.*?%\}", "", text)


def sections(raw: str) -> dict[str, str]:
    """Map each question to the section heading above it in copier.yml."""
    out: dict[str, str] = {}
    current = "General"
    for line in raw.splitlines():
        m = re.match(r"#\s*-{5,}\s*(\w[\w ]*)$", line)
        if m:
            current = m.group(1).strip().capitalize()
            continue
        m = re.match(r"^([a-z_]+):", line)
        if m:
            out[m.group(1)] = current
    return out


def questions() -> str:
    raw = (ROOT / "copier.yml").read_text()
    data = yaml.safe_load(raw)
    where = sections(raw)
    lines = [
        "# Copier questions",
        "",
        "Every question `copier copy` asks, in order, generated from",
        f"[`copier.yml`]({source_link(ROOT / 'copier.yml')}). Answer them interactively, or put the",
        "answers in a YAML file and pass `--data-file answers.yml --defaults`.",
        "",
        "A default in `{{ }}` is computed from earlier answers. A question with a",
        "condition is asked only when the condition holds.",
    ]
    current = None
    for key, q in data.items():
        if key.startswith("_") or not isinstance(q, dict):
            continue
        if q.get("when") is False or ("when" in q and not q.get("help")):
            continue  # computed values, not questions
        if where.get(key) != current:
            current = where.get(key)
            lines += ["", f"## {current}", "",
                      "| Question | Type | Default | What it decides |", "|---|---|---|---|"]
        help_text = md_cell(q.get("help", ""))
        if "when" in q:
            help_text += f" *Asked when* `{md_cell(q['when']).strip('{} ')}`."
        choices = q.get("choices")
        if isinstance(choices, dict):
            values = ", ".join(f"`{v}`" for v in choices.values())
            help_text += f" Choices: {values}."
        elif isinstance(choices, list):
            help_text += " Choices: " + ", ".join(f"`{v}`" for v in choices) + "."
        kind = q.get("type", "str") + (" (several)" if q.get("multiselect") else "")
        if "default" not in q:
            default = "required when asked" if "when" in q else "required"
        elif q["default"] in ("", None):
            default = "empty"
        else:
            default = f"`{md_cell(q['default'])}`"
        lines.append(f"| `{key}` | {kind} | {default} | {help_text} |")
    return "\n".join(lines) + "\n"


def ontologies() -> str:
    data = yaml.safe_load((ROOT / "copier.yml").read_text())
    catalog = yaml.safe_load(data["ontology_catalog"]["default"])
    lines = [
        "# Ontology catalog",
        "",
        "The ontologies the `ontologies` question offers. Each one adds, to the",
        "generated schema, a descriptor class, a dynamic enum rooted at the term",
        "below, and a record section. Every root was checked against OLS before it",
        "was added. Generated from `ontology_catalog` in `copier.yml`.",
        "",
        "| Key | Prefix | Root | Root label | Descriptor class | Record section | Adapter |",
        "|---|---|---|---|---|---|---|",
    ]
    for key, o in catalog.items():
        lines.append(
            f"| `{key}` | {o['prefix']} | `{o['root']}` | {o['root_label']} | `{o['descriptor']}` "
            f"| `{o['slot']}` | `{o['adapter']}` |"
        )
    lines += [
        "",
        "To add an ontology to the catalog, check its root first:",
        "",
        "```bash",
        "python skills/make-mech/scripts/check_terms.py label <CURIE>",
        "```",
        "",
        "## Ontologies outside the catalog",
        "",
        "The `extra_ontologies` question takes any ontology OAK can read, and gives",
        "it the same descriptor class, dynamic enum and record section. Each item",
        "names a `prefix`, a `root`, its `root_label` and a `noun`, and optionally",
        "an `adapter`, a `uri`, a `slot`, a `descriptor` and an `enum`.",
        "",
        "| Adapter | Reads | Needs |",
        "|---|---|---|",
        "| `ols:<name>` (the default) | EBI's Ontology Lookup Service | the network |",
        "| `sqlite:obo:<name>` | a prebuilt SQLite copy of an OBO Foundry ontology "
        "| one download, then nothing |",
        "| `bioportal:<name>` | BioPortal, is-a only "
        "| `BIOPORTAL_API_KEY`, locally and as a repository secret |",
        "| `simpleobo:ontologies/<file>.obo` | an OBO file in the Mech's repository | the file, committed |",
        "| `pronto:ontologies/<file>.owl` | an OBO or OWL file in the repository | the file, committed |",
        "| `sqlite:ontologies/<file>.db` | a SQLite ontology file in the repository | the file, committed |",
        "",
        "Check the root and a few expected terms through the same adapter:",
        "",
        "```bash",
        "python skills/make-mech/scripts/check_terms.py --adapter sqlite:obo:zfa \\",
        "    under ZFA:0100000 ZFA:0000107",
        "```",
        "",
        "`term_backend: sqlite` makes the catalog ontologies use `sqlite:obo:` too.",
        "",
        "BioPortal needs two things a Mech handles for you. OAK's BioPortal adapter",
        "(oaklib 0.7.4) rejects the arguments the term checks pass, so every term",
        "would fail its enum; the Mech's `oak_compat.py` patches that until OAK is",
        "fixed. And a failed BioPortal request prints its URL with the API key in",
        "it; the Mech's `just` recipes hide the key. Run term checks through `just`.",
        "",
        "GAZ is not in the catalog. As OLS serves it, countries have no is-a",
        "parent, so a dynamic enum rooted in GAZ cannot reach them. `NCIT_COUNTRY`",
        "covers countries instead.",
    ]
    return "\n".join(lines) + "\n"


def frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---"):
        _, front, body = text.split("---", 2)
        return yaml.safe_load(fill(front)) or {}, body.lstrip()
    return {}, text


def mechmaker_skills() -> list[tuple[str, str]]:
    out_dir = DOCS / "skills"
    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    index = [
        "# mechmaker skills",
        "",
        "These skills guide the agent that makes a Mech. Install them as a",
        "Claude Code plugin (see [Getting started](../getting-started.md)), or",
        "work inside a mechmaker checkout, where `.claude/skills` points at them.",
        "",
        "| Skill | Use it to |",
        "|---|---|",
    ]
    pages = []
    for path in sorted((ROOT / "skills").glob("*/SKILL.md")):
        meta, body = frontmatter(path.read_text())
        name = meta.get("name", path.parent.name)
        desc = md_cell(meta.get("description", ""))
        index.append(f"| [{name}]({name}.md) | {desc} |")
        page = [f"!!! info \"Skill `{name}`\"", f"    {desc}", "",
                f"    Source: [`{path.relative_to(ROOT)}`]({source_link(path)})", "", body]
        (out_dir / f"{name}.md").write_text("\n".join(page))
        pages.append((name, f"skills/{name}.md"))
    (out_dir / "index.md").write_text("\n".join(index) + "\n")
    return pages


def mech_skills() -> str:
    lines = [
        "# Skills in a generated Mech",
        "",
        "Every Mech carries these in `.claude/skills/`, for everyday curation.",
        "They are templates. The Mech's own name, record noun and paths are filled",
        "in when it is generated; below they are shown for an example Mech,",
        "HabitatMech, whose records are habitats.",
        "",
        "| Skill | Use it to | Source |",
        "|---|---|---|",
    ]
    for path in sorted((ROOT / "template" / ".claude" / "skills").glob("*/SKILL.md.jinja")):
        meta, _ = frontmatter(path.read_text())
        lines.append(f"| `{meta.get('name', path.parent.name)}` | {md_cell(meta.get('description', ''))} "
                     f"| [template]({source_link(path)}) |")
    return "\n".join(lines) + "\n"


def workflows() -> str:
    """Render the catalog every Mech gets, marking the template's defaults."""
    import jinja2

    data = yaml.safe_load((ROOT / "copier.yml").read_text())
    defaults = data["workflows"]["default"]
    src = (ROOT / "template" / "docs" / "WORKFLOWS.md.jinja").read_text()
    text = jinja2.Environment().from_string(src).render(
        workflows=defaults, include_site=True, agent_schedules=False, langfuse=False,
    )
    head, sep, rest = text.partition("## Always on")
    intro = (
        "# Workflows\n\n"
        "A Mech can carry GitHub workflows that check it and, if you choose, AI\n"
        "agents that help curate it. Each one is a Copier choice (the `workflows`\n"
        "question), so a Mech gets only the ones picked for it, and gets more later\n"
        "by answering again with `copier update`.\n\n"
        "This is the catalog every generated Mech carries as `docs/WORKFLOWS.md`.\n"
        "Here, **on** marks a workflow chosen by default. Generated from\n"
        f"[`template/docs/WORKFLOWS.md.jinja`]({source_link(ROOT / 'template/docs/WORKFLOWS.md.jinja')}).\n\n"
    )
    rest = rest.replace("| Key | State |", "| Key | Default |")
    langfuse = "### Langfuse\n\nOff by default. Answer `langfuse` to trace every agent run.\n\n"
    rest = re.sub(r"### Langfuse\n\n.*?\n\n", langfuse, rest, flags=re.S)
    return intro + sep + rest


def main() -> int:
    ref = DOCS / "reference"
    ref.mkdir(parents=True, exist_ok=True)
    (ref / "questions.md").write_text(questions())
    (ref / "ontologies.md").write_text(ontologies())
    (ref / "mech-skills.md").write_text(mech_skills())
    (DOCS / "workflows.md").write_text(workflows())
    pages = mechmaker_skills()
    print(f"Generated docs/reference/, docs/workflows.md and docs/skills/ ({len(pages)} skills).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
