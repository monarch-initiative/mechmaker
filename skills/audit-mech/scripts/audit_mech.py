#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6.0"]
# ///
"""Check a Mech against what was asked for it, and print a checklist.

    uv run audit_mech.py <mech>                       # the Copier answers, and the make-mech steps
    uv run audit_mech.py <mech> --requests requests.yml   # and the person's own asks
    uv run audit_mech.py <mech> --qc                  # and run `just qc` in the Mech
    uv run audit_mech.py <mech> --json                # the same items, as JSON

The answers come from the Mech's `.copier-answers.yml`. Each answer that turns
something on becomes one item, checked against the files the template writes
for it. Only answers present in the file are checked: a Mech made from an
older template is not faulted for a question it was never asked.

A requests file holds what the person asked for in their own words, one item
each. `check` is optional; without it the item is left for the agent to verify.

    - feature: Every goat breed in VBO, keyed to its term
      said: "one record per breed, using VBO ids"   # optional, their words
      check: {class: GoatBreed}                     # the schema has this class
    - feature: Country of origin on each record
      check: {slot: countries}                      # the schema has this slot
    - feature: An import from DAD-IS
      check: {recipe: import-dad-is}                # the justfile has this recipe
    - feature: A page on breed standards
      check: {path: docs/standards.md}              # this file exists
    - feature: Origin shown on the front page
      check: {contains: {path: conf/site.yaml, text: countries}}
    - feature: Seed records
      check: {records: 5}                           # at least this many records
    - feature: Records read like a breed society's description
                                                    # no check: the agent judges it

Each item is done, missing, or to check (a person or agent must look).
Exit 0 when nothing is missing, 1 when something is, 2 when the folder is
not a Mech, 64 on a usage error: a bad argument, or a requests file that is
absent or cannot be read as above.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml

DONE, MISSING, CHECK = "done", "missing", "check"
BOX = {DONE: "[x]", MISSING: "[ ]", CHECK: "[?]"}

# The ontology catalog in mechmaker's copier.yml: key -> prefix, slot, enum,
# root, adapter. A test keeps this equal to the catalog.
CATALOG = {
    "GO_BP": ("GO", "biological_processes", "BiologicalProcessTerm", "GO:0008150", "ols:go"),
    "GO_MF": ("GO", "molecular_functions", "MolecularFunctionTerm", "GO:0003674", "ols:go"),
    "GO_CC": ("GO", "cellular_components", "CellularComponentTerm", "GO:0005575", "ols:go"),
    "CL": ("CL", "cell_types", "CellTypeTerm", "CL:0000000", "ols:cl"),
    "UBERON": ("UBERON", "anatomical_entities", "AnatomicalEntityTerm", "UBERON:0001062", "ols:uberon"),
    "CHEBI": ("CHEBI", "chemical_entities", "ChemicalEntityTerm", "CHEBI:24431", "ols:chebi"),
    "HP": ("HP", "phenotypes", "PhenotypeTerm", "HP:0000118", "ols:hp"),
    "MONDO": ("MONDO", "diseases", "DiseaseTerm", "MONDO:0000001", "ols:mondo"),
    "NCBITaxon": ("NCBITaxon", "organisms", "OrganismTerm", "NCBITaxon:1", "ols:ncbitaxon"),
    "ENVO": ("ENVO", "environments", "EnvironmentTerm", "ENVO:01000254", "ols:envo"),
    "PATO": ("PATO", "qualities", "QualityTerm", "PATO:0000001", "ols:pato"),
    "OBI": ("OBI", "assays", "AssayTerm", "OBI:0000070", "ols:obi"),
    "UO": ("UO", "units", "UnitTerm", "UO:0000000", "ols:uo"),
    "PR": ("PR", "proteins", "ProteinTerm", "PR:000000001", "ols:pr"),
    "SO": ("SO", "sequence_features", "SequenceFeatureTerm", "SO:0000110", "ols:so"),
    "MAXO": ("MAXO", "medical_actions", "MedicalActionTerm", "MAXO:0000001", "ols:maxo"),
    "FOODON": ("FOODON", "foods", "FoodTerm", "FOODON:00001002", "ols:foodon"),
    "VBO": ("VBO", "breeds", "BreedTerm", "VBO:0400000", "ols:vbo"),
    "VT": ("VT", "traits", "TraitTerm", "VT:0000001", "ols:vt"),
    "NCIT_COUNTRY": ("NCIT", "countries", "CountryTerm", "NCIT:C25464", "ols:ncit"),
}

# Files each workflow answer writes under .github/workflows/.
WORKFLOW_FILES = {"dedupe": ["dedupe.yaml", "auto-close-duplicates.yaml"]}
AGENT_WORKFLOWS = {
    "claude",
    "review",
    "triage",
    "dedupe",
    "pr-shepherd",
    "curation-scanner",
    "literature-scan",
    "compliance",
    "post-review",
}
# Agent workflows with their own prompt in .github/prompts/.
PROMPTED = {
    "review",
    "triage",
    "pr-shepherd",
    "curation-scanner",
    "literature-scan",
    "compliance",
    "post-review",
}
SCHEDULED_AGENTS = {"pr-shepherd", "curation-scanner", "literature-scan", "compliance", "post-review"}

CODE_LICENSE_TEXT = {
    "BSD-3-Clause": "BSD 3-Clause License",
    "MIT": "MIT License",
    "Apache-2.0": "Apache License",
}
DATA_LICENSE_TEXT = {
    "CC-BY-4.0": "creativecommons.org/licenses/by/4.0",
    "CC0-1.0": "creativecommons.org/publicdomain/zero/1.0",
}

# The collection answer -> its name, and its value in the registry's CollectionEnum.
COLLECTIONS = {"monarch": ("Monarch", "monarch"), "xmech": ("X-Mech suite", "x-mech-suite")}

# make-mech seeds three to five records.
SEED_MIN = 3


@dataclass
class Item:
    feature: str
    asked: str  # where the ask came from: an answer, a make-mech step, or the requests file
    status: str
    found: str  # what was seen, or why it is missing
    fix: str = ""  # the next step, when not done


class Mech:
    def __init__(self, root: Path):
        self.root = root
        self.answers = yaml.safe_load((root / ".copier-answers.yml").read_text()) or {}
        self.slug = self.answers.get("mech_slug", "")
        self.schema_path = root / "src" / self.slug / "schema" / f"{self.slug}.yaml"
        self.schema = self._yaml(self.schema_path) or {}
        # Only the Mech's own history counts: a Mech inside another repository has none.
        own = Path(self._git("rev-parse", "--show-toplevel") or "/nonexistent").resolve() == root.resolve()
        self.first_commit = self._git("rev-list", "--max-parents=0", "HEAD").split("\n")[0] if own else ""

    def _yaml(self, path: Path):
        try:
            return yaml.safe_load(path.read_text())
        except (OSError, yaml.YAMLError):
            return None

    def _git(self, *args: str) -> str:
        try:
            out = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True)
        except FileNotFoundError:
            return ""
        return out.stdout.strip() if out.returncode == 0 else ""

    def conf(self, name: str) -> dict:
        data = self._yaml(self.root / "conf" / name)
        return data if isinstance(data, dict) else {}

    def text(self, rel: str) -> str:
        try:
            return (self.root / rel).read_text()
        except OSError:
            return ""

    def exists(self, rel: str) -> bool:
        return (self.root / rel).exists()

    def classes(self) -> dict:
        return self.schema.get("classes") or {}

    def slots(self) -> set[str]:
        names = set(self.schema.get("slots") or {})
        for cls in self.classes().values():
            cls = cls or {}
            names.update(cls.get("slots") or [])
            names.update(cls.get("attributes") or {})
        return names

    def enum_roots(self, enum: str) -> list[str] | None:
        e = (self.schema.get("enums") or {}).get(enum)
        if e is None:
            return None
        return list(((e or {}).get("reachable_from") or {}).get("source_nodes") or [])

    def enum_users(self, enum: str) -> list[str]:
        """Slots whose range, or one of whose bindings, is the enum."""
        users: list[str] = []

        def walk(node, owner):
            if isinstance(node, dict):
                if node.get("range") == enum and owner and owner not in users:
                    users.append(owner)
                for k, v in node.items():
                    if k in ("slots", "attributes", "slot_usage") and isinstance(v, dict):
                        for name, d in v.items():
                            walk(d, name)
                    else:
                        walk(v, owner)
            elif isinstance(node, list):
                for v in node:
                    walk(v, owner)

        walk(self.schema, None)
        return users

    def adapters(self) -> dict:
        return self.conf("oak_config.yaml").get("ontology_adapters") or {}

    def records(self) -> list[Path]:
        d = self.root / self.answers.get("records_dir", "")
        return sorted(d.rglob("*.yaml")) if d.is_dir() else []

    def recipes(self) -> set[str]:
        return set(re.findall(r"^@?([A-Za-z][\w-]*)\b[^:=\n]*:(?!=)", self.text("justfile"), re.M))

    def changed_since_template(self, rel: str) -> bool | None:
        """Whether a file differs from the first commit, the untouched template. None without git."""
        if not self.first_commit:
            return None
        out = subprocess.run(
            ["git", "-C", str(self.root), "diff", "--quiet", self.first_commit, "--", rel],
            capture_output=True,
        )
        return out.returncode == 1


def ontology_selection(a: dict) -> list[dict]:
    """Each ontology the answers chose, named as copier.yml names it."""
    sel = []
    sqlite = a.get("term_backend") == "sqlite"
    for key in a.get("ontologies") or []:
        if key not in CATALOG:
            continue
        prefix, slot, enum, root, adapter = CATALOG[key]
        if sqlite:
            adapter = adapter.replace("ols:", "sqlite:obo:")
        sel.append(
            {"key": key, "prefix": prefix, "slot": slot, "enum": enum, "root": root, "adapter": adapter}
        )
    for x in a.get("extra_ontologies") or []:
        if not isinstance(x, dict):
            continue
        noun = str(x.get("noun", "")).strip()
        camel = "".join(w.capitalize() for w in noun.split())
        if noun.endswith("y") and noun[-2:-1] not in "aeiou":
            plural = noun[:-1] + "ies"
        elif noun.endswith(("s", "x", "ch", "sh")):
            plural = noun + "es"
        else:
            plural = noun + "s"
        sel.append(
            {
                "key": x["prefix"],
                "prefix": str(x["prefix"]),
                "slot": x.get("slot") or plural.replace(" ", "_").lower(),
                "enum": x.get("enum") or camel + "Term",
                "root": str(x["root"]),
                "adapter": x.get("adapter") or "ols:" + str(x["prefix"]).lower(),
            }
        )
    # One prefix, one adapter: identity_adapter checks a picked ontology that shares its prefix.
    if a.get("identity_prefix") and "identity_adapter" in a:
        for o in sel:
            if o["prefix"] == a["identity_prefix"]:
                o["adapter"] = a["identity_adapter"]
    return sel


def item(feature, asked, ok, found, fix="", status=None) -> Item:
    return Item(feature, asked, status or (DONE if ok else MISSING), found, "" if ok else fix)


def local_file(adapter: str) -> str | None:
    """The repository file an OAK adapter reads, or None for a service or a downloaded sqlite:obo."""
    kind, _, path = adapter.partition(":")
    if kind in ("simpleobo", "pronto", "obograph", "sqlite") and not adapter.startswith("sqlite:obo:"):
        return path
    return None


def local_file_item(m: Mech, prefix: str, path: str, asked: str) -> Item:
    return item(
        f"{prefix} ontology file `{path}`",
        asked,
        m.exists(path),
        "present" if m.exists(path) else "not in the repository",
        f"copy the file to `{path}` and commit it",
    )


def from_answers(m: Mech) -> list[Item]:
    a = m.answers
    out: list[Item] = []
    slug, cls = m.slug, a.get("record_class", "")
    rel_schema = m.schema_path.relative_to(m.root).as_posix()

    out.append(
        item(
            f"{a.get('mech_name', slug)} as package `{slug}`",
            "mech_name, mech_slug",
            m.schema_path.exists(),
            f"schema at `{rel_schema}`" if m.schema_path.exists() else f"no schema at `{rel_schema}`",
            "the package was renamed or never generated; regenerate with Copier",
        )
    )

    classes = m.classes()
    root_cls = [n for n, c in classes.items() if (c or {}).get("tree_root")]
    out.append(
        item(
            f"One record is one {a.get('record_noun', cls)} (class `{cls}`)",
            "record_class",
            cls in classes and cls in root_cls,
            f"`{cls}` is the schema's tree root"
            if cls in root_cls
            else f"tree root is {root_cls or 'unset'}; `{cls}` "
            f"{'exists' if cls in classes else 'is not in the schema'}",
            "make the record class the tree root, or record the rename in docs/DOMAIN.md",
        )
    )

    rd = a.get("records_dir")
    if rd:
        out.append(
            item(
                f"Records under `{rd}/`",
                "records_dir",
                m.exists(rd),
                "folder exists" if m.exists(rd) else "folder is absent",
                f"create `{rd}/` or set RECORDS_DIR in src/{slug}/paths.py",
            )
        )

    prefix, root = a.get("identity_prefix"), a.get("identity_root")
    if prefix:
        roots = m.enum_roots("IdentityTerm") or []
        prefixes = m.schema.get("prefixes") or {}
        # validate.py and the term check reach the root through record_term (#45).
        bound = "record_term" in m.enum_users("IdentityTerm")
        ok = root in roots and prefix in prefixes and bound
        found = (
            f"`IdentityTerm` descends from {roots or 'nothing'}; prefix {prefix} "
            f"{'declared' if prefix in prefixes else 'not declared'}; "
            f"`record_term` {'binds' if bound else 'does not bind'} it"
        )
        out.append(
            item(
                f"Records keyed by {prefix} terms under `{root}`",
                "identity_prefix, identity_root",
                ok,
                found,
                "restore the `IdentityTerm` enum, the prefix, and `record_term`'s binding in the schema",
            )
        )
        if a.get("identity_direct_only"):
            e = (m.schema.get("enums") or {}).get("IdentityTerm") or {}
            direct = (e.get("reachable_from") or {}).get("is_direct") is True
            out.append(
                item(
                    f"Only direct children of `{root}` key a record",
                    "identity_direct_only",
                    direct,
                    "`IdentityTerm` has is_direct: true" if direct else "is_direct is not true",
                    "set is_direct: true on `IdentityTerm`; `just check-identity` relies on it",
                )
            )
        want = a.get("identity_adapter")
        if want is not None:
            got = m.adapters().get(prefix)
            out.append(
                item(
                    f"{prefix} terms checked with `{want or 'nothing'}`",
                    "identity_adapter",
                    got == want,
                    f"conf/oak_config.yaml has `{got}`",
                    f'set {prefix}: "{want}" in conf/oak_config.yaml',
                )
            )

    slots, adapters = m.slots(), m.adapters()
    domain = m.text("docs/DOMAIN.md")
    for o in ontology_selection(a):
        # The design may move the terms into another section; the enum is what binds them.
        has_slot = o["slot"] in slots
        roots = m.enum_roots(o["enum"])
        has_enum = roots is not None and o["root"] in roots
        users = m.enum_users(o["enum"])
        adapter_ok = adapters.get(o["prefix"]) == o["adapter"]
        bits = [
            f"enum `{o['enum']}` "
            + ("under " + o["root"] if has_enum else "absent" if roots is None else f"rooted at {roots}"),
            "bound by " + (", ".join(f"`{u}`" for u in users) if users else "no slot"),
            f"adapter `{adapters.get(o['prefix'])}`",
        ]
        if not has_slot:
            bits.insert(0, f"no `{o['slot']}` slot")
        if not has_enum or not users:
            fix = "the design cut it, or never wired it to a slot; say why in docs/DOMAIN.md, or restore it"
        else:
            fix = f'set {o["prefix"]}: "{o["adapter"]}" in conf/oak_config.yaml'
        if (not has_enum or not users) and o["prefix"] in domain:
            fix += f" (docs/DOMAIN.md mentions {o['prefix']}: read what it says)"
        out.append(
            item(
                f"{o['prefix']} terms ({o['key']})",
                "ontologies",
                has_enum and bool(users) and adapter_ok,
                "; ".join(bits),
                fix,
            )
        )
        path = local_file(o["adapter"])
        if path:
            ident_prefix = o["prefix"] == a.get("identity_prefix")
            asked = "identity_adapter" if ident_prefix else f"extra_ontologies: {o['key']}"
            out.append(local_file_item(m, o["prefix"], path, asked))

    ident = local_file(str(a.get("identity_adapter") or ""))
    picked = {local_file(o["adapter"]) for o in ontology_selection(a)}
    if a.get("identity_prefix") and ident and ident not in picked:
        out.append(local_file_item(m, a["identity_prefix"], ident, "identity_adapter"))

    if a.get("causal_graphs"):
        ok = "MechanismNode" in classes and "mechanisms" in slots
        out.append(
            item(
                "Causal mechanism graphs",
                "causal_graphs",
                ok,
                "`MechanismNode` and `mechanisms` present" if ok else "graph classes absent",
                "restore `MechanismNode`, or record in docs/DOMAIN.md why graphs were cut",
            )
        )

    reg_path = f"registry/{slug}.md"
    reg = registry_front_matter(m.text(reg_path))
    if a.get("taxon_scope"):
        want = [t.strip() for t in a["taxon_scope"].split(",") if t.strip()]
        got = [str(t) for t in reg.get("taxon") or []]
        out.append(
            item(
                f"Scoped to {', '.join(want)}",
                "taxon_scope",
                set(want) <= set(got),
                f"{reg_path} lists taxon {got or 'none'}",
                f"add the taxa to {reg_path}",
            )
        )
    if a.get("domains"):
        got = reg.get("domains") or []
        out.append(
            item(
                f"Registry domains {', '.join(a['domains'])}",
                "domains",
                set(a["domains"]) <= set(got),
                f"{reg_path} lists {got or 'none'}",
                f"set domains in {reg_path}",
            )
        )
    if a.get("collection") in COLLECTIONS:
        name, value = COLLECTIONS[a["collection"]]
        got = reg.get("collection") or []
        out.append(
            item(
                f"Joins the {name} collection",
                "collection",
                value in got,
                f"{reg_path} collection {got or 'none'}",
                f"add collection: [{value}] to {reg_path}",
            )
        )

    for key, path, table in (
        ("code_license", "LICENSE", CODE_LICENSE_TEXT),
        ("data_license", "LICENSE-data.md", DATA_LICENSE_TEXT),
    ):
        lic = a.get(key)
        if lic in table:
            ok = table[lic] in m.text(path)
            out.append(
                item(
                    f"{'Code' if key == 'code_license' else 'Data'} under {lic}",
                    key,
                    ok,
                    f"`{path}` {'names' if ok else 'does not name'} it",
                    f"restore `{path}` for {lic}",
                )
            )

    out += workflow_items(m)

    if a.get("deep_research"):
        parts = ["research/README.md", f"src/{slug}/research.py", ".claude/skills/deep-research/SKILL.md"]
        absent = [p for p in parts if not m.exists(p)]
        out.append(
            item(
                "Deep research",
                "deep_research",
                not absent,
                "research/, research.py and the skill present"
                if not absent
                else f"absent: {', '.join(absent)}",
                "regenerate with deep_research: true",
            )
        )
        tpl = "research/templates/record.md"
        changed = m.changed_since_template(tpl)
        out.append(
            item(
                "Research prompt written for the domain",
                "make-mech step 4",
                bool(changed),
                f"`{tpl}` "
                + {
                    True: "changed since the template",
                    False: "is the template's, unchanged",
                    None: "unknown: no git history",
                }[changed],
                "design-mech-schema rewrites it from the record's sections",
                status=CHECK if changed is not True else None,
            )
        )

    if a.get("include_site"):
        parts = [f"src/{slug}/render.py", f"src/{slug}/templates/record.html"]
        absent = [p for p in parts if not m.exists(p)]
        out.append(
            item(
                "Static record browser",
                "include_site",
                not absent,
                "render.py and templates present" if not absent else f"absent: {', '.join(absent)}",
                "regenerate with include_site: true",
            )
        )
    site = m.conf("site.yaml")
    for key, field in (("site_palette", "palette"), ("site_accent", "accent"), ("site_theme", "theme")):
        if a.get(key):
            got = site.get(field)
            # A later change in conf/site.yaml is the person's to make, so a difference is to check.
            out.append(
                item(
                    f"Site {field} {a[key]}",
                    key,
                    got == a[key],
                    f"conf/site.yaml has {got}",
                    f"conf/site.yaml was changed after generation; confirm {got} is wanted",
                    status=None if got == a[key] else CHECK,
                )
            )

    if a.get("include_claude_hook"):
        ok = m.exists(".claude/hooks/validate_record.py") and "PreToolUse" in m.text(".claude/settings.json")
        out.append(
            item(
                "Record check before each edit (Claude Code hook)",
                "include_claude_hook",
                ok,
                "hook and its PreToolUse entry present" if ok else "hook or its settings entry absent",
                "restore .claude/hooks/validate_record.py and its entry in .claude/settings.json",
            )
        )

    export = m.conf("export.yaml")
    if a.get("output_formats"):
        got = export.get("formats") or []
        absent = [f for f in a["output_formats"] if f not in got]
        out.append(
            item(
                f"Exports {', '.join(a['output_formats'])}",
                "output_formats",
                not absent,
                f"conf/export.yaml has {got}",
                f"add {absent} to conf/export.yaml and run `just export`",
            )
        )
        if {"csv", "tsv"} & set(a["output_formats"]) and a.get("tabular_layout"):
            got = export.get("tabular_layout")
            out.append(
                item(
                    f"Tables laid out {a['tabular_layout']}",
                    "tabular_layout",
                    got == a["tabular_layout"],
                    f"conf/export.yaml has {got}",
                    f"set tabular_layout: {a['tabular_layout']} in conf/export.yaml",
                )
            )
        if {"kgx", "kgx_maximal"} & set(a["output_formats"]) and "kgx_biolink" in a:
            got = m.conf("kgx.yaml").get("biolink")
            want = bool(a["kgx_biolink"])
            out.append(
                item(
                    f"KGX {'on' if want else 'off'} the Biolink model",
                    "kgx_biolink",
                    got is want,
                    f"conf/kgx.yaml has biolink: {got}",
                    f"set biolink: {str(want).lower()} in conf/kgx.yaml",
                )
            )
    if a.get("load_targets"):
        got = list(m.conf("load.yaml").get("targets") or {})
        absent = [t for t in a["load_targets"] if t not in got]
        out.append(
            item(
                f"`just load` into {', '.join(a['load_targets'])}",
                "load_targets",
                not absent,
                f"conf/load.yaml has {got or 'no targets'}",
                f"add {absent} to conf/load.yaml",
            )
        )
    return out


def workflow_items(m: Mech) -> list[Item]:
    a, out = m.answers, []
    wf = m.root / ".github" / "workflows"
    for name in a.get("workflows") or []:
        files = WORKFLOW_FILES.get(name, [f"{name}.yaml"])
        absent = [f for f in files if not (wf / f).exists()]
        out.append(
            item(
                f"Workflow `{name}`",
                "workflows",
                not absent,
                f"{', '.join(files)} present" if not absent else f"absent: {', '.join(absent)}",
                f"run `uvx copier update --vcs-ref=:current: --skip-answered --defaults` with {name} in workflows",
            )
        )
        if name in PROMPTED:
            rel = f".github/prompts/{name}.md"
            changed = m.changed_since_template(rel)
            if not m.exists(rel):
                out.append(
                    item(
                        f"Prompt for `{name}`",
                        "make-mech step 4b",
                        False,
                        f"`{rel}` absent",
                        "regenerate the workflow",
                    )
                )
            else:
                out.append(
                    item(
                        f"Prompt for `{name}` adapted to the domain",
                        "make-mech step 4b",
                        bool(changed),
                        f"`{rel}` "
                        + {
                            True: "changed since the template",
                            False: "is the template's, unchanged",
                            None: "present; no git history to compare",
                        }[changed],
                        "read it and fit it to the domain (the Mech's github-workflows skill)",
                        status=CHECK if changed is not True else None,
                    )
                )
    if "literature-scan" in (a.get("workflows") or []):
        rel = "conf/literature_scan.yaml"
        changed = m.changed_since_template(rel)
        out.append(
            item(
                "Literature scan tuned to the domain",
                "make-mech step 4b",
                bool(changed),
                f"`{rel}` "
                + {
                    True: "changed since the template",
                    False: "unchanged",
                    None: "present; no git history to compare",
                }[changed],
                "tune it until `just literature-scan --days 30` returns mostly relevant papers",
                status=CHECK if changed is not True else None,
            )
        )
    agents = [w for w in a.get("workflows") or [] if w in AGENT_WORKFLOWS]
    if a.get("agent_schedules"):
        sched = [w for w in agents if w in SCHEDULED_AGENTS]
        off = [
            w
            for w in sched
            if "schedule:" not in (wf / f"{w}.yaml").read_text()
            if (wf / f"{w}.yaml").exists()
        ]
        out.append(
            item(
                "Agent workflows run on their schedules",
                "agent_schedules",
                not off,
                f"scheduled: {[w for w in sched if w not in off]}" if not off else f"no schedule: {off}",
                "regenerate with agent_schedules: true",
            )
        )
    if a.get("langfuse") and agents:
        files = [f for w in agents for f in WORKFLOW_FILES.get(w, [f"{w}.yaml"]) if (wf / f).exists()]
        off = [
            f
            for f in files
            if "LANGFUSE_PUBLIC_KEY" not in (wf / f).read_text()
            and "claude-code-action" in (wf / f).read_text()
        ]
        out.append(
            item(
                "Agent traces sent to Langfuse",
                "langfuse",
                not off,
                "every agent workflow sets the LANGFUSE_* lines" if not off else f"no Langfuse: {off}",
                "regenerate with langfuse: true",
            )
        )
    return out


def registry_front_matter(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---", text, re.S)
    try:
        return (yaml.safe_load(m.group(1)) or {}) if m else {}
    except yaml.YAMLError:
        return {}


def is_converted(record: dict) -> bool:
    """Whether the record was made by the Mech's conversion helper (`just convert`)."""
    history = record.get("curation_history")
    first = history[0] if isinstance(history, list) and history else {}
    return (
        isinstance(first, dict)
        and first.get("action") == "CREATE"
        and str(first.get("description", "")).startswith("Converted from ")
    )


def from_steps(m: Mech) -> list[Item]:
    """What make-mech promises beyond the answers: a design, seeds, a registry entry."""
    out: list[Item] = []
    a = m.answers
    if not m.first_commit:
        out.append(
            item(
                "Git history, the untouched template as the first commit",
                "make-mech step 3",
                False,
                "not a git repository, or no commits",
                "git init -b main; commit the fresh copy",
            )
        )
    else:
        out.append(
            item(
                "Git history, the untouched template as the first commit",
                "make-mech step 3",
                True,
                f"first commit {m.first_commit[:7]}",
            )
        )

    domain = m.text("docs/DOMAIN.md")
    # A TODO opens a line, or fills a table cell.
    todos = len(re.findall(r"^TODO|\|\s*TODO\s*(?=\|)", domain, re.M))
    out.append(
        item(
            "Domain model written in docs/DOMAIN.md",
            "make-mech step 4",
            bool(domain) and not todos,
            f"{todos} TODO(s) left" if todos else ("filled in" if domain else "file absent"),
            "run design-mech-schema; each TODO is a decision not yet made",
        )
    )

    rel_schema = m.schema_path.relative_to(m.root).as_posix()
    changed = m.changed_since_template(rel_schema)
    out.append(
        item(
            "Schema shaped to the domain",
            "make-mech step 4",
            bool(changed),
            {
                True: "changed since the template",
                False: "still the scaffold",
                None: "no git history to compare",
            }[changed],
            "run design-mech-schema",
            status=CHECK if changed is None else None,
        )
    )

    recs = m.records()
    out.append(
        item(
            f"{SEED_MIN} to 5 seed records",
            "make-mech step 5",
            len(recs) >= SEED_MIN,
            f"{len(recs)} record(s) in {a.get('records_dir')}/",
            "curate seeds with the Mech's curate-record skill: one typical, one hard, one at the edge",
        )
    )
    # A converted record starts DRAFT on purpose and becomes PROPOSED once
    # curated (convert-knowledge-base step 6). That DRAFT is work left, not a fault.
    statuses: dict[str, int] = {}
    converted: dict[str, int] = {}
    for r in recs:
        data = m._yaml(r) or {}
        status = data.get("status", "unset")
        tally = converted if is_converted(data) else statuses
        tally[status] = tally.get(status, 0) + 1
    drafts = converted.pop("DRAFT", 0)
    for k, v in converted.items():
        statuses[k] = statuses.get(k, 0) + v
    if statuses:
        bad = {k: v for k, v in statuses.items() if k not in ("PROPOSED", "REVIEWED")}
        out.append(
            item(
                "Seed records marked PROPOSED until a person reviews them",
                "make-mech step 5",
                not bad,
                ", ".join(f"{v} {k}" for k, v in sorted(statuses.items())),
                "an agent-drafted record is PROPOSED",
            )
        )
    if drafts or converted:
        total = drafts + sum(converted.values())
        out.append(
            item(
                "Converted records curated to PROPOSED",
                "convert-knowledge-base step 6",
                not drafts,
                f"{drafts} of {total} converted record(s) still DRAFT",
                "curate each with the Mech's curate-record; a record whose sections are filled "
                "or explained is PROPOSED",
                status=CHECK if drafts else None,
            )
        )

    reg_path = f"registry/{m.slug}.md"
    reg = registry_front_matter(m.text(reg_path))
    if not reg:
        out.append(
            item(
                "Registry entry drafted",
                "make-mech step 6",
                False,
                f"`{reg_path}` absent or unreadable",
                "run register-mech",
            )
        )
    else:
        count = reg.get("record_count")
        ok = count == len(recs)
        out.append(
            item(
                "Registry entry up to date",
                "make-mech step 6",
                ok,
                f"`{reg_path}` says record_count {count}; the Mech has {len(recs)}",
                "run register-mech to update the counts",
                status=None if ok else CHECK,
            )
        )
    return out


class RequestsError(ValueError):
    """A requests file the audit cannot read."""


def load_requests(path: Path) -> list[dict]:
    """The requests file as a list of mappings, or a RequestsError that says what is wrong."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise RequestsError(f"not valid YAML: {exc}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise RequestsError(f"cannot be read: {exc}") from exc
    if isinstance(data, dict):
        if "requests" not in data:
            raise RequestsError(
                "a mapping with no `requests:` key; write a list, or put it under `requests:`"
            )
        data = data["requests"]
    data = data or []
    if not isinstance(data, list):
        raise RequestsError("the requests must be a list")
    reqs = []
    for i, r in enumerate(data, 1):
        if isinstance(r, str):
            r = {"feature": r}
        if not isinstance(r, dict):
            raise RequestsError(f"request {i} is {r!r}; each must be a mapping or a string")
        check = r.get("check")
        if check is not None and not isinstance(check, dict):
            raise RequestsError(f"request {i}: `check` is {check!r}; write it as a mapping, e.g. {{slot: x}}")
        for kind, arg in (check or {}).items():
            if kind in ("class", "slot", "recipe", "path") and not isinstance(arg, str):
                raise RequestsError(f"request {i}: `{kind}` takes a name, not {arg!r}")
            if kind == "contains" and not (
                isinstance(arg, dict)
                and isinstance(arg.get("path"), str)
                and isinstance(arg.get("text"), str)
            ):
                raise RequestsError(f"request {i}: `contains` takes {{path: ..., text: ...}}, not {arg!r}")
            if kind == "records" and (isinstance(arg, bool) or not isinstance(arg, int)):
                raise RequestsError(f"request {i}: `records` takes a whole number, not {arg!r}")
        reqs.append(r)
    return reqs


def from_requests(m: Mech, path: Path) -> list[Item]:
    out = []
    classes, slots, recipes = m.classes(), m.slots(), m.recipes()
    for i, r in enumerate(load_requests(path), 1):
        feature = r.get("feature") or f"request {i}"
        asked = "requested" + (f': "{r["said"]}"' if r.get("said") else "")
        check = r.get("check") or {}
        if not check:
            out.append(Item(feature, asked, CHECK, "no automatic check; look for it", ""))
            continue
        for kind, arg in check.items():
            if kind == "class":
                out.append(
                    item(
                        feature,
                        asked,
                        arg in classes,
                        f"class `{arg}` " + ("present" if arg in classes else "not in the schema"),
                        "add it to the schema",
                    )
                )
            elif kind == "slot":
                out.append(
                    item(
                        feature,
                        asked,
                        arg in slots,
                        f"slot `{arg}` " + ("present" if arg in slots else "not in the schema"),
                        "add it to the schema",
                    )
                )
            elif kind == "recipe":
                out.append(
                    item(
                        feature,
                        asked,
                        arg in recipes,
                        f"recipe `{arg}` " + ("in the justfile" if arg in recipes else "not in the justfile"),
                        "add the recipe",
                    )
                )
            elif kind == "path":
                out.append(
                    item(
                        feature,
                        asked,
                        m.exists(arg),
                        f"`{arg}` " + ("present" if m.exists(arg) else "absent"),
                        f"create `{arg}`",
                    )
                )
            elif kind == "contains":
                p, text = arg["path"], arg["text"]
                hit = text in m.text(p)
                out.append(
                    item(
                        feature,
                        asked,
                        hit,
                        f"`{p}` {'contains' if hit else 'lacks'} `{text}`",
                        f"add it to `{p}`",
                    )
                )
            elif kind == "records":
                n = len(m.records())
                out.append(
                    item(
                        feature,
                        asked,
                        n >= arg,
                        f"{n} record(s); asked for {arg}",
                        "curate more records",
                    )
                )
            else:
                out.append(Item(feature, asked, CHECK, f"unknown check `{kind}`; look for it by hand", ""))
    return out


def run_qc(m: Mech, recipe: str) -> Item:
    try:
        out = subprocess.run(["just", recipe], cwd=m.root, capture_output=True, text=True, timeout=3600)
    except FileNotFoundError:
        return Item(f"`just {recipe}` passes", "make-mech step 3", CHECK, "just is not installed", "")
    except subprocess.TimeoutExpired:
        return Item(
            f"`just {recipe}` passes",
            "make-mech step 3",
            MISSING,
            "timed out after an hour",
            f"run `just {recipe}` by hand and read where it stops",
        )
    tail = (out.stdout + out.stderr).strip().splitlines()[-3:]
    return item(
        f"`just {recipe}` passes",
        "make-mech step 3",
        out.returncode == 0,
        "passed" if out.returncode == 0 else f"exit {out.returncode}: " + " / ".join(tail),
        f"run `just {recipe}` and fix the first failure",
    )


def render(m: Mech, items: list[Item]) -> str:
    n = {s: sum(1 for i in items if i.status == s) for s in (DONE, MISSING, CHECK)}
    head = m._git("rev-parse", "--short", "HEAD")
    lines = [
        f"# Audit: {m.answers.get('mech_name', m.slug)}",
        "",
        f"`{m.root}`" + (f", at commit {head}" if head else ", not under git") + ".",
        f"{len(items)} features asked for: {n[DONE]} done, {n[MISSING]} missing, {n[CHECK]} to check.",
        "",
        "## Checklist",
        "",
    ]
    for i in items:
        lines.append(f"- {BOX[i.status]} **{i.feature}** ({i.asked}). {i.found}.")
    for status, title in ((MISSING, "Not implemented"), (CHECK, "To check")):
        group = [i for i in items if i.status == status]
        if group:
            lines += ["", f"## {title}", ""]
            for i in group:
                lines.append(f"- **{i.feature}**: {i.found}." + (f" Next: {i.fix}." if i.fix else ""))
    if not n[MISSING] and not n[CHECK]:
        lines += ["", "Every feature asked for is present."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("mech", type=Path, help="the Mech's folder")
    p.add_argument("--requests", type=Path, help="a YAML list of what the person asked for")
    p.add_argument("--qc", action="store_true", help="run `just qc` in the Mech")
    p.add_argument("--qc-full", action="store_true", help="run `just qc-full` (network)")
    p.add_argument("--json", action="store_true", help="print JSON instead of Markdown")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return 64 if e.code else 0
    root = args.mech.resolve()
    if not (root / ".copier-answers.yml").exists():
        print(f"{root} has no .copier-answers.yml: not a Mech made from mechmaker.", file=sys.stderr)
        return 2
    if args.requests and not args.requests.exists():
        print(f"No requests file at {args.requests}.", file=sys.stderr)
        return 64
    m = Mech(root)
    requested: list[Item] = []
    if args.requests:
        # Read the requests first, so a bad file stops the audit before `just qc` runs.
        try:
            requested = from_requests(m, args.requests)
        except RequestsError as exc:
            print(f"Cannot read {args.requests}: {exc}", file=sys.stderr)
            return 64
    items = from_answers(m) + from_steps(m)
    if args.qc_full:
        items.append(run_qc(m, "qc-full"))
    elif args.qc:
        items.append(run_qc(m, "qc"))
    items += requested
    if args.json:
        print(json.dumps({"mech": str(root), "items": [asdict(i) for i in items]}, indent=2))
    else:
        print(render(m, items), end="")
    return 1 if any(i.status == MISSING for i in items) else 0


if __name__ == "__main__":
    sys.exit(main())
