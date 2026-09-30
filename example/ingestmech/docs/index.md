# IngestMech

IngestMech records the data ingests of the Monarch Initiative knowledge graph: the upstream sources each one reads, the files it fetches, the terms those sources are licensed under, and what it produces.

IngestMech is a **Mech**: a knowledge base where AI agents do most of
the curation and people review their work. It keeps one record per
ingest, and every record follows the same rules.

- **One file per ingest**, validated against a
  [LinkML schema](elements/index.md).
- **Standard vocabulary.** Records bind terms from established ontologies,
  and each term's identifier and label are checked against the ontology.
- **Every claim has a source.** Each claim cites a paper and quotes it word
  for word, and a program checks that the quote is really in the paper.
- **A full history.** Every change records who made it, human or AI, and why.
- **People review.** Changes arrive as pull requests, and people accept them.

## Explore

| | |
|---|---|
| [Records](records/index.html) | Browse every ingest record |
| [The domain](DOMAIN.md) | What a record is, how records are keyed, what they contain |
| [Curation](CURATION.md) | How records are written and checked |
| [Schema](elements/index.md) | Every class, slot and enum, with diagrams |
| [Record structure](structure.md) | Everything a record can contain, in one diagram |
| [Corpus](corpus.md) | How many records there are, and in what state |
| [Workflows](WORKFLOWS.md) | The automation that checks and curates the records |

## Download

- Records: the [repository](https://github.com/monarch-initiative/ingestmech/tree/main/data/ingests).
- Schema: [ingestmech.yaml](schema/ingestmech.yaml) with its imports merged, and [JSON Schema](schema/ingestmech.schema.json).

## What the checks do not check

Validation checks that citations exist, quotes are exact, and ontology
terms are real. It does not check that the science is right. Treat
IngestMech as a curated draft reviewed by people, not as an authority.

## Contribute and cite

Issues and reviews are welcome on
[GitHub](https://github.com/monarch-initiative/ingestmech). See
[CONTRIBUTING.md](https://github.com/monarch-initiative/ingestmech/blob/main/CONTRIBUTING.md).

Records are released under CC-BY-4.0. Code is released under
BSD-3-Clause.
