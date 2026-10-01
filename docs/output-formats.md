# Output formats

A Mech curates its records as YAML. `just export` turns them into the
formats the Mech publishes, reads each file back to check it, and puts them
in `build/export/`. A release attaches them, if the `release-records`
workflow is on. `just qc` runs the export too, so a format that stops
working fails QC.

Every format comes from LinkML or the libraries it brings.

| Format | Files | What it is for |
|---|---|---|
| `yaml` | `<slug>-records.zip` | The curated files, as they are |
| `json` | `<slug>-records.json`, `<slug>-records.jsonl` | Programs; JSON Lines for streaming |
| `jsonld` | `<slug>-records.jsonld` | Linked data, as JSON |
| `ttl` | `<slug>-records.ttl` | Linked data, as Turtle, for triple stores |
| `sqlite` | `<slug>-records.sqlite` | A database to query directly |
| `duckdb` | `<slug>-records.duckdb` | Analytics in DuckDB: one table of records, nested values as JSON. Optional, see below |
| `sql` | `<slug>-schema.sql`, `<slug>-records.sql` | The schema as SQL DDL, and the data as SQL to load anywhere |
| `csv`, `tsv` | see below | Spreadsheets and data frames |

## Choosing

Copier asks `output_formats` when the Mech is made. The default is every
format but TSV and DuckDB. Change the choice any time in `conf/export.yaml`:

```yaml
formats:
  - yaml
  - json
  - ttl
tabular_layout: per_class
```

## DuckDB, an optional extra

The DuckDB export goes through [linkml-store](https://github.com/linkml/linkml-store),
which brings about seventy packages of its own (DuckDB, and clients for
other databases such as MongoDB). So a Mech installs it only when
`output_formats` includes `duckdb`: the template adds `linkml-store` to the
Mech's dependencies then, and not otherwise.

The database has one table, named after the records folder (for GoatMech,
`goat_breeds`), with one row per record. Nested sections are DuckDB `JSON`
columns, so SQL can reach inside them:

```sql
SELECT name, f->>'preferred_term', f->'term'->>'label'
FROM goat_breeds, unnest(distinguishing_features) AS t(f);
```

For one table per class in DuckDB, attach the SQLite export instead:
`ATTACH '<slug>-records.sqlite' AS s (TYPE sqlite);`, then query `s.<Class>`.
The first `ATTACH` downloads DuckDB's SQLite extension, so it needs the
network once; run `INSTALL sqlite;` ahead of time for offline use.

To add DuckDB to an existing Mech, put `duckdb` in `conf/export.yaml`, then
`uv add 'linkml-store>=0.3.2'` and `just install`. Without the package,
`just export` fails and says exactly that.

## Loading into a database

Some uses need the records in a running database, not a file. `just load`
fills one, through linkml-store, and counts the data back:

```bash
just load mongodb              # refuses if the collection already holds data
just load neo4j --replace      # replace what is there
```

| Target | What it holds | `--replace` deletes |
|---|---|---|
| `mongodb` | One collection, named for the records folder, one document per record, nested as in the YAML | That collection only |
| `neo4j` | A graph. Every object is a node labelled with its class; every field holding objects is an edge named for the field; each ontology term is one shared node per CURIE. Nested objects get path ids such as `VBO:0000736/origins/0` | **Every node in the Neo4j database.** Give the Mech a database of its own |

A Neo4j query, on GoatMech: the features of the Boer and their terms.

```cypher
MATCH (b:GoatBreed {id: 'VBO:0000736'})-[:distinguishing_features]->(f)-[:term]->(t)
RETURN f.preferred_term, t.label
```

Copier asks `load_targets` when the Mech is made; each choice adds
linkml-store, with that target's extra, to the Mech's dependencies.
Addresses live in `conf/load.yaml`. `${NAME}` in an address is read from
the environment, so passwords stay out of the repository, and addresses are
printed with passwords hidden. A password must not contain `@` or `:`:
linkml-store splits the address on them.

```yaml
targets:
  mongodb: "mongodb://localhost:27017/goatmech"
  neo4j: "neo4j://neo4j:${NEO4J_PASSWORD}@localhost:7687/neo4j"
```

linkml-store reaches other databases too. These were tried and left out
for now:

- **Postgres** (through Ibis): linkml-store 0.3.2 passes the whole address
  where Ibis expects a host name, so it cannot connect.
- **Solr**: linkml-store can query Solr but not insert into it.
- **BigQuery, Snowflake, Dremio, ClickHouse, MySQL**: not tried; each needs
  an account or a server this work did not have.
- **ChromaDB**: a vector store; it needs an embedding model, which is a
  separate decision.

## Nested data in tables

A record nests things: descriptors, ontology terms, quotes. Tables cannot,
so CSV and TSV come in two layouts, set by `tabular_layout`:

- **`per_class`** (the default): one table per class, one file per table,
  zipped as `<slug>-tables-csv.zip`. This is the layout of the SQL export,
  made by LinkML's `gen-sqltables`. A nested row points at its parent with a
  `<ParentClass>_id` column, and a `parent_slot` column names the field it
  came from. That keeps a record's own quotes apart from the quotes for its
  description, which would otherwise share one column.
- **`flat`**: one row per record, in `<slug>-records.csv`. A list of plain
  values is joined with ` | `; a nested object is written as JSON in its
  cell. Easy to open; harder to query.

## RDF needs prefixes and URIs

JSON-LD and Turtle turn every CURIE in a record into an IRI through the
schema's `prefixes`. A prefix with no URI makes a broken IRI, so the export
checks every IRI and fails on one that is not `http(s)`, naming the prefix
to declare. The [`design-mech-schema`](skills/design-mech-schema.md) skill
makes prefixes and URIs part of every new schema: each prefix declared with
its full URI, looked up rather than composed; standard properties for slots
that mean the same thing (`name` is `schema:name`, `description` is
`dcterms:description`, `synonyms` is `skos:altLabel`, as the template sets
them); and a `meaning` for enum values that stand for ontology terms.

JSON-LD and Turtle are written from one RDF graph, so they say the same
thing.

## Known limits

- LinkML's own SQL loader (`SQLStore`) fails on a Mech's schema in linkml
  1.11 (dates, and imports given as a path), so the database is filled by
  the Mech's `export.py`, into the tables `gen-sqltables` defines.
- linkml-runtime 1.11 misreads a one-key item in a list of objects, such
  as `{purpose: DAIRY}`, when that key is an enum. The export gives such an
  item a second, empty field before loading it; the data is unchanged.
- Classes and slots from the shared `mech_shared` module take its URIs,
  under `https://w3id.org/kg-microbe/mech-shared/`.
- Parquet and Croissant are not LinkML-native and not yet offered
  ([#21](https://github.com/monarch-initiative/mechmaker/issues/21)).
