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

## News leads

`news/<record>.md` holds the news leads for one record: articles about its
incidents, and about incidents it does not have yet, found by searching
dated windows. Each file says when and how it was made. Leads are not
evidence and are never cited; a curator reads the archived copy of an
article and quotes that.

To refresh one record's leads:

```bash
just news-plan 48502_flint_michigan     # the searches, read from conf/news.yaml
just news-leads 48502_flint_michigan    # writes curation/news/48502_flint_michigan.md
```

`conf/news.yaml` builds the searches from the record: its place and state,
its incidents with their dates, kinds, advisories and contaminants, and the
Wikipedia articles it cites. Each search keeps its 15 most promising leads
and counts the rest. The `news-leads` skill has the details. The
`news-watch` workflow looks for new stories every Wednesday and files them
as one `news` issue.
