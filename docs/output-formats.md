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
| `sql` | `<slug>-schema.sql`, `<slug>-records.sql` | The schema as SQL DDL, and the data as SQL to load anywhere |
| `csv`, `tsv` | see below | Spreadsheets and data frames |

## Choosing

Copier asks `output_formats` when the Mech is made. The default is every
format but TSV. Change the choice any time in `conf/export.yaml`:

```yaml
formats:
  - yaml
  - json
  - ttl
tabular_layout: per_class
```

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
- Parquet, DuckDB and Croissant are not LinkML-native and not yet offered
  ([#21](https://github.com/monarch-initiative/mechmaker/issues/21)).
