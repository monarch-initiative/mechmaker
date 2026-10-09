# Curation inputs

`source_queue.tsv` ranks the sources that feed curation. One row per source.

| Column | Meaning |
|---|---|
| `rank` | Integer. 1 is next. |
| `source` | Name. |
| `url` | Landing page or API. |
| `kind` | `literature`, `database`, `knowledge_base`, `ontology`, `dataset`. |
| `license` | SPDX id or a short phrase. Unknown is written `UNKNOWN`, never guessed. |
| `status` | `CANDIDATE`, `EVALUATING`, `ADOPTED`, `REJECTED`. |
| `notes` | What it gives, what it costs, why the rank. |

A source is `ADOPTED` when code or a documented procedure that uses it is
merged, not when the row is edited. The `source-queue` skill triages the list.

## The record queue

`record_queue.tsv` lists ZIP code areas to curate, each with the incident
that puts it in the queue and the source to start from. A ZIP area is
curated when an incident touched its water (docs/DOMAIN.md, Priority), so
the queue is built by searching for incidents, not by walking ZIP codes.

| Column | Meaning |
|---|---|
| `rank` | Integer. 1 is next. |
| `zip` | The five-digit ZIP code; the record will be `datmech:<zip>`. |
| `place` | The place the Postal Service names for it. |
| `incident` | The incident that puts it in the queue. |
| `lead` | Where to start: a reference the curator fetches and reads. |
| `status` | `CANDIDATE`, `CURATED`, or `REJECTED` (no incident touched this ZIP area's water). |
| `notes` | The record's curation_priority once curated; anything to check first. |

A `CANDIDATE` ZIP is the incident's center, chosen by hand. An incident
usually touches several ZIP areas; curate the others as their own rows.
