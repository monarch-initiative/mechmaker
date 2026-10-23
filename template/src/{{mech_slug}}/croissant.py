"""Croissant metadata for the export: what the Mech's files hold, and where its data came from.

    <slug>-croissant.json   Croissant 1.1 (MLCommons), JSON-LD

Croissant is not a data format: it describes the other files `just export`
writes, so it is written last, beside them. It says:

- what the dataset is: name, description, version, license, creators and a
  citation, read from registry/<slug>.md (the schema and paths.py when that
  is missing), and how it was curated, in Croissant's Responsible AI terms;
- every file, with its size and sha256. Each file's contentUrl is its name:
  the metadata sits in build/export/ and in each release with the files;
- the records, field by field (RecordSets): the per-class tables (CSV, TSV
  or Parquet, as gen-sqltables lays them out, linked by their foreign keys),
  else the flat CSV or TSV, else the JSON Lines records;
- where the data came from, in PROV-O: each structured ingest as locked in
  conf/ingests.lock.yaml (release, file checksums, upstream sources), each
  ontology the records bind, and registry/<slug>.md's data_sources; and
  every work the records cite as evidence, as schema.org citations.

The file is read back with MLCommons' mlcroissant: it must validate, and
every RecordSet must load (which checks each file's sha256) with the rows
the export wrote. mlcroissant is installed only when a Mech exports Croissant.
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import yaml

from .paths import MECH_NAME, RECORD_CLASS, REPO_ROOT, REPO_URL, SLUG

CONFORMS_TO = "http://mlcommons.org/croissant/1.1"
# The context of Croissant 1.1's own examples, as mlcroissant writes it, with PROV-O.
# Not the spec's appendix: that one uses http://schema.org/, which mlcroissant rejects.
CONTEXT = {
    "@language": "en",
    "@vocab": "https://schema.org/",
    "arrayShape": "cr:arrayShape",
    "citeAs": "cr:citeAs",
    "column": "cr:column",
    "conformsTo": "dct:conformsTo",
    "containedIn": "cr:containedIn",
    "cr": "http://mlcommons.org/croissant/",
    "rai": "http://mlcommons.org/croissant/RAI/",
    "data": {"@id": "cr:data", "@type": "@json"},
    "dataType": {"@id": "cr:dataType", "@type": "@vocab"},
    "dct": "http://purl.org/dc/terms/",
    "equivalentProperty": "cr:equivalentProperty",
    "examples": {"@id": "cr:examples", "@type": "@json"},
    "extract": "cr:extract",
    "field": "cr:field",
    "fileProperty": "cr:fileProperty",
    "fileObject": "cr:fileObject",
    "fileSet": "cr:fileSet",
    "format": "cr:format",
    "includes": "cr:includes",
    "isArray": "cr:isArray",
    "isLiveDataset": "cr:isLiveDataset",
    "jsonPath": "cr:jsonPath",
    "key": "cr:key",
    "md5": "cr:md5",
    "parentField": "cr:parentField",
    "path": "cr:path",
    "prov": "http://www.w3.org/ns/prov#",
    "recordSet": "cr:recordSet",
    "references": "cr:references",
    "regex": "cr:regex",
    "repeated": "cr:repeated",
    "replace": "cr:replace",
    "samplingRate": "cr:samplingRate",
    "sc": "https://schema.org/",
    "separator": "cr:separator",
    "source": "cr:source",
    "subField": "cr:subField",
    "transform": "cr:transform",
}
MISSING = (
    "croissant: needs mlcroissant to check the metadata, which this Mech does not install. Run "
    "`uv add 'mlcroissant>=1.1.1'` and `just install`, or take croissant out of conf/export.yaml."
)
REGISTRY = REPO_ROOT / "registry" / f"{SLUG}.md"
INGEST_LOCK = REPO_ROOT / "conf" / "ingests.lock.yaml"
OAK_CONFIG = REPO_ROOT / "conf" / "oak_config.yaml"
# Media types: Croissant's own where it names one (mlcroissant reads those), else IANA's.
ENCODINGS = {
    ".zip": "application/zip",
    ".json": "application/json",
    ".jsonl": "application/jsonlines",
    ".jsonld": "application/ld+json",
    ".ttl": "text/turtle",
    ".sqlite": "application/vnd.sqlite3",
    ".duckdb": "application/x-duckdb",
    ".sql": "application/sql",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".parquet": "application/x-parquet",
}
LICENSES = {
    "CC-BY-4.0": "https://creativecommons.org/licenses/by/4.0/",
    "CC0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/",
}
INFORES = "https://w3id.org/information-resource-registry/"


# ---------------------------------------------------------------- the dataset


def registry_entry() -> dict:
    """registry/<slug>.md's front matter; empty when there is none."""
    if not REGISTRY.exists():
        return {}
    parts = REGISTRY.read_text(encoding="utf-8").split("---\n")
    return (yaml.safe_load(parts[1]) or {}) if len(parts) > 2 else {}


def license_url(sv, reg: dict) -> str | None:
    """The data license as a URL: the registry entry's, else the schema's; None when neither has one."""
    if (reg.get("license") or {}).get("id"):
        return reg["license"]["id"]
    lic = sv.schema.license
    return LICENSES.get(lic, f"https://spdx.org/licenses/{lic}") if lic else None


def mech_version() -> str:
    """The installed package's version: the latest git tag, through uv-dynamic-versioning."""
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version(SLUG)
    except PackageNotFoundError:
        return "0.0.0"


def creators(reg: dict) -> list[dict]:
    people = []
    for c in reg.get("contacts") or []:
        if not c.get("label"):
            continue
        kind = "sc:Person" if c.get("category", "Individual") == "Individual" else "sc:Organization"
        person = {"@type": kind, "name": c["label"]}
        if c.get("orcid"):
            person["@id"] = f"https://orcid.org/{c['orcid']}"
        people.append(person)
    return people or [{"@type": "sc:Organization", "name": MECH_NAME, "url": REPO_URL}]


def cite_as(name: str, people: list[dict], year: str, url: str, version: str) -> str:
    """A BibTeX entry. Built by joining: doubled braces read as unrendered Jinja to the template's tests."""
    fields = {"title": name, "author": " and ".join(p["name"] for p in people), "year": year,
              "version": version, "url": url}
    body = ",\n".join(f"  {k} = " + "{" + v + "}" for k, v in fields.items())
    return "@misc{" + SLUG + ",\n" + body + "\n}"


def responsible_ai(reg: dict, ingests: bool) -> dict:
    """How the records were made, in Croissant's RAI vocabulary, from the registry's curation block."""
    curation = reg.get("curation") or {}
    kinds = ["Secondary Data analysis"] + (["Software Collection"] if ingests else [])
    out = {"rai:dataCollectionType": kinds}
    if curation.get("evidence_policy"):
        how = "Records are curated by AI agents"
        if curation.get("human_review"):
            how += f", reviewed by people ({str(curation['human_review']).replace('_', ' ')})"
        out["rai:dataCollection"] = f"{how}. {curation['evidence_policy'].strip()}"
    if curation.get("agents"):
        out["rai:machineAnnotationTools"] = list(curation["agents"])
    if reg.get("disclaimer"):
        out["rai:dataLimitations"] = reg["disclaimer"].strip()
    return out


# ---------------------------------------------------------------- sources


def entity(iri: str | None, label: str, **extra) -> dict:
    out = {"@type": "prov:Entity", "prov:label": label}
    if iri:
        out["@id"] = iri
    return {**out, **{k: v for k, v in extra.items() if v not in (None, [], {})}}


def infores_iri(curie) -> str | None:
    """An infores: CURIE as its Information Resource Registry IRI."""
    curie = str(curie or "")
    return INFORES + curie.split(":", 1)[1] if curie.startswith("infores:") else None


def ingest_sources() -> list[dict]:
    """Each locked ingest: the release or Koza run, its files' checksums, and the sources upstream of it."""
    if not INGEST_LOCK.exists():
        return []
    lock = (yaml.safe_load(INGEST_LOCK.read_text(encoding="utf-8")) or {}).get("ingests") or {}
    out = []
    for name, e in sorted(lock.items()):
        upstream = [entity(infores_iri(s.get("id")), s.get("id", "unknown source"),
                           **{"version": s.get("version"), "prov:generatedAtTime": s.get("retrieved_at")})
                    for s in e.get("sources") or [] if isinstance(s, dict)]
        if e.get("kind") == "release":
            base = f"https://github.com/{e['repo']}/releases"
            files = [entity(f"{base}/download/{e['release']}/{f}", f, sha256=v.get("sha256"))
                     for f, v in sorted((e.get("files") or {}).items())]
            out.append(entity(f"{base}/tag/{e['release']}", f"{name} ingest ({e['repo']} {e['release']})",
                              version=e.get("build_version"),
                              **{"prov:hadMember": files, "prov:wasDerivedFrom": upstream}))
        elif e.get("kind") == "koza":
            files = [entity(v.get("url"), f, sha256=v.get("sha256"))
                     for f, v in sorted((e.get("downloads") or {}).items())]
            koza = (e.get("tools") or {}).get("koza")
            out.append(entity(f"{REPO_URL}/tree/main/{e['path']}",
                              f"{name} ingest ({e['path']}{f', koza {koza}' if koza else ''})",
                              **{"prov:wasDerivedFrom": files + upstream}))
    return out


def ontology_sources(sv) -> list[dict]:
    """Each ontology the records bind terms from, as conf/oak_config.yaml's adapters reach it.

    An OBO Foundry ontology (ols:<name>, sqlite:obo:<name>) is named by its PURL; a file in the
    repository, or a BioPortal ontology, by where it is; anything else by its prefix's URI.
    """
    if not OAK_CONFIG.exists():
        return []
    adapters = (yaml.safe_load(OAK_CONFIG.read_text(encoding="utf-8")) or {}).get("ontology_adapters") or {}
    prefixes = {p.lower(): v.prefix_reference for p, v in sv.schema.prefixes.items()}
    out = []
    for p, adapter in sorted(adapters.items()):
        if not adapter or p == SLUG:
            continue
        kind, _, rest = str(adapter).partition(":")
        iri, where = prefixes.get(p.lower()), None
        if kind == "ols":
            iri = f"http://purl.obolibrary.org/obo/{rest}.owl"
            where = f"https://www.ebi.ac.uk/ols4/ontologies/{rest}"
        elif kind == "sqlite" and rest.startswith("obo:"):
            iri = f"http://purl.obolibrary.org/obo/{rest[4:]}.owl"
        elif kind == "bioportal":
            where = f"https://bioportal.bioontology.org/ontologies/{rest}"
        elif (REPO_ROOT / rest).exists():
            where = f"{REPO_URL}/blob/main/{rest}"
        out.append(entity(iri, f"{p} ontology", **{"prov:atLocation": where}))
    return out


def registry_sources(reg: dict) -> dict[str, list[dict]]:
    """registry/<slug>.md's data_sources, under the PROV relation each names."""
    out: dict[str, list[dict]] = {}
    for s in reg.get("data_sources") or []:
        if not s.get("name"):
            continue
        rel = s.get("relation_type") or ""
        rel = rel if rel.startswith("prov:") else "prov:wasDerivedFrom"
        out.setdefault(rel, []).append(entity(s.get("url"), s["name"], description=s.get("description")))
    return out


def references(records: list[dict]) -> list[str]:
    """Every reference the records cite, in order of first use."""
    seen: dict[str, None] = {}

    def walk(obj):
        if isinstance(obj, dict):
            if isinstance(obj.get("reference"), str):
                seen.setdefault(obj["reference"], None)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(records)
    return list(seen)


def citations(sv, refs: list[str]) -> list[dict]:
    """The cited works, each by its IRI where the schema's prefixes expand it, titled from the cache."""
    from .validate import cached_title

    prefixes = {p.lower(): v.prefix_reference for p, v in sv.schema.prefixes.items()}
    out = []
    for ref in refs:
        prefix, _, local = ref.partition(":")
        work = {"@type": "sc:CreativeWork", "identifier": ref}
        if prefix.lower() == "url":
            work["url"] = local
        elif prefix.lower() in prefixes:
            work["url"] = prefixes[prefix.lower()] + local
        title = cached_title(ref)
        if title and title != local:  # a url: reference's cached title is its URL
            work["name"] = title
        out.append(work)
    return out


# ---------------------------------------------------------------- files and records


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def file_object(path: Path) -> dict:
    return {"@type": "cr:FileObject", "@id": path.name, "name": path.name, "contentUrl": path.name,
            "encodingFormat": ENCODINGS.get(path.suffix, "application/octet-stream"),
            "contentSize": f"{path.stat().st_size} B", "sha256": sha256(path)}


def member(container: str, name: str) -> dict:
    return {"@type": "cr:FileObject", "@id": f"{container}/{name}", "name": name, "contentUrl": name,
            "containedIn": {"@id": container}, "encodingFormat": ENCODINGS[Path(name).suffix]}


def data_type(declared: str, parquet: bool = False) -> str:
    """The Croissant type for a column gen-sqltables declared. Parquet holds dates as text."""
    d = (declared or "").upper()
    if "INT" in d:
        return "sc:Integer"
    if "BOOL" in d:
        return "sc:Boolean"
    if any(k in d for k in ("FLOAT", "REAL", "DOUB", "NUMERIC", "DECIMAL")):
        return "sc:Float"
    if not parquet and d == "DATETIME":
        return "sc:DateTime"
    if not parquet and d == "DATE":
        return "sc:Date"
    return "sc:Text"


def slot_text(sv, cls: str | None, name: str) -> str | None:
    if cls in sv.all_classes():
        slot = next((s for s in sv.class_induced_slots(cls) if s.name == name), None)
        if slot is not None and slot.description:
            return slot.description.strip()
    return None


def column(rs: str, name: str, file_id: str, kind: str, text: str | None) -> dict:
    field = {"@type": "cr:Field", "@id": f"{rs}/{name}", "name": name, "dataType": kind,
             "source": {"fileObject": {"@id": file_id}, "extract": {"column": name}}}
    if text:
        field["description"] = text
    return field


def table_record_sets(sv, zip_path: Path, db: Path) -> tuple[list[dict], list[dict], dict[str, int]]:
    """A RecordSet per table in a per-class zip, typed as in the SQLite export, each link named.

    (file objects inside the zip, record sets, rows per record set)
    """
    parquet = zip_path.name.endswith("-parquet.zip")
    with zipfile.ZipFile(zip_path) as zf:
        names = sorted(zf.namelist())
    con = sqlite3.connect(db)
    classes = set(sv.all_classes())
    files, sets, rows = [], [], {}
    tables = {Path(n).stem: n for n in names}
    for t, name in tables.items():
        info = list(con.execute(f'PRAGMA table_info("{t}")'))
        links = {r[3]: (r[2], r[4]) for r in con.execute(f'PRAGMA foreign_key_list("{t}")')}
        fid = f"{zip_path.name}/{name}"
        files.append(member(zip_path.name, name))
        cls = t if t in classes else None
        fields = []
        for _, col, declared, _, _, _ in info:
            text = slot_text(sv, cls, col)
            if col == "parent_slot":
                text = "The field of the parent object this row sits in."
            target = links.get(col)
            if target:
                # Said, not declared as `references`: mlcroissant joins on a reference when it
                # loads, which changes the rows a table gives.
                link = f"Points at {target[0]}.{target[1]}."
                text = f"{text} {link}" if text else link
            fields.append(column(t, col, fid, data_type(declared, parquet), text))
        rs = {"@type": "cr:RecordSet", "@id": t, "name": t, "field": fields}
        key = [{"@id": f"{t}/{r[1]}"} for r in sorted(info, key=lambda r: r[5]) if r[5]]
        if key:
            rs["key"] = key[0] if len(key) == 1 else key
        if cls and sv.get_class(cls).description:
            rs["description"] = sv.get_class(cls).description.strip()
        elif "_" in t and t.split("_", 1)[0] in classes:
            owner, slot = t.split("_", 1)
            rs["description"] = f"The {slot} of each {owner}, a row each."
        sets.append(rs)
        rows[t] = con.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
    con.close()
    return files, sets, rows


def flat_record_set(sv, path: Path, n: int) -> tuple[list[dict], dict[str, int]]:
    """One RecordSet for the flat table: a column per field, nested values as JSON text."""
    with path.open(newline="", encoding="utf-8") as fh:
        header = next(csv.reader(fh, delimiter="," if path.suffix == ".csv" else "\t"), [])
    slots = {s.name: s for s in sv.class_induced_slots(RECORD_CLASS)}
    fields = [column(RECORD_CLASS, h, path.name, flat_type(sv, slots.get(h)), slot_text(sv, RECORD_CLASS, h))
              for h in header]
    rs = {"@type": "cr:RecordSet", "@id": RECORD_CLASS, "name": RECORD_CLASS, "field": fields,
          "key": {"@id": f"{RECORD_CLASS}/id"}}
    return [rs], {RECORD_CLASS: n}


def flat_type(sv, slot) -> str:
    """A flat cell's type: a single value keeps its range's type; lists and objects are text."""
    if slot is None or slot.multivalued or slot.range in sv.all_classes():
        return "sc:Text"
    return {"integer": "sc:Integer", "float": "sc:Float", "double": "sc:Float", "decimal": "sc:Float",
            "boolean": "sc:Boolean", "date": "sc:Date", "datetime": "sc:DateTime"}.get(slot.range, "sc:Text")


def jsonl_record_set(sv, path: Path, records: list[dict]) -> tuple[list[dict], dict[str, int]]:
    """One RecordSet for the JSON Lines records: a field per single, plain value every record has.

    Lists and nested objects stay in the file; the RecordSet names the values a table would hold.
    """
    slots = [s for s in sv.class_induced_slots(RECORD_CLASS)
             if not s.multivalued and s.range not in sv.all_classes()
             and all(s.name in d for d in records)]
    # mlcroissant reads JSON Lines as a table, a column per top-level key.
    fields = [column(RECORD_CLASS, s.name, path.name, flat_type(sv, s), slot_text(sv, RECORD_CLASS, s.name))
              for s in slots]
    rs = {"@type": "cr:RecordSet", "@id": RECORD_CLASS, "name": RECORD_CLASS, "field": fields}
    return ([rs] if fields else []), ({RECORD_CLASS: len(records)} if fields else {})


def record_sets(sv, written: list[Path], records: list[dict], db: Path | None):
    """The record sets for the best table the export wrote: per-class tables, flat, then JSON Lines."""
    by_name = {p.name: p for p in written}
    for fmt in ("csv", "tsv", "parquet"):
        zp = by_name.get(f"{SLUG}-tables-{fmt}.zip")
        if zp and db is not None and db.exists():
            return table_record_sets(sv, zp, db)
    for fmt in ("csv", "tsv"):
        flat = by_name.get(f"{SLUG}-records.{fmt}")
        if flat:
            return [], *flat_record_set(sv, flat, len(records))
    lines = by_name.get(f"{SLUG}-records.jsonl")
    if lines and records:
        return [], *jsonl_record_set(sv, lines, records)
    return [], [], {}


# ---------------------------------------------------------------- write and check


def build(sv, records: list[dict], written: list[Path], db: Path | None) -> tuple[dict, dict[str, int]]:
    """The Croissant document, and the rows each RecordSet must load."""
    reg = registry_entry()
    name = reg.get("name") or MECH_NAME
    description = (reg.get("description") or sv.schema.description or name).strip()
    repo = reg.get("repository") or REPO_URL
    url = reg.get("homepage_url") or repo
    license_ = license_url(sv, reg)
    version = mech_version()
    today = datetime.datetime.now(datetime.UTC).date().isoformat()
    people = creators(reg)
    keywords = ["mech", "knowledge base", "linkml", "ontology", "curation", *(reg.get("domains") or [])]
    inner, sets, rows = record_sets(sv, written, records, db)
    doc = {
        "@context": CONTEXT,
        "@type": "sc:Dataset",
        "conformsTo": CONFORMS_TO,
        "name": name,
        "description": description,
        "url": url,
        "sameAs": [repo] if url != repo else [],
        "version": version,
        "datePublished": today,
        "license": license_,
        "creator": people,
        "citeAs": cite_as(name, people, today[:4], url, version),
        "keywords": keywords,
        "inLanguage": "en",
        **responsible_ai(reg, INGEST_LOCK.exists()),
        "distribution": [file_object(p) for p in written] + inner,
        "recordSet": sets,
    }
    derived = ingest_sources() + ontology_sources(sv)
    for rel, entities in registry_sources(reg).items():
        if rel == "prov:wasDerivedFrom":
            derived += entities
        else:
            doc[rel] = entities
    if derived:
        doc["prov:wasDerivedFrom"] = derived
    cited = citations(sv, references(records))
    if cited:
        doc["citation"] = cited
    return {k: v for k, v in doc.items() if v not in ([], None, "")}, rows


def write(sv, records: list[dict], written: list[Path], db: Path | None, out: Path) -> dict[str, int]:
    doc, rows = build(sv, records, written, db)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return rows


def check(out: Path, rows: dict[str, int]) -> tuple[list[str], list[str]]:
    """Validate the file with mlcroissant, and load every RecordSet: sha256s match, rows are all there.

    (problems, warnings). A warning, such as a version that is not MAJOR.MINOR.PATCH before the
    first release tag, does not fail the export. The check runs in its own process, with an empty
    cache: mlcroissant reads CROISSANT_CACHE once, when imported, and caches an archive's
    contents by its name, so a rebuilt zip would otherwise be read as it was.
    Raises ModuleNotFoundError (name mlcroissant) when mlcroissant is not installed.
    """
    import importlib.util
    import subprocess
    import sys

    if importlib.util.find_spec("mlcroissant") is None:
        raise ModuleNotFoundError("No module named 'mlcroissant'", name="mlcroissant")
    with tempfile.TemporaryDirectory() as cache:
        proc = subprocess.run([sys.executable, "-m", f"{SLUG}.croissant", str(out), json.dumps(rows)],
                              env={**os.environ, "CROISSANT_CACHE": cache}, capture_output=True, text=True)
    try:
        result = json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return [f"{out.name}: the mlcroissant check did not finish: {proc.stderr.strip()[-800:]}"], []
    return result["problems"], result["warnings"]


def check_here(out: Path, rows: dict[str, int]) -> tuple[list[str], list[str]]:
    """check(), in this process: run it with a fresh CROISSANT_CACHE."""
    import logging

    import mlcroissant as mlc

    logging.getLogger("absl").setLevel(logging.ERROR)
    try:
        ds = mlc.Dataset(jsonld=str(out))
    except mlc.ValidationError as exc:
        return [f"{out.name}: not valid Croissant: {exc}"], []
    problems: list[str] = []
    warnings = [f"{out.name}: {w}" for w in ds.metadata.ctx.issues.warnings]
    for rs, want in rows.items():
        try:
            got = sum(1 for _ in ds.records(record_set=rs))
        except Exception as exc:  # noqa: BLE001  mlcroissant raises many kinds; report any
            problems.append(f"{out.name}: record set {rs} does not load: {exc}")
            continue
        if got != want:
            problems.append(f"{out.name}: record set {rs} loads {got} row(s), expected {want}")
    return problems, warnings


if __name__ == "__main__":
    import sys

    found, warned = check_here(Path(sys.argv[1]), json.loads(sys.argv[2]))
    print(json.dumps({"problems": found, "warnings": warned}))
