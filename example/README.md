# Examples

Two Mechs made with mechmaker's skills and template, to show the whole path
from a request to curated records. Each one's git history shows every step
as its own commit, starting with the untouched template output.

## GoatMech: a Mech from nothing

A Mech for goat breeds. Walkthrough:
https://monarch-initiative.github.io/mechmaker/walkthrough/

Site and record browser: https://monarch-initiative.github.io/mechmaker/example/goatmech/

| Path | What it is |
|---|---|
| `survey-brief.md` | The domain survey, from the `survey-domain` skill |
| `answers.yml` | The Copier answers the Mech was first generated from; its current answers are in `goatmech/.copier-answers.yml` |
| `goatmech/` | The Mech: template output, then the design, then three curated records |

## IngestMech: a Mech converted from a knowledge base

A Mech for the Monarch Initiative's data ingests, converted from the
ingest repositories with the `convert-knowledge-base` skill. Walkthrough:
https://monarch-initiative.github.io/mechmaker/walkthrough-conversion/

Site and record browser: https://monarch-initiative.github.io/mechmaker/example/ingestmech/

| Path | What it is |
|---|---|
| `ingest-survey-brief.md` | The survey of the existing knowledge base and the domain |
| `ingest-answers.yml` | The Copier answers the Mech was first generated from; its current answers are in `ingestmech/.copier-answers.yml` |
| `ingestmech/` | The Mech: template output, the design, the conversion script, three converted and curated records |

Both are examples. Neither is a published knowledge base, and their records
are not surveys of goat breeds or of Monarch's ingests.

## Keeping them in step with the template

The examples show what a Mech made today looks like, so they follow the
template. Every file the template writes is in each example byte for byte,
except the files the Mech owns: its schema, `docs/DOMAIN.md`, its links into
this repository, and a few settings. `scripts/sync_examples.py` lists them,
with the reason for each.

After a template change:

```bash
just sync-examples                 # render each example's answers, copy the template's files in
cd example/goatmech && just qc     # and the same in example/ingestmech
```

`just test` fails while an example has drifted. A change the template makes
to a file an example owns is not copied; the sync lists those files, to merge
by hand when the change applies. `_commit` in each `.copier-answers.yml` is
the template commit at the last sync.
