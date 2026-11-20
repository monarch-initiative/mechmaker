"""The record browser's query page: its data, and a check of every prewritten query.

    python -m <slug>.query check          # run every query in conf/queries.yaml; fail on an error
    python -m <slug>.query build DIR      # write the page's data files into DIR, replacing its old ones

The query page (records/query.html) runs queries in the visitor's browser, so
the site stays static. Its data are written beside it, under records/data/,
whenever the site is built:

  tables.json      the tables, their columns and row counts, and each record's
                   id, IRI and page, so results can link to records
  <Table>.parquet  for SQL: one file per class, the tables of the SQLite
                   export (see export.py), plus two tables made for querying:
                     record_evidence  one row per quote: the record, the
                                      section it sits in, the reference, its
                                      support and the quote itself
                     record_terms     one row per ontology term a record
                                      binds, with the section it sits in
  records.ttl      for SPARQL: the records as RDF, the graph the Turtle export
                   writes, through the schema's URIs

SQL runs in DuckDB (DuckDB-WASM in the browser, the duckdb package here).
SPARQL runs in Oxigraph (its WebAssembly build in the browser, pyoxigraph
here). The check runs each query with the same engine the page uses, over
the same files, so a query that breaks when the schema changes fails
`just qc` before it reaches the site. It checks that each query runs, not
what it returns: a new Mech with no records still passes.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

import yaml

from . import export
from .paths import REPO_ROOT, SLUG
from .validate import iter_records, load

SETTINGS = REPO_ROOT / "conf" / "queries.yaml"
LANGUAGES = ("sql", "sparql")
MISSING = {
    "sql": "SQL queries need the duckdb package, which this Mech does not install. Run "
           "`uv add 'duckdb>=1.4'` and `just install`, or take sql out of conf/queries.yaml `languages`.",
    "sparql": "SPARQL queries need pyoxigraph, which this Mech does not install. Run "
              "`uv add 'pyoxigraph>=0.5'` and `just install`, or take sparql out of conf/queries.yaml "
              "`languages`.",
}
# Tables made for querying, beside the class tables. A class of the same name would be shadowed.
DERIVED = {
    "record_evidence": ["record_id", "record_name", "section", "reference", "reference_title", "supports",
                        "evidence_source", "snippet"],
    "record_terms": ["record_id", "record_name", "section", "term_id", "term_label"],
}


def settings() -> dict:
    data = yaml.safe_load(SETTINGS.read_text(encoding="utf-8")) if SETTINGS.exists() else {}
    data = data or {}
    return {"languages": list(data.get("languages") or ["sql"]), "queries": list(data.get("queries") or [])}


def problems(cfg: dict) -> list[str]:
    """What is wrong with conf/queries.yaml itself, before any query runs."""
    out = []
    bad = [lang for lang in cfg["languages"] if lang not in LANGUAGES]
    if bad:
        out.append(f"languages: unknown {bad}; choose from {list(LANGUAGES)}")
    seen = set()
    for i, q in enumerate(cfg["queries"]):
        where = f"queries[{i}]"
        if not isinstance(q, dict):
            out.append(f"{where}: not a mapping")
            continue
        for key in ("id", "title", "language", "query"):
            if not str(q.get(key) or "").strip():
                out.append(f"{where}: no {key}")
        qid = q.get("id")
        if qid in seen:
            out.append(f"{where}: id {qid!r} is used twice")
        seen.add(qid)
        if q.get("language") and q["language"] not in cfg["languages"]:
            out.append(f"{where} ({qid}): language {q['language']!r} is not among `languages` "
                       f"{cfg['languages']}")
    return out


def records() -> list[tuple[Path, dict]]:
    loaded = [(p, load(p)) for p in iter_records()]
    return [(p, d) for p, d in loaded if isinstance(d, dict)]


# ---------------------------------------------------------------- tables made for querying


def walk(value, section: str, found: dict[str, list]) -> None:
    """Every quote and every ontology term under one section of a record."""
    if isinstance(value, list):
        for v in value:
            walk(v, section, found)
        return
    if not isinstance(value, dict):
        return
    if "reference" in value and "supports" in value:
        found["evidence"].append([section] + [value.get(k) for k in DERIVED["record_evidence"][3:]])
    if set(value) == {"id", "label"}:
        found["terms"].append([section, value["id"], value["label"]])
        return
    for v in value.values():
        walk(v, section, found)


def derived_rows(recs: list[tuple[Path, dict]]) -> dict[str, list[list]]:
    rows: dict[str, list[list]] = {"record_evidence": [], "record_terms": []}
    for _, data in recs:
        head = [str(data.get("id")), data.get("name")]
        for key, value in data.items():
            if key == "curation_history":
                continue
            found: dict[str, list] = {"evidence": [], "terms": []}
            # A record's own description quotes are the description's.
            walk(value, "description" if key == "description_evidence" else key, found)
            rows["record_evidence"] += [head + r for r in found["evidence"]]
            rows["record_terms"] += [head + r for r in found["terms"]]
    return rows


# ---------------------------------------------------------------- building the data


def column_type(declared: str, values: list) -> str:
    """The DuckDB type for a column gen-sqltables declared; text when a value does not fit it."""
    d = (declared or "").upper()
    present = [v for v in values if v is not None]
    if "BOOL" in d and all(v in (0, 1) and not isinstance(v, str) for v in present):
        return "BOOLEAN"
    if "INT" in d and all(isinstance(v, int) for v in present):
        return "BIGINT"
    if any(k in d for k in ("FLOAT", "REAL", "DOUB", "NUMERIC", "DECIMAL")) and all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
        return "DOUBLE"
    return "VARCHAR"


def quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def write_parquet(con, table: str, columns: list[tuple[str, str]], rows: list, out_dir: Path) -> Path:
    con.execute(f"CREATE TABLE {quote(table)} ({', '.join(f'{quote(c)} {t}' for c, t in columns)})")
    if rows:
        typed = [[None if v is None else str(v) if t == "VARCHAR" else bool(v) if t == "BOOLEAN" else v
                  for v, (_, t) in zip(r, columns, strict=True)] for r in rows]
        con.executemany(f"INSERT INTO {quote(table)} VALUES ({', '.join('?' * len(columns))})", typed)
    out = out_dir / f"{table}.parquet"
    con.execute(f"COPY {quote(table)} TO '{str(out).replace(chr(39), chr(39) * 2)}' (FORMAT parquet)")
    return out


def build_tables(sv, recs: list[tuple[Path, dict]], out_dir: Path) -> list[dict]:
    """The SQLite export's tables and the tables made for querying, as Parquet files in out_dir."""
    try:
        import duckdb
    except ModuleNotFoundError:
        raise SystemExit(MISSING["sql"]) from None
    tables = []
    con = duckdb.connect()
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "records.sqlite"
        export.build_sqlite(sv, recs, db)
        src = sqlite3.connect(db)
        names = [t for (t,) in src.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        # DuckDB's table names ignore case.
        clash = sorted(n for n in names if n.lower() in DERIVED)
        if clash:
            raise SystemExit(f"query: the schema has a class named {clash[0]!r}, the name of a table the "
                             f"query page makes ({', '.join(DERIVED)}). Rename the class.")
        for t in names:
            declared = [(r[1], r[2]) for r in src.execute(f"PRAGMA table_info({quote(t)})")]
            rows = src.execute(f"SELECT * FROM {quote(t)}").fetchall()
            columns = [(c, column_type(d, [r[i] for r in rows])) for i, (c, d) in enumerate(declared)]
            write_parquet(con, t, columns, rows, out_dir)
            tables.append({"name": t, "columns": [c for c, _ in columns], "rows": len(rows)})
        src.close()
    for t, rows in derived_rows(recs).items():
        columns = [(c, "VARCHAR") for c in DERIVED[t]]
        write_parquet(con, t, columns, rows, out_dir)
        tables.append({"name": t, "columns": DERIVED[t], "rows": len(rows), "made_for_queries": True})
    con.close()
    return tables


def build_graph(sv, recs: list[tuple[Path, dict]], out_dir: Path) -> tuple[Path, list[str]]:
    """The records as Turtle, and what is wrong with the graph (IRIs a query cannot name)."""
    try:
        import pyoxigraph  # noqa: F401  (the check needs it; fail here, before the slow part)
    except ModuleNotFoundError:
        raise SystemExit(MISSING["sparql"]) from None
    out = out_dir / "records.ttl"
    if not recs:
        out.write_text("", encoding="utf-8")
        return out, []
    export.rdf_graph(sv, recs).serialize(out, format="turtle")
    return out, export.check_rdf(out, "turtle", sv, len(recs))


def build(out_dir: Path, cfg: dict | None = None) -> tuple[list[Path], list[str]]:
    """Write the page's data into out_dir. (files written, problems)"""
    cfg = cfg or settings()
    out_dir.mkdir(parents=True, exist_ok=True)
    # The files an earlier build wrote (a table whose class is gone goes too); nothing else.
    for old in [*out_dir.glob("*.parquet"), out_dir / "records.ttl", out_dir / "tables.json"]:
        if old.is_file():
            old.unlink()
    recs = records()
    sv = export.schemaview()
    found: list[str] = []
    manifest: dict = {"languages": cfg["languages"], "tables": [], "graph": None, "records": []}
    if "sql" in cfg["languages"]:
        manifest["tables"] = build_tables(sv, recs, out_dir)
    if "sparql" in cfg["languages"]:
        graph, found = build_graph(sv, recs, out_dir)
        manifest["graph"] = graph.name
    for path, data in recs:
        rid = str(data.get("id"))
        try:
            iri = sv.expand_curie(rid)
        except Exception:  # an id the schema's prefixes do not cover: the page links it by CURIE alone
            iri = rid
        manifest["records"].append({"id": rid, "iri": iri, "page": f"records/{path.stem}.html"})
    (out_dir / "tables.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
                                         encoding="utf-8")
    written = [*out_dir.glob("*.parquet"), out_dir / "records.ttl", out_dir / "tables.json"]
    return sorted(p for p in written if p.is_file()), found


# ---------------------------------------------------------------- checking the queries


def run_sql(data_dir: Path, sql: str) -> list[tuple]:
    import duckdb

    con = duckdb.connect()
    try:
        for p in sorted(data_dir.glob("*.parquet")):
            con.execute(f"CREATE VIEW {quote(p.stem)} AS SELECT * FROM read_parquet('{p.as_posix()}')")
        return con.execute(sql).fetchall()
    finally:
        con.close()


def run_sparql(data_dir: Path, sparql: str) -> list:
    import pyoxigraph

    store = pyoxigraph.Store()
    graph = data_dir / "records.ttl"
    if graph.stat().st_size:
        store.load(path=str(graph), format=pyoxigraph.RdfFormat.TURTLE)
    result = store.query(sparql)
    # An ASK query answers with a QueryBoolean, which is not iterable; the rest give rows or triples.
    return bool(result) if isinstance(result, pyoxigraph.QueryBoolean) else list(result)


def check(cfg: dict | None = None, data_dir: Path | None = None) -> list[str]:
    """Every problem with conf/queries.yaml and its queries, run over the records."""
    cfg = cfg or settings()
    found = problems(cfg)
    if found:
        return found
    with tempfile.TemporaryDirectory() as tmp:
        if data_dir is None:
            data_dir = Path(tmp)
            _, found = build(data_dir, cfg)
        run = {"sql": run_sql, "sparql": run_sparql}
        for q in cfg["queries"]:
            try:
                rows = run[q["language"]](data_dir, q["query"])
            except Exception as e:  # the engine's own message says what is wrong
                found.append(f"{q['id']} ({q['language']}): {type(e).__name__}: {e}")
                continue
            print(f"  ok {q['id']} ({q['language']}): {rows if isinstance(rows, bool) else len(rows)}")
    return found


def page_queries(cfg: dict) -> list[dict]:
    """The queries as the page shows them: in conf/queries.yaml's order, for its languages."""
    keep = ("id", "title", "description", "language", "query")
    return [{k: str(q.get(k) or "").strip() for k in keep} for q in cfg["queries"]
            if q.get("language") in cfg["languages"]]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="run every query in conf/queries.yaml over the records")
    b = sub.add_parser("build", help="write the page's data files")
    b.add_argument("out_dir", type=Path)
    args = parser.parse_args(argv)
    if args.command == "build":
        files, found = build(args.out_dir)
        print(f"Wrote {len(files)} files to {args.out_dir} for {SLUG}'s query page.")
    else:
        found = check()
    for p in found:
        print(f"ERROR {p}")
    if found:
        return 1
    if args.command == "check":
        print("Every query runs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
