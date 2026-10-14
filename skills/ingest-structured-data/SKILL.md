---
name: ingest-structured-data
description: >-
  Find, offer and set up structured data ingests for a Mech: the Monarch
  Initiative's ingests (one per source, such as ZFIN, OMIM, HPO annotations,
  ClinVar, Reactome, each released monthly as KGX nodes and edges), searched
  in mechmaker's catalog and offered to the person as an optional menu; and
  the Mech's own reproducible ingests, written with Koza, for a source no
  ingest covers. Turns on the template's `ingests` and `koza_ingests`
  answers, fetches and locks a release, and seeds records from rows with
  evidence that quotes sources. Use while surveying a domain whose sources
  are databases, when asked which Monarch data a Mech can draw on, or how to
  ingest a structured source reproducibly.
---

# Structured data ingests

Many sources a Mech draws on are databases: tables of genes, phenotypes,
variants, pathways. The Monarch Initiative already ingests dozens of them.
Each ingest is a repository that downloads one source, turns it into KGX
nodes and edges with [Koza](https://koza.monarchinitiative.org/), and
publishes the result as a GitHub release every month, with a
`release-metadata.yaml` giving each file's sha256 and the upstream
versions. A Mech that reuses one fetches tested, Biolink-shaped rows instead
of parsing the source again.

| Step | Who | Output |
|---|---|---|
| 1. Find | you, with the script | the ingests that read the Mech's sources |
| 2. Judge the fit | you | which ones serve the records, and how |
| 3. Offer | you and the person | their choice, or none |
| 4. Turn on | Copier | `conf/ingests.yaml`, `just ingest`, the `structured-ingests` skill |
| 5. Fetch and trial | you | a locked release, and a few seeded records |
| 6. The Mech's own | you, with Koza | `ingests/<name>/`, for a source no ingest covers |

Most Mechs need no ingest. A Mech curated from papers, or about things no
database tables, is complete without one. The question is optional, and
"none" is an answer to accept, not argue with.

## 1. Find

A script comes with this skill, in the `scripts/` folder beside this file;
`<scripts>` stands for that folder's path. It needs only Python 3.

```bash
python3 <scripts>/ingest_catalog.py list
python3 <scripts>/ingest_catalog.py search zebrafish phenotype
python3 <scripts>/ingest_catalog.py search infores:omim       # the ingests that read a source
python3 <scripts>/ingest_catalog.py show hpoa clinvar          # in full, with the conf entry
python3 <scripts>/ingest_catalog.py releases hpoa              # latest release, file sizes (network)
```

Search with the record entity's words, the species, and each source in the
survey's source table, by name and by infores id. The catalog is
`ingest_catalog` in mechmaker's `copier.yml`; its reference page is
<https://monarch-initiative.github.io/mechmaker/reference/ingests/>.

The catalog holds the ingests the Monarch KG is built from (monarch-ingest's
`src/monarch_ingest/ingests.yaml`), and three that left the build but still
release (CTD, MeDIC, MAxO annotations). KG-Registry's `kg-monarch` entry
lists fewer sources and two that are gone; trust the catalog over it for
Monarch, and use `search-kg-registry`'s `used-by` for ingests elsewhere
(KG-Hub's graphs ingest other sources the same way).

## 2. Judge the fit

An ingest's rows are associations: gene to phenotype, variant to disease,
chemical to pathway. A Mech's records are entities. For each candidate,
say how one serves the records:

- **Seeds.** The rows name the entities records are about, keyed by the
  same identifiers: an HPO annotation row names a disease by its OMIM or
  ORPHA id, a ClinVar row a variant. Records can be created from them.
- **Sections.** Rows about a record fill one of its sections: a disease's
  phenotypes from HPO annotations, a gene's orthologs from PANTHER.
- **Leads.** Rows cite publications (the `publications` column); each is a
  paper to read and quote.
- **No fit.** The ingest covers the domain but not what the records say.

Check, before offering it:

- **Identifiers.** Do the rows' CURIEs (their `subject` and `object`) use
  the prefixes the Mech's records and ontologies use? A Mech keyed by MONDO
  reading OMIM-keyed rows needs a mapping, from MONDO's own xrefs; say so.
- **Size.** `releases` gives each file's size. GO annotations are about
  1.1 GB, BioGRID and PANTHER hundreds of MB. A Mech can fetch fewer files
  than the catalog lists.
- **License.** The ingest's code is open; the upstream data has its own
  terms, which the ingest does not record. Read the source's terms (the
  IngestMech example in mechmaker's `example/` curates some). Data that may
  not be redistributed must not be copied into records: tell the person,
  and stop for that source, as `convert-knowledge-base` does.
- **Status.** `show` says whether the Monarch KG still uses it; one that
  left the build may stop releasing.

## 3. Offer

Show the person the ingests that fit, each in one line: what it covers,
how it would serve the records, its size, and any license or identifier
caveat. Then ask which to use, saying that none is fine. Put their answer
in `requests.yml`, in their words. Never pick one for them.

The same menu is the Copier `ingests` question: a person generating a
Mech by hand chooses there.

## 4. Turn it on

For a new Mech, put the keys in `answers.yml`:

```yaml
ingests: [hpoa, omim]     # from the catalog; [] for none
koza_ingests: false       # true when the Mech will write its own (section 6)
```

For an existing Mech:

```bash
uvx copier update --vcs-ref=:current: --skip-answered --defaults --data 'ingests=[hpoa, omim]'
```

The Mech gets `conf/ingests.yaml` (one entry per ingest: its repository,
sources and files), `src/<slug>/ingest.py` with `just ingest`, `just ingests`
and `just ingest-check` (a gate in `just qc`), and the Mech's own
`structured-ingests` skill. A Mech made before the feature takes it with
`sync-mech` first.

## 5. Fetch and trial

In the new Mech:

```bash
just ingest hpoa             # fetch the latest release into build/ingest/hpoa/
```

Every file is checked against the sha256 its release publishes, and
`conf/ingests.lock.yaml` records the release tag and each file's sha256.
Commit the lock. A later run takes the same release and fails on any
changed byte; `--update` moves to the newest. That is what makes the Mech's
seeding reproducible: the lock names exactly which rows it read.

Then seed: a conversion script reads rows with `rows(name, file)` and runs
through the Mech's `just convert`, as `convert-knowledge-base` describes
(trial set, `--limit`, `qc-full`, then batches). The Mech's
`structured-ingests` skill has the script's shape. The rules:

- A row is a seed, never a quote. Ids, terms and names may be copied, and
  are checked like any value. A claim quotes a source: fetch a paper from
  the row's `publications`, and quote the sentence that says it.
- One record is not one row. Group rows by the entity the record is about.
- What the rows never say (often what the Mech is for) becomes curation:
  `CURATION_TODO` discussions on the records.
- Add each ingest to `curation/source_queue.tsv`, with the upstream data
  license as read, or UNKNOWN. `register-mech` lists adopted ones in the
  registry entry.

## 6. The Mech's own ingest, with Koza

For a structured source no ingest covers (a download, a table, an API
dump), write one with Koza instead of a one-off script: the download list,
the transform and the output are files, rerun the same way, and locked.
Turn it on with `koza_ingests: true` (it adds `koza` and `kghub-downloader`
to the Mech). Then:

```bash
just new-ingest <name>        # ingests/<name>/download.yaml, <name>.yaml, <name>.py
just ingest <name>            # download, transform, lock
```

What to know about Koza (2.6.2, checked 2026-10-14):

- **Command.** `koza transform CONFIG.yaml [INPUT_FILES]... -o DIR -f tsv`.
  Writers are `tsv`, `jsonl` and `passthrough` only; `-f parquet` and
  `-f kgx` are rejected or fail, whatever the docs say. Output files are
  `<name>_nodes.tsv` and `<name>_edges.tsv`.
- **Config.** `name`; one `reader` (`format`: csv, jsonl, json or yaml;
  `files`; for csv `delimiter`, `columns`, `header_mode`); `transform`
  (`code`, `mappings`, extra keys); `writer` (`node_properties`,
  `edge_properties`: the TSV columns). `reader.files` resolve from the
  config's own folder, so the Mech's runner passes the downloaded files'
  full paths instead.
- **Python.** A function decorated `@koza.transform_record()` gets
  `(koza_transform, row)` and yields or returns entities;
  `@koza.transform()` gets every row at once. `koza_transform.lookup(...)`
  reads mapping files. Entities must be Biolink pydantic classes
  (`biolink_model.datamodel.pydanticmodel_v2`), or objects with `id` and
  `name` (a node) or `subject`, `predicate`, `object` (an edge). **A plain
  dict is rejected.**
- **Ids are stable.** Make them from the row. Many Monarch transforms use
  `uuid`; a Mech's must not, or every run differs and the lock cannot tell
  a changed source from a changed transform.
- **Downloads.** kghub-downloader's `download.yaml` is a top-level list of
  `- url:` and `local_name:` items (`{ENV_VAR}` in a url is filled from the
  environment). koza-ingest-template's empty `downloads: []` crashes
  kghub-downloader 0.5.0; use the list form.
- **Tests.** Koza's documented `mock_koza` fixture is not in 2.6.2. Call the
  decorated function with a `unittest.mock.MagicMock` for the transform
  and a row dict, and assert on what it yields.

If the source would serve other knowledge graphs too, offer the person the
other path: a repository of its own from
[koza-ingest-template](https://github.com/monarch-initiative/koza-ingest-template),
with monthly releases, that the Mech then reads as `kind: release` and
that Monarch could adopt. Its versions are recorded (`src/versions.py`),
not pinned; the release is the fixed point.

## Keeping the catalog current

The catalog belongs to mechmaker. To add or refresh an entry, read
monarch-ingest's `src/monarch_ingest/ingests.yaml` and the build receipt of
the latest KG release
(`https://data.monarchinitiative.org/monarch-kg/latest/metadata.yaml`), edit
`ingest_catalog` and the `ingests` choices in `copier.yml` together, run
`uv run python scripts/gen_docs.py` (it rewrites the script's
`ingest_catalog.json`), and check every entry against GitHub:

```bash
python3 <scripts>/ingest_catalog.py check
```

## Report

Say which ingests were found for the domain, which the person chose and
why the others were left, the release each is locked at, how many records
the trial seeded, and the license and identifier caveats still open.
