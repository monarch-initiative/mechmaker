"""Export the records in the formats conf/export.yaml names, and check each one.

    python -m <slug>.export            # write build/export/ and check every file
    python -m <slug>.export --list     # the formats this Mech exports, and the files

Every format comes from LinkML or the libraries it brings:

  yaml     <slug>-records.zip          the curated YAML files, as they are
  json     <slug>-records.json, .jsonl the records as JSON
  jsonld   <slug>-records.jsonld       RDF as JSON-LD, the same graph as ttl
  ttl      <slug>-records.ttl          RDF as Turtle, through the schema's URIs
  sqlite   <slug>-records.sqlite       a SQLite database
  duckdb   <slug>-records.duckdb       a DuckDB database, through linkml-store: one
                                       table of records, nested values as DuckDB JSON
  kgx      <slug>-kgx_nodes/_edges     KGX: Biolink associations, record to term (see kgx.py)
  kgx_maximal  ..._maximal_nodes/_edges  KGX: the whole record graph (see kgx.py)
  sql      <slug>-schema.sql           the schema as SQL DDL (gen-sqltables)
           <slug>-records.sql          the database as SQL: DDL and INSERTs
  csv/tsv  tabular_layout per_class:   <slug>-tables-csv.zip, one file per class
           tabular_layout flat:        <slug>-records.csv, one row per record

Tables, one per class, follow gen-sqltables: a nested object's row points at
its parent through a `<ParentClass>_id` column, and a `parent_slot` column
names the field it came from (a record's `evidence` and its
`description_evidence` would otherwise share one column). Flat tables have
one row per record; a list of values is joined with " | ", and a nested
object is written as JSON.

Each file is read back after it is written: RDF is parsed, tables and the
database are counted, SQL is loaded into an empty database. An RDF IRI that
is not http(s) fails the export: it is a CURIE whose prefix the schema does
not declare. Output in build/ is not committed; releases attach it.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sqlite3
import sys
import zipfile
from pathlib import Path

import yaml

from .paths import BUILD_DIR, RECORD_CLASS, RECORDS_DIR, REPO_ROOT, SCHEMA_PATH, SLUG
from .validate import iter_records, load

EXPORT_DIR = BUILD_DIR / "export"
SETTINGS = REPO_ROOT / "conf" / "export.yaml"
FORMATS = ("yaml", "json", "jsonld", "ttl", "sqlite", "duckdb", "sql", "csv", "tsv", "kgx", "kgx_maximal")
# Only the duckdb format needs a package a Mech does not always install.
DUCKDB_MISSING = (
    "duckdb: needs linkml-store, which this Mech does not install. Run `uv add 'linkml-store>=0.3.2'` "
    "and `just install`, or take duckdb out of conf/export.yaml."
)
LAYOUTS = ("per_class", "flat")
DEFAULTS = {"formats": ["yaml", "json"], "tabular_layout": "per_class"}


def settings() -> dict:
    data = yaml.safe_load(SETTINGS.read_text()) if SETTINGS.exists() else {}
    out = {**DEFAULTS, **(data or {})}
    bad = [f for f in out["formats"] if f not in FORMATS]
    if bad:
        raise SystemExit(f"conf/export.yaml: unknown format(s) {bad}; choose from {list(FORMATS)}")
    if out["tabular_layout"] not in LAYOUTS:
        raise SystemExit(f"conf/export.yaml: tabular_layout must be one of {list(LAYOUTS)}")
    return out


def schemaview():
    from linkml_runtime.utils.schemaview import SchemaView

    sv = SchemaView(str(SCHEMA_PATH))
    sv.merge_imports()
    return sv


# ---------------------------------------------------------------- RDF


def pad_single_keys(sv, cls: str, obj):
    """Give each one-key object in a list a second, empty field.

    linkml-runtime (1.11) reads a one-key list item such as {purpose: DAIRY}
    as a key:value shorthand, and then fails comparing the enum it made with
    the string it read. A second field set to None takes it down the
    ordinary path; None fields are dropped, so the data is unchanged.
    """
    classes = sv.all_classes()
    if not isinstance(obj, dict):
        return obj
    out = dict(obj)
    for slot in sv.class_induced_slots(cls):
        value = out.get(slot.name)
        if slot.range not in classes or value is None:
            continue
        names = [s.name for s in sv.class_induced_slots(slot.range)]
        if isinstance(value, list):
            items = []
            for item in value:
                item = pad_single_keys(sv, slot.range, item)
                if isinstance(item, dict) and len(item) == 1:
                    spare = next((n for n in names if n not in item), None)
                    if spare:
                        item = {**item, spare: None}
                items.append(item)
            out[slot.name] = items
        else:
            out[slot.name] = pad_single_keys(sv, slot.range, value)
    return out


def rdf_graph(sv, records: list[tuple[Path, dict]]):
    """One graph for every record, through the schema's URIs."""
    from linkml.generators.pythongen import PythonGenerator
    from linkml_runtime.dumpers import rdflib_dumper

    module = PythonGenerator(sv.schema).compile_module()
    target = getattr(module, RECORD_CLASS)
    import rdflib

    graph = rdflib.Graph()
    for _, data in records:
        obj = target(**pad_single_keys(sv, RECORD_CLASS, data))
        graph += rdflib_dumper.as_rdf_graph(obj, schemaview=sv)
    for prefix, p in sv.schema.prefixes.items():
        graph.bind(prefix, p.prefix_reference, override=True)
    return graph


def check_rdf(path: Path, fmt: str, sv, n: int) -> list[str]:
    import rdflib
    from rdflib.namespace import RDF

    g = rdflib.Graph().parse(path, format=fmt)
    problems = []
    cls = rdflib.URIRef(sv.get_uri(RECORD_CLASS, expand=True))
    found = len(set(g.subjects(RDF.type, cls)))
    if found != n:
        problems.append(f"{path.name}: {found} {RECORD_CLASS} subject(s), expected {n}")
    odd = sorted({str(t) for triple in g for t in triple
                  if isinstance(t, rdflib.URIRef) and not str(t).startswith(("http://", "https://"))})
    if odd:
        prefixes = sorted({t.split(":", 1)[0] for t in odd})
        problems.append(
            f"{path.name}: {len(odd)} IRI(s) are not http(s), e.g. {odd[0]!r}. Declare these prefixes "
            f"with full URIs in the schema's `prefixes`: {', '.join(prefixes)}")
    return problems


# ---------------------------------------------------------------- tables


def build_sqlite(sv, records: list[tuple[Path, dict]], db: Path) -> None:
    """Load the records into gen-sqltables' layout, one table per class."""
    from linkml.generators.sqltablegen import SQLTableGenerator

    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(SQLTableGenerator(sv.schema, dialect="sqlite").generate_ddl())
    classes = set(sv.all_classes())
    columns = {t: [r[1] for r in con.execute(f'PRAGMA table_info("{t}")')]
               for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table, cols in columns.items():
        # A class table whose rows can sit under a parent gets parent_slot. A join
        # table (<Class>_<slot>) does not need one: its name says the slot.
        if table in classes and any(c.endswith("_id") and c[:-3] in classes for c in cols):
            con.execute(f'ALTER TABLE "{table}" ADD COLUMN parent_slot TEXT')
            cols.append("parent_slot")

    def table_cols(table: str) -> list[str]:
        if table not in columns:
            raise SystemExit(f"export: gen-sqltables made no table {table!r}; the layout is not as expected")
        return columns[table]

    def insert(cls: str, obj: dict, parent: tuple[str, object, str] | None = None):
        cols = table_cols(cls)
        ident = sv.get_identifier_slot(cls)
        row: dict = {}
        later = []
        if parent:
            pcls, pid, pslot = parent
            row[f"{pcls}_id"], row["parent_slot"] = pid, pslot
        for slot in sv.class_induced_slots(cls):
            value = obj.get(slot.name)
            if value is None:
                continue
            rng = slot.range if slot.range in classes else None
            if rng:
                check_reference(cls, slot.name, rng, value)
            if slot.multivalued:
                later.append((slot, rng, value))
            elif rng and not isinstance(value, dict):
                row[slot.name] = str(value)  # a reference by id: gen-sqltables names the column for the slot
            elif rng:
                child_ident = sv.get_identifier_slot(rng)
                row[f"{slot.name}_id"] = upsert(rng, value) if child_ident else insert(rng, value)
            else:
                row[slot.name] = int(value) if isinstance(value, bool) else value
        missing = [k for k in row if k not in cols]
        if missing:
            raise SystemExit(f"export: table {cls!r} has no column(s) {missing}; "
                             "the layout is not as expected")
        names = ", ".join(f'"{k}"' for k in row)
        cur = con.execute(f'INSERT INTO "{cls}" ({names}) VALUES ({", ".join("?" * len(row))})',
                          [v if isinstance(v, (str, int, float)) else str(v) for v in row.values()])
        pk = obj.get(ident.name) if ident else cur.lastrowid
        for slot, rng, values in later:
            for v in values:
                if rng and not sv.get_identifier_slot(rng):
                    insert(rng, v, (cls, pk, slot.name))
                else:
                    joined = f"{cls}_{slot.name}"
                    item = upsert(rng, v) if rng and isinstance(v, dict) else v
                    col = f"{slot.name}_id" if rng else slot.name
                    table_cols(joined)
                    sql = f'INSERT OR IGNORE INTO "{joined}" ("{cls}_id", "{col}") VALUES (?, ?)'
                    con.execute(sql, (pk, item))
        return pk

    def check_reference(cls: str, slot: str, rng: str, value) -> None:
        """A field holding a class is a nested object, or an id when the class has one."""
        for v in value if isinstance(value, list) else [value]:
            if not isinstance(v, dict) and not sv.get_identifier_slot(rng):
                raise SystemExit(f"export: {cls}.{slot} holds {v!r}, but {rng} has no identifier, "
                                 "so it must be a nested object")

    def upsert(cls: str, obj: dict):
        ident = sv.get_identifier_slot(cls)
        if con.execute(f'SELECT 1 FROM "{cls}" WHERE "{ident.name}" = ?', (obj[ident.name],)).fetchone():
            return obj[ident.name]
        return insert(cls, obj)

    for _, data in records:
        insert(RECORD_CLASS, data)
    con.commit()
    con.close()


def table_rows(con: sqlite3.Connection, table: str) -> tuple[list[str], list[tuple]]:
    cur = con.execute(f'SELECT * FROM "{table}" ORDER BY rowid')
    return [d[0] for d in cur.description], cur.fetchall()


def flat_rows(sv, records: list[tuple[Path, dict]]) -> tuple[list[str], list[list]]:
    cols = [s.name for s in sv.class_induced_slots(RECORD_CLASS)]
    used = [c for c in cols if any(c in d for _, d in records)]

    def cell(v):
        if v is None:
            return ""
        if isinstance(v, list) and all(not isinstance(x, (dict, list)) for x in v):
            return " | ".join(map(str, v))
        if isinstance(v, (dict, list)):
            return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
        return v

    return used, [[cell(d.get(c)) for c in used] for _, d in records]


def write_table(path: Path, header: list[str], rows, delimiter: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=delimiter)
        w.writerow(header)
        w.writerows(rows)


# ---------------------------------------------------------------- DuckDB


def write_duckdb(sv, records: list[tuple[Path, dict]], out: Path) -> Path:
    """The records in DuckDB, through linkml-store, one row per record.

    Nested values become DuckDB JSON columns, queryable in SQL, e.g.
    SELECT name, p->>'$.term.label' FROM <table>, unnest(<section>) AS t(p).
    Raises ModuleNotFoundError (name linkml_store) when linkml-store is not installed.
    """
    from linkml_store import Client

    out.unlink(missing_ok=True)
    db = Client().attach_database(f"duckdb:///{out}", alias=SLUG)
    db.set_schema_view(sv)
    collection = db.create_collection(RECORD_CLASS, alias=RECORDS_DIR.name)
    if records:
        collection.insert([d for _, d in records])
    db.commit()
    db.close()
    return out


def check_duckdb(out: Path, ids: list) -> list[str]:
    import duckdb

    con = duckdb.connect(str(out), read_only=True)
    try:
        if not ids:
            return []
        got = sorted(str(r[0]) for r in con.execute(f'SELECT id FROM "{RECORDS_DIR.name}"').fetchall())
    finally:
        con.close()
    want = sorted(str(i) for i in ids)
    if got == want:
        return []
    return [f"{out.name}: holds {len(got)} record(s) with other ids than the {len(want)} exported"]


# ---------------------------------------------------------------- export


def export(
    cfg: dict, paths: list[Path] | None = None, out_dir: Path = EXPORT_DIR
) -> tuple[list[Path], list[str]]:
    """Write every configured format into out_dir and read each back. (files, problems)"""
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.iterdir():
        if old.is_file():
            old.unlink()
    records = [(p, load(p) or {}) for p in (iter_records() if paths is None else paths)]
    n = len(records)
    seen: dict[str, Path] = {}
    for p, d in records:
        rid = str(d.get("id"))
        if rid in seen:
            # Every format keys records by id: a second one would overwrite or collide.
            raise SystemExit(f"export: {p.name} and {seen[rid].name} have the same id {rid!r}")
        seen[rid] = p
    fmts = set(cfg["formats"])
    written: list[Path] = []
    problems: list[str] = []
    sv = schemaview() if fmts - {"yaml", "json"} else None

    if "yaml" in fmts:
        out = out_dir / f"{SLUG}-records.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
            for p, _ in records:
                inside = p.is_relative_to(RECORDS_DIR.parent)
                zf.write(p, p.relative_to(RECORDS_DIR.parent) if inside else p.name)
        written.append(out)
        if len(zipfile.ZipFile(out).namelist()) != n:
            problems.append(f"{out.name}: wrong number of files")

    if "json" in fmts:
        out = out_dir / f"{SLUG}-records.json"
        out.write_text(json.dumps([d for _, d in records], ensure_ascii=False, indent=1) + "\n")
        lines = out_dir / f"{SLUG}-records.jsonl"
        lines.write_text("".join(json.dumps(d, ensure_ascii=False) + "\n" for _, d in records))
        written += [out, lines]
        if len(json.loads(out.read_text())) != n or len(lines.read_text().splitlines()) != n:
            problems.append(f"{out.name}: wrong number of records")

    if fmts & {"ttl", "jsonld"} and n:
        graph = rdf_graph(sv, records)
        if "ttl" in fmts:
            out = out_dir / f"{SLUG}-records.ttl"
            graph.serialize(out, format="turtle")
            written.append(out)
            problems += check_rdf(out, "turtle", sv, n)
        if "jsonld" in fmts:
            out = out_dir / f"{SLUG}-records.jsonld"
            context = {p: v.prefix_reference for p, v in sv.schema.prefixes.items()}
            graph.serialize(out, format="json-ld", context=context, indent=1)
            written.append(out)
            problems += check_rdf(out, "json-ld", sv, n)

    if "duckdb" in fmts:
        try:
            out = write_duckdb(sv, records, out_dir / f"{SLUG}-records.duckdb")
        except ModuleNotFoundError as exc:
            if exc.name != "linkml_store":  # installed, but something it needs is not: show that
                raise
            problems.append(DUCKDB_MISSING)
        else:
            written.append(out)
            problems += check_duckdb(out, [d.get("id") for _, d in records])

    for fmt in ("kgx", "kgx_maximal"):
        if fmt not in fmts:
            continue
        from . import kgx

        try:
            files, kgx_problems, warnings = kgx.export(fmt, sv, [d for _, d in records], out_dir)
        except ModuleNotFoundError as exc:
            if exc.name != "biolink_model":  # installed, but something it needs is not: show that
                raise
            problems.append(kgx.BIOLINK_MISSING)
            continue
        written += files
        problems += kgx_problems
        for w in warnings:
            print(f"WARNING {w}")

    tables = fmts & {"csv", "tsv"}
    per_class = cfg["tabular_layout"] == "per_class"
    if fmts & {"sqlite", "sql"} or (tables and per_class):
        db = out_dir / f"{SLUG}-records.sqlite"
        build_sqlite(sv, records, db)
        con = sqlite3.connect(db)
        got = con.execute(f'SELECT count(*) FROM "{RECORD_CLASS}"').fetchone()[0]
        if got != n:
            problems.append(f"{db.name}: {got} {RECORD_CLASS} row(s), expected {n}")
        if "sqlite" in fmts:
            written.append(db)
        if "sql" in fmts:
            from linkml.generators.sqltablegen import SQLTableGenerator

            ddl = out_dir / f"{SLUG}-schema.sql"
            ddl.write_text(SQLTableGenerator(sv.schema, dialect="sqlite").generate_ddl())
            dump = out_dir / f"{SLUG}-records.sql"
            dump.write_text("\n".join(con.iterdump()) + "\n")
            written += [ddl, dump]
            probe = sqlite3.connect(":memory:")
            probe.executescript(ddl.read_text())
            probe.close()
            probe = sqlite3.connect(":memory:")
            probe.executescript(dump.read_text())
            if probe.execute(f'SELECT count(*) FROM "{RECORD_CLASS}"').fetchone()[0] != n:
                problems.append(f"{dump.name}: does not load back to {n} records")
            probe.close()
        for fmt in sorted(tables) if per_class else []:
            sep = "," if fmt == "csv" else "\t"
            out = out_dir / f"{SLUG}-tables-{fmt}.zip"
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                    header, rows = table_rows(con, t)
                    if not rows:
                        continue
                    buf = io.StringIO()
                    w = csv.writer(buf, delimiter=sep)
                    w.writerow(header)
                    w.writerows(rows)
                    zf.writestr(f"{t}.{fmt}", buf.getvalue())
            written.append(out)
            with zipfile.ZipFile(out) as zf:
                text = zf.read(f"{RECORD_CLASS}.{fmt}").decode() if n else ""
            if n and len(list(csv.reader(io.StringIO(text), delimiter=sep))) - 1 != n:
                problems.append(f"{out.name}: {RECORD_CLASS}.{fmt} does not have {n} rows")
        con.close()
        if "sqlite" not in fmts:
            db.unlink()

    for fmt in sorted(tables) if not per_class else []:
        sep = "," if fmt == "csv" else "\t"
        out = out_dir / f"{SLUG}-records.{fmt}"
        header, rows = flat_rows(sv, records)
        write_table(out, header, rows, sep)
        written.append(out)
        with out.open(newline="", encoding="utf-8") as fh:
            if len(list(csv.reader(fh, delimiter=sep))) - 1 != n:
                problems.append(f"{out.name}: does not have {n} rows")
    return written, problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list", action="store_true", help="print the configured formats and stop")
    args = parser.parse_args(argv)
    cfg = settings()
    if args.list:
        print(f"formats: {', '.join(cfg['formats'])}; tables: {cfg['tabular_layout']}")
        return 0
    written, problems = export(cfg)
    for p in written:
        print(f"  {p.relative_to(REPO_ROOT)}  ({p.stat().st_size:,} bytes)")
    for p in problems:
        print(f"ERROR {p}")
    n = len(iter_records())
    print(f"\n{n} record(s) in {len(written)} file(s); "
          + ("every file read back." if not problems else f"{len(problems)} problem(s)."))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
