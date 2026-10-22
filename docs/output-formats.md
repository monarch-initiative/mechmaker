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
| `parquet` | `<slug>-tables-parquet.zip` | Data frames and analytics engines: one typed Parquet file per class. Optional, see below |
| `sql` | `<slug>-schema.sql`, `<slug>-records.sql` | The schema as SQL DDL, and the data as SQL to load anywhere |
| `kgx` | `<slug>-kgx_nodes`, `_edges` (`.jsonl`, `.tsv`) | A knowledge graph in KGX: an edge from each record to each term it binds. See below |
| `kgx_maximal` | `<slug>-kgx_maximal_nodes`, `_edges` | The whole record graph in KGX: every object a node. See below |
| `csv`, `tsv` | see below | Spreadsheets and data frames |
| `sssom` | `<slug>-mappings.sssom.tsv` | [SSSOM](https://mapping-commons.github.io/sssom/): each record's mappings to identifiers elsewhere. Optional, see below |
| `croissant` | `<slug>-croissant.json` | [Croissant](https://docs.mlcommons.org/croissant/) metadata: the other files, the records field by field, and where the data came from. Optional, see below |

## Choosing

Copier asks `output_formats` when the Mech is made. The default is every
format but TSV, DuckDB, Parquet, the two KGX formats, SSSOM and Croissant. Change the choice any time in `conf/export.yaml`:

```yaml
formats:
  - yaml
  - json
  - ttl
tabular_layout: per_class
```

## Where the files are listed

The file names do not change from one release to the next, so a link to
`releases/latest/download/<file>` always reaches the newest copy. Two
places use those links:

- **The docs site's Downloads page** (`docs/downloads.md`), written by
  `just docs-build` from `conf/export.yaml`: each file, what it is, and a
  link to it in the latest release. Without `release-records`, it lists the
  files `just export` writes, unlinked. It is generated; change the formats,
  not the page.
- **The registry entry** (`registry/<slug>.md`), when `release-records` is
  on: one product per file, each with its format from MechRegistry's list
  (`ttl` is `turtle` there). After a change to `conf/export.yaml`,
  `python -m <slug>.export --registry-products` prints the new products; a
  test fails until the entry lists them.

## KGX: a knowledge graph

[KGX](https://github.com/biolink/kgx) is the node and edge format of the
Monarch knowledge graph and other Biolink graphs. A Mech can write it two
ways, after [DisMech's two KGX exports](https://github.com/monarch-initiative/dismech/tree/main/src/dismech/export):

- **`kgx`**: one association per term a record's section binds,
  from the record to the term. A record that binds the same term twice gives
  one edge. Evidence goes on the edge: references in `publications`, and
  each quote in `supporting_text` as
  `[PMID:1] [SUPPORT] the quote --- Explanation: why`.
- **`kgx_maximal`**: every object in a record is a node, labelled
  `<slug>:<Class>`, and every field holding objects is an edge,
  `<slug>:<field>`. Records also carry their record category; ontology
  terms are shared nodes with their section's category. Nothing is left
  out, and most of it is local to the Mech.

Every edge carries `primary_knowledge_source` (`infores:<slug>`),
`knowledge_level` (`knowledge_assertion`) and `agent_type`
(`manual_validation_of_automated_agent`: agents curate, people review), and
an id hashed from subject, predicate and object, stable between exports.

`conf/kgx.yaml` maps the Mech onto a graph: the record's category, and for
each record section, the predicate from the record to its terms and the
terms' category.

### With Biolink, or without

By default the graph uses the [Biolink model](https://biolink.github.io/biolink-model/),
as the Monarch graph does. The template starts every section at
`biolink:related_to`, which is never wrong, with categories from the
ontology catalog. The `design-mech-schema` skill chooses sharper ones.

Biolink is biomedical. A Mech about goat breeds fits it; a Mech about
software ingests or soil horizons may not. Answer no to `kgx_biolink` when
generating, or set `biolink: false` in `conf/kgx.yaml` later. The graph
then uses the Mech's own terms: records are `<slug>:<RecordClass>`, terms
`<slug>:<Noun>`, and each section's predicate `<slug>:<section>`. Nothing
checks them against a model, and `biolink-model` is not installed. Every
category and predicate must still be a CURIE. The provenance fields keep
Biolink's values for `knowledge_level` and `agent_type`, since KGX uses
them either way.

```yaml
biolink: true
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

With Biolink, the export checks every category and predicate against the model:
a category must be a concrete class (not a mixin, not abstract), and a
predicate must descend from `related_to`. Either fails the export. A
predicate whose Biolink domain or range does not fit the categories is a
warning. For example, `biolink:has_phenotype` expects a biological entity,
so it warns from an `OrganismTaxon`. The check uses the `biolink-model`
package, which the template adds only when a KGX format is chosen with
Biolink.

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

## Parquet, an optional extra

The Parquet export holds the tables of the SQLite export, one Parquet file
per class, zipped as `<slug>-tables-parquet.zip`: the `per_class` layout
below, whatever `tabular_layout` says. Each column takes the Arrow type of
its `gen-sqltables` declaration (integers, floats and booleans as such;
text, dates and anything else as strings). A value that does not fit its
declared type turns its column into text rather than fail the export. Each
file is read back, and its rows and columns must match its SQLite table.

The files are written with [pyarrow](https://arrow.apache.org/docs/python/),
which a Mech installs only when `output_formats` includes `parquet`. To add
Parquet to an existing Mech, put `parquet` in `conf/export.yaml`, then
`uv add 'pyarrow>=18.0'` and `just install`. Without the package,
`just export` fails and says exactly that.

Unzipped, each file reads directly in pandas, Polars or DuckDB, and the
tables join on their `_id` columns as in SQLite:

```sql
SELECT * FROM 'GoatBreed.parquet';
```

MechRegistry has no `parquet` format, so the registry entry lists the zip
as `format: other`.

## SSSOM: mappings to other identifiers

[SSSOM](https://mapping-commons.github.io/sssom/), the Simple Standard for
Sharing Ontological Mappings, is how ontologies and databases publish which
of their entries match which elsewhere: Mondo's mappings to OMIM and
Orphanet, Bioregistry's between registries. A Mech that chooses `sssom`
publishes its records' mappings the same way, so others can join its
records to their own data.

Choosing it adds a section to the record, `mappings`, whose fields are
SSSOM's:

```yaml
mappings:
  - predicate_id: skos:exactMatch          # or closeMatch, broadMatch, narrowMatch, relatedMatch
    object_id: OMIM:143100                 # its prefix declared in the schema, with its URI
    object_label: Huntington disease
    mapping_justification: semapv:UnspecifiedMatching
    confidence: 0.9                        # optional
    evidence:
      - reference: PMID:<n>
        supports: SUPPORT
        snippet: <a quote naming both>
```

The record is the subject. The predicates are the five
[SKOS](https://www.w3.org/TR/skos-reference/#mapping) mapping relations,
which SSSOM recommends; `predicate_modifier: Not` states that a mapping
does not hold. The justification says how the mapping was found, from
[SEMAPV](https://mapping-commons.github.io/semantic-mapping-vocabulary/).
A mapping is a claim like any other: it needs evidence, and its object
must be checked at its source. The Mech's `curate-mappings` skill says how;
mechmaker's `search-mappings` skill finds the sets that already exist,
which a survey reads before deciding whether a Mech needs its own.

`just export` writes every record's mappings as one mapping set, one row
per mapping: the record's id and name as subject, the mapping's fields, its
evidence's references (as URLs where the schema's prefixes expand them) in
`see_also`, and its notes in `comment`. The metadata above the table gives:

- `curie_map`: every prefix the rows use, with the URI the schema declares
  for it. A mapping whose prefix the schema does not declare fails the
  export, as in RDF.
- `mapping_set_id`: the file's address in the latest release, which is
  where it is published.
- `mapping_set_version` (the latest git tag), `license`, a title and
  description, and creators from `registry/<slug>.md` (with ORCIDs as
  `creator_id`).

The export also refuses a mapping with no justification, a record mapped to
itself, and a mapping a record states twice. Then it reads the file back
with [sssom-py](https://github.com/mapping-commons/sssom-py), the reference
library: the file must parse, validate against the SSSOM schema, declare a
prefix for every CURIE, and give back every row. Every Mech has sssom-py
already, because oaklib depends on it; choosing `sssom` also names it as a
dependency of the Mech's own, so the export keeps the version it needs.

The registry entry lists the file as a `MappingProduct` in format `sssom`.

To add SSSOM to an existing Mech, take this template change (the
`sync-mech` skill) and add `sssom` to the `output_formats` answer, which
adds the schema's section, the skill and the dependency. By hand: copy the
`Mapping` class, the `mappings` slot on the record class and its slots, the
three enums and the `semapv` prefix from a Mech that has them; put `sssom`
in `conf/export.yaml`; `uv add 'sssom>=0.4.17'` and `just install`.
Without the package, `just export` fails and says so; without the
`mappings` slot, it says that.

## Croissant: metadata about the data

[Croissant](https://docs.mlcommons.org/croissant/docs/croissant-spec-1.1.html)
is MLCommons' JSON-LD vocabulary for describing a dataset, read by dataset
search engines and machine learning tools. It is not a data format: it
describes the other files, so a Mech that chooses `croissant` must also
choose `csv`, `tsv`, `parquet` or `json`. The export writes it last, as
`<slug>-croissant.json` (Croissant 1.1), beside the files it describes. It
holds:

- **The dataset**: name, description, home page, repository, version (the
  latest git tag), license, creators (with ORCIDs), keywords and a BibTeX
  citation, read from `registry/<slug>.md`, so keep that entry current.
  How the records are made (agent curation, human review, the evidence
  policy, the disclaimer) goes in Croissant's Responsible AI terms
  (`rai:dataCollection`, `rai:machineAnnotationTools`, `rai:dataLimitations`).
- **Every file**, with its size and sha256. Each `contentUrl` is the file's
  name: the metadata travels with the files, in `build/export/` and in
  each release.
- **The records, field by field**, as RecordSets. They come from the first
  of these the export wrote: the per-class tables (CSV, TSV or Parquet, one
  RecordSet per table, typed from `gen-sqltables`; a column that points at
  another table says so in its description); the flat CSV or TSV; or the
  JSON Lines records (the single, plain values every record has).
- **Where the data came from**, in [PROV-O](https://www.w3.org/TR/prov-o/):
  - each structured ingest in `conf/ingests.lock.yaml`, as
    `prov:wasDerivedFrom`: the ingest's release (or Koza run), its files with
    their checksums, and the sources upstream of it, by infores id, version
    and retrieval date;
  - each ontology the records bind, from `conf/oak_config.yaml`: an OBO
    Foundry ontology by its PURL, with its OLS page;
  - `data_sources` from `registry/<slug>.md`, each under the PROV relation
    it names (`prov:hadPrimarySource`, `prov:wasDerivedFrom`, `prov:used`);
  - every work the records cite as evidence, as a schema.org `citation`
    with its identifier, its URL where the schema's prefixes expand it, and
    its title from `references_cache/`.

The export reads the file back with MLCommons'
[mlcroissant](https://pypi.org/project/mlcroissant/): it must validate, and
every RecordSet must load with the rows the export wrote. Loading checks
each file's sha256, so a file changed after the export fails. Warnings
(before the first release tag, the version is not `MAJOR.MINOR.PATCH`) are
printed and do not fail. mlcroissant brings pandas and scipy, so a Mech
installs it only when `output_formats` includes `croissant`. To add Croissant
to an existing Mech, put `croissant` in `conf/export.yaml`, then
`uv add 'mlcroissant>=1.1.1'` and `just install`.

Each check runs in its own process with an empty cache: mlcroissant caches
an archive's contents by its name, so a rebuilt zip would otherwise be read
as it was.

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
- Parquet has one layout only, one table per class; there is no flattened
  Parquet to match `tabular_layout: flat`.
- Croissant names a link between tables in a column's description, not with
  `references`: mlcroissant 1.1.1 joins the tables on a reference when it
  loads them, which changes the rows a table gives, and its 1.1 syntax for
  one crashes the validator.
- SSSOM's released schema (sssom-py 0.4.17) accepts nine SEMAPV
  justifications. SEMAPV's newer `semapv:AgentBasedMatching`, which fits an
  agent's mapping, is not among them, so the Mech offers only the nine and
  an agent's mapping is `semapv:UnspecifiedMatching`. Its `curate-mappings`
  skill says when each applies.
- The SSSOM export writes TSV only; `sssom convert` turns it into OWL,
  JSON or RDF.
- Croissant names each ontology, but not its version: a Mech does not record
  the version it checked terms against.
