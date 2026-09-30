# The GoatMech domain model

This file is the design record for what GoatMech knows. mechmaker
wrote the skeleton. The `design-mech-schema` skill fills it in, and every
later schema change updates it. Sections marked TODO are not done.

## What a record is

One record is one goat breed.

TODO: Define a goat breed in two or three sentences. Say what counts
as one and what does not. Name the nearest things that are *not* records
here, and where they go instead (a field on a record, another Mech, nowhere).

## Identity

Records are keyed by VBO CURIEs where a term exists, descending from `VBO:0400025`.
Where none exists, the record mints `goatmech:<slug>` and can be
re-grounded later.

The filename stem is derived from `name`: lowercase, runs of non-alphanumerics
become one underscore.

TODO: State the granularity rule. When are two candidates one record, and
when are they two? When is a subtype its own record?

## Sections

TODO: For each section of a record, give its purpose, its ontology, and one
worked example. Start from the scaffold below and cut what the domain does
not need.

| Section | Ontology | Purpose |
|---|---|---|
| `organisms` | NCBITaxon under `NCBITaxon:1` | TODO |
| `units` | UO under `UO:0000000` | TODO |
| `evidence` | PMID, DOI | Record-level citations |
| `discussions` | none | Open questions and knowledge gaps (mech_shared) |
| `datasets` | accessions | Public datasets (mech_shared) |

## Sources

TODO: What feeds curation: literature queries, databases, existing
knowledge bases, ontologies. Each source goes in
`curation/source_queue.tsv` with its license.

## Out of scope

TODO: What this Mech will not record, and why.

## Related Mechs

TODO: Mechs whose records this one links to or overlaps with. See
https://monarch-initiative.github.io/mechregistry/.
