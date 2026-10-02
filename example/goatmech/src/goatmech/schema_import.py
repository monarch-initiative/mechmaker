"""Start the Mech's schema from an existing one.

    python -m <slug>.schema_import SOURCE --record-class CLASS                 # dry run, copy mode
    python -m <slug>.schema_import SOURCE --record-class CLASS --mode reference
    python -m <slug>.schema_import SOURCE --from json-schema --record-class CLASS
    ... --rename SourceName=NewName ... --apply

SOURCE is a LinkML schema, as a path or a URL; its local imports come with
it. Other formats go through schema-automator first (--from), run by uvx in
its own environment, so the Mech never carries its dependencies.

CLASS is the source's class for one record. It becomes the Mech's record
class: the Mech's own name for it stays, and it gains the source class's
slots. Every decision is printed: what was taken, what clashed, what won.

copy       The source's classes, slots, enums and types are copied into the
           Mech's schema, which then owns them. Each keeps its source URI as
           an explicit class_uri, slot_uri or enum_uri, so RDF exports mean
           what the source meant. Where a name is in both, the Mech's core
           slots (id, name, description, notes, synonyms) win; any other
           clash stops the import until --rename gives the source's element
           a new name.
reference  The source file is stored unchanged next to the Mech's schema and
           imported, and the record class extends CLASS (is_a). Upstream
           changes come in by replacing that file. LinkML cannot merge a
           name defined in both schemas, so the Mech drops its own copy of a
           shared core slot and uses the source's. A clash on anything the
           Mech's checks depend on (evidence, quotes, terms, history) stops
           the import: use copy mode.

Both record the source, its version and its SHA-256 in the schema's
annotations, and check that the result loads, merges and generates a JSON
Schema for the record class. Nothing is written without --apply. Afterwards,
update tests/data/example_record.yaml and docs/DOMAIN.md, and run just qc.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

import yaml
from ruamel.yaml import YAML

from .paths import RECORD_CLASS, SCHEMA_DIR, SCHEMA_PATH

# Slots the Mech defines that a source may define too, where one definition
# can stand for both.
CORE = {"id", "name", "description", "notes", "synonyms"}
# Elements the Mech's checks depend on. A source may not redefine them in
# reference mode; in copy mode the source's element must be renamed.
PROTECTED_SLOTS = {
    "label", "status", "record_term", "preferred_term", "term", "mechanisms", "downstream", "target",
    "evidence", "description_evidence", "datasets", "discussions", "reference", "reference_title",
    "supports", "evidence_source", "snippet", "explanation", "creation_date", "updated_date",
    "curation_history", "timestamp", "curator", "llm_assisted", "model", "action",
}
SCHEMAUTO = ["uvx", "--quiet", "--python", "3.13", "--from", "schema-automator==0.5.7", "schemauto"]
# --from FORMAT: the schema-automator command that turns it into LinkML.
CONVERTERS = {
    "json-schema": "import-json-schema",
    "owl": "import-owl",
    "rdfs": "import-rdfs",
    "xsd": "import-xsd",
    "frictionless": "import-frictionless",
    "tsv": "generalize-tsv",
    "json": "generalize-json",
}
ANNOTATION = "imported_schema"


class Problem(Exception):
    """A clash or a malformed source: the import stops and says why."""


# ---------------------------------------------------------------- reading


def fetch(source: str, workdir: Path) -> Path:
    """A local copy of SOURCE, and of any local schemas it imports beside it."""
    if not re.match(r"^https?://", source):
        path = Path(source).resolve()
        if not path.exists():
            raise Problem(f"{source} does not exist")
        return path
    name = Path(urllib.parse.urlparse(source).path).name or "source.yaml"
    out = workdir / name
    with urllib.request.urlopen(source, timeout=120) as resp:
        out.write_bytes(resp.read())
    if out.suffix in (".yaml", ".yml"):
        doc = yaml.safe_load(out.read_text()) or {}
        base = source.rsplit("/", 1)[0]
        for imp in doc.get("imports") or []:
            if ":" in str(imp):
                continue  # linkml:types and other prefixed imports resolve on their own
            target = workdir / f"{imp}.yaml"
            target.parent.mkdir(parents=True, exist_ok=True)
            with urllib.request.urlopen(f"{base}/{imp}.yaml", timeout=120) as resp:
                target.write_bytes(resp.read())
    return out


def convert(path: Path, fmt: str, workdir: Path, extra: list[str]) -> Path:
    """A LinkML schema from another format, through schema-automator."""
    out = workdir / f"{path.stem}.linkml.yaml"
    cmd = SCHEMAUTO + [CONVERTERS[fmt], str(path), "-o", str(out), *extra]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 or not out.exists():
        last = (result.stderr.strip().splitlines() or ["no output"])[-1]
        raise Problem(f"schema-automator {CONVERTERS[fmt]} failed: {last}")
    return out


def source_docs(path: Path) -> list[tuple[Path, dict]]:
    """The source schema and the local schemas it imports, depth first."""
    seen: dict[Path, dict] = {}

    def visit(p: Path) -> None:
        if p in seen:
            return
        doc = yaml.safe_load(p.read_text()) or {}
        seen[p] = doc
        for imp in doc.get("imports") or []:
            if ":" not in str(imp):
                visit((p.parent / f"{imp}.yaml").resolve())

    visit(path.resolve())
    return list(seen.items())


def version_of(doc: dict, path: Path) -> dict:
    return {
        "source": str(path),
        "name": str(doc.get("name", path.stem)),
        "version": str(doc.get("version", "unversioned")),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


# ---------------------------------------------------------------- the Mech side


def _yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    y.indent(mapping=2, sequence=4, offset=2)
    return y


def mech_names() -> dict[str, set[str]]:
    """Every class, slot, enum and type name the Mech's schema has, imports included."""
    from linkml_runtime.utils.schemaview import SchemaView

    sv = SchemaView(str(SCHEMA_PATH))
    return {"classes": set(sv.all_classes()), "slots": set(sv.all_slots()),
            "enums": set(sv.all_enums()), "types": set(sv.all_types())}


def uri(doc: dict, name: str, kind: str) -> str:
    """The URI LinkML gives an element by default: the schema's prefix and the element's cleaned name."""
    from linkml_runtime.utils.formatutils import camelcase, underscore

    local = underscore(name) if kind == "slots" else camelcase(name)
    return f"{doc.get('default_prefix') or doc.get('name')}:{local}"


# ---------------------------------------------------------------- copy mode


def plan_copy(docs: list[tuple[Path, dict]], record_class: str, renames: dict[str, str],
              mech: dict, report: list[str], keep_uris: bool = True) -> dict:
    """The elements to add, with the record class folded in. Raises Problem on an unresolved clash.

    keep_uris pins each element to its source URI. A schema converted from
    another format has only a namespace the converter made up, so its
    elements take the Mech's own instead.
    """
    out: dict = {"prefixes": {}, "classes": {}, "slots": {}, "enums": {}, "types": {}, "record": None}
    clashes = []
    for _, doc in docs:
        for p, u in (doc.get("prefixes") or {}).items():
            if not keep_uris and p == doc.get("default_prefix"):
                continue
            out["prefixes"][p] = u["prefix_reference"] if isinstance(u, dict) else u
        kinds = (("classes", "class_uri"), ("slots", "slot_uri"), ("enums", "enum_uri"), ("types", None))
        for kind, uri_key in kinds:
            for name, body in (doc.get(kind) or {}).items():
                body = copy.deepcopy(body) or {}
                if kind == "classes" and name == record_class:
                    out["record"] = (doc, body)
                    continue
                new = renames.get(name, name)
                if keep_uris and uri_key and uri_key not in body:
                    body[uri_key] = uri(doc, name, kind)  # keep the source's meaning under a Mech name
                if kind == "classes":
                    body.pop("tree_root", None)
                    for attr, adef in (body.get("attributes") or {}).items():
                        if keep_uris and isinstance(adef, dict) and "slot_uri" not in adef:
                            adef["slot_uri"] = uri(doc, attr, "slots")
                if new in mech[kind]:
                    if kind == "slots" and new in CORE and new == name:
                        report.append(f"slot {name}: the Mech's definition is kept, the source's set aside")
                        continue
                    clashes.append(f"{kind[:-1]} {name!r} is also the Mech's")
                    continue
                if new != name:
                    report.append(f"{kind[:-1]} {name} is renamed {new}")
                out[kind][new] = body
    if out["record"] is None:
        raise Problem(f"the source has no class {record_class!r}")
    if clashes:
        raise Problem("names the source shares with the Mech: " + "; ".join(clashes)
                      + ". Give each a new name with --rename OLD=NEW.")
    retarget = {record_class: RECORD_CLASS, **renames}

    def fix_refs(body: dict) -> None:
        for key in ("range", "is_a"):
            if body.get(key) in retarget:
                body[key] = retarget[body[key]]
        if body.get("mixins"):
            body["mixins"] = [retarget.get(m, m) for m in body["mixins"]]
        if body.get("slots"):
            body["slots"] = [renames.get(x, x) for x in body["slots"]]
        if body.get("slot_usage"):
            body["slot_usage"] = {renames.get(k, k): v for k, v in body["slot_usage"].items()}
        for sub in ("attributes", "slot_usage"):
            for v in (body.get(sub) or {}).values():
                if isinstance(v, dict):
                    fix_refs(v)

    for kind in ("classes", "slots", "enums"):
        for body in out[kind].values():
            fix_refs(body)
    doc, rbody = out["record"]
    fix_refs(rbody)
    out["keep_uris"] = keep_uris
    return out


def apply_copy(schema, plan: dict, record_class: str, renames: dict[str, str], report: list[str]) -> None:
    """Fold the plan into the Mech's schema (a ruamel tree), in place."""
    prefixes = schema.setdefault("prefixes", {})
    for p, u in plan["prefixes"].items():
        have = prefixes.get(p)
        have = have.get("prefix_reference") if isinstance(have, dict) else have
        if have and have != u:
            raise Problem(f"prefix {p} is {have} in the Mech and {u} in the source")
        if not have:
            prefixes[p] = u
    for kind in ("classes", "slots", "enums", "types"):
        if plan[kind]:
            section = schema.setdefault(kind, {})
            for name, body in plan[kind].items():
                section[name] = body
            report.append(f"{len(plan[kind])} {kind} copied")
    doc, src = plan["record"]
    target = schema["classes"][RECORD_CLASS]
    slots = target.setdefault("slots", [])
    for s in src.get("slots") or []:
        s = renames.get(s, s)
        if s not in slots:
            slots.append(s)
    for key in ("attributes", "slot_usage"):
        for name, body in (src.get(key) or {}).items():
            if key == "attributes" and name in CORE | PROTECTED_SLOTS:
                report.append(f"attribute {record_class}.{name}: the Mech's slot is kept")
                continue
            keep = plan["keep_uris"] and key == "attributes" and isinstance(body, dict)
            if keep and "slot_uri" not in body:
                body["slot_uri"] = uri(doc, name, "slots")
            target.setdefault(key, {})[name] = body
    for key in ("is_a", "mixins"):
        if src.get(key):
            target[key] = src[key]
    if plan["keep_uris"] and "class_uri" not in target:
        target["class_uri"] = uri(doc, record_class, "classes")
    ident = next((s for s, b in (plan["slots"].items()) if isinstance(b, dict) and b.get("identifier")
                  and s in (src.get("slots") or [])), None)
    if ident and ident != "id":
        plan["slots"][ident]["identifier"] = False
        schema["slots"][ident]["identifier"] = False
        report.append(f"slot {ident} was {record_class}'s identifier; records are keyed by id, "
                      f"and {ident} is kept as a plain slot")
    report.append(f"{record_class} is folded into {RECORD_CLASS}: {len(slots)} slots")


# ---------------------------------------------------------------- reference mode


def apply_reference(schema, docs: list[tuple[Path, dict]], record_class: str, mech: dict,
                    report: list[str]) -> list[tuple[Path, str]]:
    """Import the source unchanged; returns the files to store beside the schema."""
    names = {k: set() for k in ("classes", "slots", "enums", "types")}
    for _, doc in docs:
        for kind in names:
            names[kind] |= set((doc.get(kind) or {}).keys())
        for c in (doc.get("classes") or {}).values():
            names["slots"] |= set(((c or {}).get("attributes") or {}).keys())
    if record_class not in names["classes"]:
        raise Problem(f"the source has no class {record_class!r}")
    own = schema.get("slots") or {}
    blocked = sorted(n for n in names["slots"] & mech["slots"] if n in PROTECTED_SLOTS)
    blocked += sorted(f"{k[:-1]} {n}" for k in ("classes", "enums", "types") for n in names[k] & mech[k])
    if blocked:
        raise Problem("the source defines names the Mech's checks depend on: " + ", ".join(blocked)
                      + ". LinkML cannot merge a name defined twice; use --mode copy, which can rename.")
    for n in sorted(names["slots"] & set(own)):
        del own[n]
        report.append(f"slot {n}: the Mech's definition is dropped; the source's is used")
    unknown = sorted((names["slots"] & mech["slots"]) - set(schema.get("slots") or {}) - CORE)
    if unknown:
        raise Problem(f"the source redefines slots the Mech imports: {', '.join(unknown)}; use --mode copy")
    main = docs[0][1]
    imports = schema.setdefault("imports", [])
    if main["name"] in (str(i) for i in imports):
        raise Problem(f"the Mech already imports {main['name']}")
    imports.append(main["name"])
    target = schema["classes"][RECORD_CLASS]
    if target.get("is_a"):
        raise Problem(f"{RECORD_CLASS} already has is_a {target['is_a']}")
    target.insert(0, "is_a", record_class)
    from linkml_runtime.utils.schemaview import SchemaView

    found = SchemaView(str(docs[0][0])).get_identifier_slot(record_class)
    ident = str(found.name) if found is not None else None  # a plain str, which ruamel can write
    if ident and ident != "id":
        # Records are keyed by id. The source file stays as it is, so the
        # source's own identifier is made a plain, optional slot here.
        target.setdefault("slot_usage", {})[ident] = {"identifier": False, "required": False}
        report.append(f"slot {ident} is {record_class}'s identifier; in {RECORD_CLASS} records are "
                      f"keyed by id, and {ident} is a plain, optional slot")
    roots = [n for _, d in docs for n, c in (d.get("classes") or {}).items() if (c or {}).get("tree_root")]
    if roots:
        report.append(f"the source marks {', '.join(roots)} as tree_root; "
                      f"{RECORD_CLASS} stays the Mech's record")
    report.append(f"{RECORD_CLASS} is_a {record_class}; schema {main['name']} imported unchanged")
    files = [(docs[0][0], f"{main['name']}.yaml")]
    base = docs[0][0].parent
    for p, _ in docs[1:]:
        files.append((p, str(p.relative_to(base))))
    return files


# ---------------------------------------------------------------- checking


def check(schema_text: str, extra_files: list[tuple[Path, str]]) -> list[str]:
    """Load, merge and generate a JSON Schema for the record class, in a scratch copy of the schema dir."""
    from linkml.generators.jsonschemagen import JsonSchemaGenerator
    from linkml_runtime.utils.schemaview import SchemaView

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for f in SCHEMA_DIR.glob("*.yaml"):
            shutil.copy(f, d / f.name)
        for src, name in extra_files:
            (d / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, d / name)
        (d / SCHEMA_PATH.name).write_text(schema_text)
        try:
            sv = SchemaView(str(d / SCHEMA_PATH.name))
            sv.merge_imports()
            if RECORD_CLASS not in sv.all_classes():
                return [f"{RECORD_CLASS} is missing after the import"]
            JsonSchemaGenerator(str(d / SCHEMA_PATH.name), top_class=RECORD_CLASS).serialize()
        except Exception as exc:  # any failure to load or merge is the answer
            return [f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="a schema file or URL")
    parser.add_argument("--record-class", required=True, help="the source's class for one record")
    parser.add_argument("--mode", choices=("copy", "reference"), default="copy")
    parser.add_argument("--from", dest="fmt", choices=["linkml", *CONVERTERS], default="linkml",
                        help="the source's format; not linkml goes through schema-automator")
    parser.add_argument("--rename", action="append", default=[], metavar="OLD=NEW",
                        help="copy mode: give a source element a new name")
    parser.add_argument("--apply", action="store_true", help="write the schema")
    args, extra = parser.parse_known_args(argv)
    bad = [r for r in args.rename if "=" not in r]
    if bad:
        parser.error(f"--rename takes OLD=NEW, not {', '.join(bad)}")
    renames = dict(r.split("=", 1) for r in args.rename)

    report: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        try:
            path = fetch(args.source, work)
            if args.fmt != "linkml":
                path = convert(path, args.fmt, work, [a for a in extra if a != "--"])
                report.append(f"converted from {args.fmt} with schema-automator; compare its constraints "
                              "with the original, since a conversion can drop some (patterns, for one)")
                if args.mode == "reference":
                    report.append("note: a converted schema is a snapshot; copy mode usually suits it better")
            docs = source_docs(path)
            y = _yaml()
            schema = y.load(SCHEMA_PATH.read_text())
            mech = mech_names()
            files: list[tuple[Path, str]] = []
            if args.mode == "copy":
                plan = plan_copy(docs, args.record_class, renames, mech, report,
                                 keep_uris=args.fmt == "linkml")
                apply_copy(schema, plan, args.record_class, renames, report)
            else:
                files = apply_reference(schema, docs, args.record_class, mech, report)
            note = version_of(docs[0][1], docs[0][0])
            note["source"] = args.source
            note["mode"] = args.mode
            note["record_class"] = args.record_class
            schema.setdefault("annotations", {})[ANNOTATION] = (
                " ".join(f"{k}={v}" for k, v in note.items()))
            buf = io.StringIO()
            y.dump(schema, buf)
            text = buf.getvalue()
            problems = check(text, files)
        except Problem as exc:
            print(f"ERROR: {exc}")
            print("Nothing was written.")
            return 1
        for line in report:
            print(f"  {line}")
        print(f"  source {note['name']} {note['version']}, sha256 {note['sha256'][:12]}")
        if problems:
            for p in problems:
                print(f"ERROR: the result does not load: {p}")
            print("Nothing was written.")
            return 1
        if not args.apply:
            print(f"\n# dry run; the result loads and validates. Pass --apply to write {SCHEMA_PATH.name}"
                  + (f" and {len(files)} source file(s)" if files else "") + ".")
            return 0
        for src, name in files:
            (SCHEMA_DIR / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, SCHEMA_DIR / name)
        SCHEMA_PATH.write_text(text)
    print(f"\nWrote {SCHEMA_PATH.name}" + (f" and {', '.join(n for _, n in files)}" if files else "")
          + ". Next: update tests/data/example_record.yaml and docs/DOMAIN.md, then run just qc.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
