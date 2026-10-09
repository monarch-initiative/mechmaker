# The DaTMech domain model

This file is the design record for what DaTMech knows. mechmaker
wrote the skeleton. mechmaker's `design-mech-schema` skill fills it in, and every
later schema change updates it. Sections marked TODO are not done.

## What a record is

One record is one ZIP code area.

TODO: Define a ZIP code area in two or three sentences. Say what counts
as one and what does not. Name the nearest things that are *not* records
here, and where they go instead (a field on a record, another Mech, nowhere).

## Identity

No ontology keys records. A record takes a stable identifier from a source
when one names it uniquely, else a minted id, `datmech:<uuid>`
(`just new-record` mints one when given no `--id`).

An id never changes when a record is renamed, and no two records share one.

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
| `chemical_entities` | CHEBI under `CHEBI:24431`, checked with `ols:chebi` | TODO |
| `organisms` | NCBITaxon under `NCBITaxon:1`, checked with `ols:ncbitaxon` | TODO |
| `environments` | ENVO under `ENVO:01000254`, checked with `ols:envo` | TODO |
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
