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
| `kgx` | `<slug>-kgx_nodes`, `_edges` (`.jsonl`, `.tsv`) | A knowledge graph in KGX: Biolink associations from each record to its terms. Optional, see below |
| `kgx_maximal` | `<slug>-kgx_maximal_nodes`, `_edges` | The whole record graph in KGX: every object a node. Optional, see below |
| `csv`, `tsv` | see below | Spreadsheets and data frames |

## Choosing

Copier asks `output_formats` when the Mech is made. The default is every
format but TSV, DuckDB and the two KGX formats. Change the choice any time in `conf/export.yaml`:

```yaml
formats:
  - yaml
  - json
  - ttl
tabular_layout: per_class
```

## KGX: a knowledge graph

[KGX](https://github.com/biolink/kgx) is the node and edge format of the
Monarch knowledge graph and other Biolink graphs. A Mech can write it two
ways, after [DisMech's two KGX exports](https://github.com/monarch-initiative/dismech/tree/main/src/dismech/export):

- **`kgx`**: one Biolink association per term a record's section binds,
  from the record to the term. A record that binds the same term twice gives
  one edge. Evidence goes on the edge: references in `publications`, and
  each quote in `supporting_text` as
  `[PMID:1] [SUPPORT] the quote --- Explanation: why`.
- **`kgx_maximal`**: every object in a record is a node, labelled
  `<slug>:<Class>`, and every field holding objects is an edge,
  `<slug>:<field>`. Records also carry their Biolink category; ontology
  terms are shared nodes with Biolink categories. Nothing is left out, and
  most of it is local to the Mech.

Every edge carries `primary_knowledge_source` (`infores:<slug>`),
`knowledge_level` (`knowledge_assertion`) and `agent_type`
(`manual_validation_of_automated_agent`: agents curate, people review), and
an id hashed from subject, predicate and object, stable between exports.

`conf/kgx.yaml` maps the Mech onto Biolink: the record's category, and for
each record section, the predicate from the record to its terms and the
terms' category. The template starts every section at `biolink:related_to`,
which is never wrong, with categories from the ontology catalog. The
`design-mech-schema` skill chooses sharper ones.

```yaml
record_category: biolink:OrganismTaxon
sections:
  origins:
    predicate: biolink:related_to
    category: biolink:GeographicLocation
  measurements:
    predicate: biolink:related_to
    category: biolink:NamedThing
    term_field: trait        # the item's field that holds the term
```

The export checks every category and predicate against the Biolink model:
a category must be a concrete class (not a mixin, not abstract), and a
predicate must descend from `related_to`. Either fails the export. A
predicate whose Biolink domain or range does not fit the categories is a
warning. For example, `biolink:has_phenotype` expects a biological entity,
so it warns from an `OrganismTaxon`. The check uses the `biolink-model`
package, which the template adds only when a KGX format is chosen.

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
| `neo4j` | A graph. Every object is a node labelled with its class and with `MechNode`, with the Mech's slug in `mech`; every field holding objects is an edge named for the field; each ontology term is one shared node per CURIE. Nested objects get path ids such as `VBO:0000736/origins/0` | This Mech's nodes only (those with its `mech`). Several Mechs can share one database |

A Neo4j query, on GoatMech: the features of the Boer and their terms.

```cypher
MATCH (b:GoatBreed {id: 'VBO:0000736'})-[:distinguishing_features]->(f)-[:term]->(t)
RETURN f.preferred_term, t.label
```

Neo4j is written with batched Cypher and an index on `MechNode.id`, not
with linkml-store's collection inserts, which match each edge's ends by
reading every node. On GoatMech's records copied 200 times, 22,824 nodes
and 28,800 edges load in about 4 seconds.

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
- The KGX files are not run through the `kgx` package's validator, which
  brings over thirty dependencies; the export's own checks cover categories,
  predicates and dangling edges.
- Parquet and Croissant are not LinkML-native and not yet offered
  ([#21](https://github.com/monarch-initiative/mechmaker/issues/21)).
