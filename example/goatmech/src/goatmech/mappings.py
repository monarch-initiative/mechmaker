"""The SSSOM export: every record's mappings to other identifiers, as one SSSOM mapping set.

The export calls this for the format sssom in conf/export.yaml. It writes
build/export/<slug>-mappings.sssom.tsv: SSSOM's TSV, its metadata a YAML
block of `#` lines above the table. Each item in a record's `mappings` is a
row:

  subject_id, subject_label   the record's id and name
  predicate_id                a SKOS mapping relation, such as skos:exactMatch
  predicate_modifier          Not, when the mapping is stated not to hold
  object_id, object_label     the mapped entity
  mapping_justification       how it was found, from SEMAPV
  confidence                  from 0 to 1, when the curator gave one
  see_also                    the evidence's references, as URLs where the schema's prefixes expand them
  comment                     the mapping's notes

The metadata names the set (its id is the file's address in the latest
release), its version (the latest git tag), license, title, description,
creators (ORCIDs from registry/<slug>.md) and the curie_map: every prefix the
rows use, with the URI the schema declares for it. A row whose CURIE has an
undeclared prefix fails the export, as in RDF.

The file is read back with sssom-py: it must parse, validate against the
SSSOM schema, have a prefix for every CURIE, and give back every row. sssom
is installed only when a Mech exports SSSOM.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path

import yaml

from .croissant import license_url, mech_version, registry_entry
from .export import release_url
from .paths import MECH_NAME, RECORD_CLASS, REPO_URL, SLUG

MISSING = (
    "sssom: needs sssom (sssom-py) to check the mapping set, which this Mech does not install. Run "
    "`uv add 'sssom>=0.4.17'` and `just install`, or take sssom out of conf/export.yaml."
)
NO_SLOT = (
    f"sssom: {RECORD_CLASS} has no `mappings` slot, so there is nothing to export. Add the Mapping "
    "class and its enums (see the Output formats page of mechmaker's docs), or take sssom out of "
    "conf/export.yaml."
)
FILE = f"{SLUG}-mappings.sssom.tsv"
# The columns, in SSSOM's order. A column no row fills is left out, but for the required four.
COLUMNS = ["subject_id", "subject_label", "predicate_id", "predicate_modifier", "object_id", "object_label",
           "mapping_justification", "confidence", "see_also", "comment"]
REQUIRED = {"subject_id", "predicate_id", "object_id", "mapping_justification"}
CURIE_COLUMNS = ("subject_id", "predicate_id", "object_id", "mapping_justification")


def prefix_map(sv) -> dict[str, str]:
    return {p: v.prefix_reference for p, v in sv.schema.prefixes.items()}


def expand(curie: str, prefixes: dict[str, str]) -> str:
    """The CURIE as a URL, when its prefix is declared; else as it is."""
    prefix, _, local = curie.partition(":")
    return prefixes[prefix] + local if local and prefix in prefixes else curie


def one_line(value) -> str:
    """The text with each run of whitespace (tabs, newlines) as one space: one cell, one row."""
    return " ".join(str(value).split()) if value else ""


def rows(sv, records: list[dict]) -> tuple[list[dict], list[str]]:
    """One row per mapping in the records, and the problems found on the way."""
    prefixes = prefix_map(sv)
    out: list[dict] = []
    problems: list[str] = []
    seen: set[tuple] = set()
    for rec in records:
        for i, m in enumerate(rec.get("mappings") or []):
            where = f"{rec.get('id')} mappings[{i}]"
            if not isinstance(m, dict):
                problems.append(f"sssom: {where} is not a mapping")
                continue
            row = {
                "subject_id": str(rec.get("id")),
                "subject_label": one_line(rec.get("name")),
                "predicate_id": m.get("predicate_id") or "",
                "predicate_modifier": m.get("predicate_modifier") or "",
                "object_id": str(m.get("object_id") or ""),
                "object_label": one_line(m.get("object_label")),
                "mapping_justification": m.get("mapping_justification") or "",
                "confidence": "" if m.get("confidence") is None else str(m["confidence"]),
                "see_also": "|".join(dict.fromkeys(expand(str(e["reference"]), prefixes)
                                                   for e in m.get("evidence") or []
                                                   if isinstance(e, dict) and e.get("reference"))),
                "comment": one_line(m.get("notes")),
            }
            missing = sorted(c for c in REQUIRED if not row[c])
            if missing:
                problems.append(f"sssom: {where} has no {', '.join(missing)}")
                continue
            undeclared = sorted({row[c].partition(":")[0] for c in CURIE_COLUMNS
                                 if row[c].partition(":")[0] not in prefixes})
            if undeclared:
                problems.append(f"sssom: {where} uses prefix(es) the schema does not declare: "
                                f"{', '.join(undeclared)}. Declare each with its full URI in `prefixes`.")
                continue
            if row["subject_id"] == row["object_id"]:
                problems.append(f"sssom: {where} maps the record to itself")
                continue
            key = (row["subject_id"], row["predicate_id"], row["predicate_modifier"], row["object_id"])
            if key in seen:
                problems.append(f"sssom: {where} repeats a mapping the record already states")
                continue
            seen.add(key)
            out.append(row)
    return out, problems


def metadata(sv, table: list[dict]) -> dict:
    """The mapping set's metadata: what it is, and a curie_map of every prefix the rows use."""
    reg = registry_entry()
    prefixes = prefix_map(sv)
    used = {row[c].partition(":")[0] for row in table for c in CURIE_COLUMNS}
    meta: dict = {"curie_map": {p: prefixes[p] for p in sorted(used)}}
    # Those with an ORCID first, so creator_label[i] is the person creator_id[i] names.
    people = sorted((c for c in reg.get("contacts") or [] if c.get("label")),
                    key=lambda c: not c.get("orcid"))
    orcids = [c["orcid"] for c in people if c.get("orcid")]
    if orcids:
        meta["curie_map"]["orcid"] = "https://orcid.org/"
    meta.update({
        "mapping_set_id": release_url(FILE),
        "mapping_set_version": mech_version(),
        "mapping_set_title": f"{reg.get('name') or MECH_NAME} mappings",
        "mapping_set_description": (
            f"Each {RECORD_CLASS} record's mappings to identifiers elsewhere, as curated in "
            f"{reg.get('name') or MECH_NAME} ({reg.get('repository') or REPO_URL})."),
        "license": license_url(sv, reg),
        "creator_id": [f"orcid:{o}" for o in orcids],
        "creator_label": [c["label"] for c in people],
        "mapping_provider": reg.get("repository") or REPO_URL,
    })
    return {k: v for k, v in meta.items() if v not in ([], None, "")}


def has_slot(sv) -> bool:
    """Whether the record class has the `mappings` the export reads."""
    return "mappings" in {s.name for s in sv.class_induced_slots(RECORD_CLASS)}


def write(sv, records: list[dict], out: Path) -> tuple[int, list[str]]:
    """Write the mapping set. (rows written, problems)"""
    if not has_slot(sv):
        return 0, [NO_SLOT]
    table, problems = rows(sv, records)
    columns = [c for c in COLUMNS if c in REQUIRED or any(row[c] for row in table)]
    head = yaml.safe_dump(metadata(sv, table), sort_keys=False, allow_unicode=True, width=1000)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter="\t", lineterminator="\n")
    w.writerow(columns)
    w.writerows([row[c] for c in columns] for row in table)
    out.write_text("".join(f"#{line}\n" for line in head.splitlines()) + buf.getvalue(), encoding="utf-8")
    return len(table), problems


def check(out: Path, n: int) -> list[str]:
    """Parse and validate the file with sssom-py: schema, prefixes, CURIEs, and every row back.

    Raises ModuleNotFoundError (name sssom) when sssom is not installed.
    """
    import importlib.util

    if importlib.util.find_spec("sssom") is None:
        raise ModuleNotFoundError("No module named 'sssom'", name="sssom")
    from sssom.constants import SchemaValidationType
    from sssom.parsers import parse_sssom_table
    from sssom.validators import validate

    logging.getLogger("sssom").setLevel(logging.ERROR)
    try:
        msdf = parse_sssom_table(out)
    except Exception as exc:  # sssom-py raises many kinds; any of them means the file is not SSSOM
        return [f"{out.name}: sssom-py cannot read it: {exc}"]
    problems = []
    got = len(msdf.df)
    if got != n:
        problems.append(f"{out.name}: sssom-py reads {got} mapping(s), expected {n}")
    if n:  # sssom-py validates the mappings; a set with none has nothing to validate
        kinds = [SchemaValidationType.JsonSchema, SchemaValidationType.PrefixMapCompleteness,
                 SchemaValidationType.StrictCurieFormat]
        reports = validate(msdf, kinds, fail_on_error=False)
        for kind, report in reports.items():
            for result in report.results:
                problems.append(f"{out.name}: {kind.value}: {result.message}")
    return problems
