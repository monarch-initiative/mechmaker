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
