# The IngestMech domain model

This file is the design record for what IngestMech knows. Every schema
change updates it.

## What a record is

One record is one Monarch ingest: a repository in the
`monarch-initiative` GitHub organization that downloads files from upstream
sources and transforms them with koza into Biolink associations for the
Monarch knowledge graph.

A repository is an ingest here if it has the koza template layout: a
`download.yaml` and a `src/versions.py`. 25 of the organization's 40
repositories named `*ingest*` had it on 2026-09-30.

Not records:

| Candidate | Where it goes instead |
|---|---|
| An upstream source, such as ZFIN | An entry in `upstream_sources` of every ingest that reads it |
| One koza transform, such as `zfin_orthology` | A name in `koza_transforms` |
| A tool repository, such as `koza-ingest-template` or `monarch-ingest` | Nowhere |
| An ingest in an older layout, such as `alliance-disease-association-ingest` | Nowhere, until it moves to the template |

## Identity

Records mint `ingestmech:<repository-name>`, for example
`ingestmech:omim-ingest`. `name` is the repository name, so the file is
`data/ingests/omim_ingest.yaml`.

Granularity rule: one repository, one record. A repository with several
transforms is still one record. A renamed repository keeps its record, with
the old name in `notes`.

## Sections

| Section | Vocabulary | Filled by | Purpose |
|---|---|---|---|
| `repository`, `source_commit` | none | conversion | Where the ingest lives, and the commit the record was read from. Evidence quoting the repository is pinned to that commit |
| `code_license` | SPDX | conversion, from `.copier-answers.yml` | Terms of the ingest's own code |
| `upstream_sources` | infores | conversion, from `src/versions.py`; then curation | Each source the ingest downloads from |
| `upstream_sources[].files` | none | conversion, from `download.yaml` | The files, as the ingest names them |
| `upstream_sources[].access` | `AccessEnum` | conversion (a `{KEY}` placeholder in a URL means `REGISTRATION_REQUIRED`); curation confirms | What it takes to download |
| `upstream_sources[].data_license` | SPDX where one applies | curation, from the source's own terms | Terms of the upstream data. The ingests do not record this |
| `upstream_sources[].description`, `homepage` | none | curation, from the source or the infores catalog | What the source is |
| `organisms` | NCBITaxon under `NCBITaxon:1` | conversion where the README lists species by NCBITaxon id; else curation | Species whose data the ingest takes |
| `associations` | Biolink classes as `biolink:` CURIEs | conversion, from the README's Biolink lines | What the ingest writes |
| `koza_transforms` | none | conversion, from each `src/*.yaml` | The transforms in the repository |
| `evidence` | url, PMID, DOI | curation | Record-level citations, such as the source's paper |
| `discussions` | none | conversion and curation | Gaps, such as an infores id missing from the catalog, or a license not found |

Worked example: `omim-ingest` reads `infores:omim`, whose one file is
`https://data.omim.org/downloads/{MONARCH_OMIM_DOWNLOAD_KEY}/morbidmap.txt`.
The placeholder makes its access `REGISTRATION_REQUIRED`, and the README
says so too: "requires access key".

## Evidence

Facts copied from an ingest are quoted from its own files, fetched from
`raw.githubusercontent.com` at `source_commit` with `url:` references, for
example
`url:https://raw.githubusercontent.com/monarch-initiative/omim-ingest/<sha>/download.yaml`.
The conversion script writes these and the validator checks them.

Facts about an upstream source are quoted from the source: its terms page,
its paper, or the Biolink information resource catalog pinned to a commit.
A page that cannot be fetched is not quoted from memory. The gap becomes a
`KNOWLEDGE_GAP` discussion.

`evidence_source` says which: `INGEST_REPOSITORY`, `SOURCE_DOCUMENTATION`,
`REGISTRY` or `PUBLICATION`.

## Sources

See `curation/source_queue.tsv`. The ingest repositories feed the
conversion. The Biolink information resource catalog checks infores ids.
Each upstream source's own site gives its terms.

## Out of scope

Data from the sources themselves. IngestMech records how the knowledge
graph is fed, not what it holds.

## Related Mechs

None in the registry overlaps. The Monarch Mechs, such as DisMech, consume
the knowledge graph these ingests build.
