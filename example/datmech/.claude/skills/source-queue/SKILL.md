---
name: source-queue
description: >-
  Triage the sources that feed DaTMech curation in
  curation/source_queue.tsv: add candidates, check licenses and access, rank,
  and decide what to adopt next. Use when asked what to curate from, whether
  a database or corpus is usable, or to plan bulk seeding.
---

# The source queue

`curation/source_queue.tsv` ranks the sources that feed curation. The
columns are explained in `curation/README.md`.

## Adding a candidate

For each source, find out and write down:

- **What it gives.** Which record sections it could fill, and for roughly
  how many records. Measure with a sample, not a guess.
- **License.** Read the actual terms. Write `UNKNOWN` if you could not find
  them. Never infer a license from a site's look.
- **Access.** API, bulk download, or pages only. Rate limits. Whether
  identifiers are stable.
- **Grounding.** Does it use CURIEs the schema accepts, or does it need
  mapping?

## Ranking

Rank by value per unit of effort, and say why in `notes`. A small, clean,
openly licensed source that fills a required section beats a large one that
needs mapping.

## Adopting

A source is `ADOPTED` when merged code or a written procedure uses it. The
pull request that adds the ingest code also changes the row. Ingest code
writes through `write_validated_record`, runs dry by default, and records a
history entry for each bulk change.

Bulk-seeded records start as `DRAFT`. Their evidence must still validate.
Seeding does not excuse a record from the evidence rules.
