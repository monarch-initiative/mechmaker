---
name: convert-knowledge-base
description: >-
  Turn an existing knowledge base (a spreadsheet, database, set of YAML or
  JSON files, wiki, or a collection of repositories) into a Mech: survey it,
  map it to records, shape the schema, write a conversion script on the
  Mech's `just convert` helper, carry its facts over with checked quotes,
  and curate what it never recorded. Use when someone already has a
  knowledge base and wants it as a Mech, or asks to import, migrate or
  convert one. For a Mech started from nothing, use make-mech.
---

# Convert a knowledge base into a Mech

A conversion keeps the old knowledge base as it is. The old one becomes a
source. The new Mech holds records that quote it, and the things it never
said are curated from elsewhere or marked as gaps.

| Step | Who | Output |
|---|---|---|
| 1. Survey the knowledge base | you | the brief's first section |
| 2. Map it to a Mech | you, with `survey-domain` | the rest of the brief, `answers.yml` |
| 3. Generate and design | Copier, then you with `design-mech-schema` | the repository, `docs/DOMAIN.md`, the schema |
| 4. Write the conversion script | you | `scripts/convert_<source>.py` |
| 5. Trial | you | three to five DRAFT records, `just qc-full` green |
| 6. Curate what the source lacks | you, with the Mech's `curate-record` | PROPOSED records |
| 7. Batch | you and the person | reviewable pull requests |
| 8. Record the source | you | `curation/source_queue.tsv`, `registry/<slug>.md` |

Steps 3 and later follow `make-mech` where this skill says nothing.

## 1. Survey the knowledge base

Measure it. Do not describe it from its README.

- **Where and what format.** One file, a database, an export, many
  repositories. How to read it without a person's help.
- **Entries.** Count them. Count how many follow the main layout and how
  many do not. The ones that do not are out of scope for the first
  conversion. Say so in the brief.
- **Fields.** For each field: how many entries fill it, what its values
  look like, and whether they are identifiers, free text or numbers.
- **Identifiers.** Which field names an entry. Check a sample of the
  identifiers it uses for other things against their registry or ontology.
  Report how many fail. In the Monarch ingests, 13 of 40 infores ids were
  not in the Biolink catalog.
- **Citations.** What form they take: PMIDs, DOIs, free text, none.
- **License.** Of the knowledge base, and of what it describes, separately.

Pick a trial set of three to five entries that span it: one typical, one
with the most structure, one odd.

### License is a hard stop

Read the license of what you will copy. If it does not allow
redistribution of the text you would put in records, stop. Tell the person
what the license says, and convert nothing until they decide. A Mech is
published, and its records carry quotes.

## 2. Map it to a Mech

Run `survey-domain` with the knowledge base as the main source. Decide:

- **One record is one what.** Usually one entry. Sometimes an entry is a
  field of a larger record, or one entry is several records. Write the rule.
- **The id.** An ontology CURIE if one keys the entity, else minted in the
  Mech's namespace. The source's own identifier is kept: as the minted id
  when it is stable and unique, or in a slot the schema adds for it.
  Never as a synonym. Synonyms are names.
- **Field by field.** Each source field goes to a section, a slot, or
  nowhere, and the brief says which. A field with no
  home is a design question now, and costly later.
- **What the source never records.** This is often what the Mech is for.
  List it. It becomes curation, not conversion.

## 3. Generate and design

`make-mech` steps 2 and 3, then `design-mech-schema`, with the source's
fields as the inventory. Put `repository` or `source` and a version (a
commit, a release, an export date) on the record when the source changes
over time. Evidence will be pinned to it.

## 4. Write the conversion script

Every Mech has `src/<slug>/convert.py`. The script reads the source and
yields one `Entry` (the source key and the record) or one `Skip` (the key
and why) per entry. The helper does the rest the same way every time: DRAFT
status, a CREATE event naming the entry, validation through
`write_validated_record`, never overwriting, a report of every skip, a dry
run unless `--apply`, and one history record per applied batch.

```python
from <slug>.convert import Entry, Skip, run

def entries():
    for row in read_the_source():
        if not row["name"]:
            yield Skip(row["key"], "no name")
            continue
        yield Entry(row["key"], {"id": ..., "name": row["name"], ...})

if __name__ == "__main__":
    raise SystemExit(run(entries(), source="Old KB", script=__file__))
```

```bash
just convert scripts/convert_old_kb.py --limit 5          # dry run
just convert scripts/convert_old_kb.py --only KEY         # one entry
just convert scripts/convert_old_kb.py --model <id> --apply
```

Rules for the script:

- **Quote what you copy.** Each fact copied from the source gets an
  evidence item whose snippet is the source's own text: the line, the cell,
  the sentence. Point the reference at a fixed version:
  `url:https://raw.githubusercontent.com/<org>/<repo>/<commit>/<path>` for
  a repository, a DOI or release URL for an export. `just qc-full` then
  checks every copied fact. A local file only you have cannot be checked by
  anyone else.
- **Look up, never guess.** Map values to CURIEs with lookups (OLS, the
  source's registry). A value that does not map keeps its text as
  `preferred_term` and gets a `CURATION_TODO` discussion. An identifier the
  registry does not know is left out, with a `CURATION_TODO`.
- **Write the gaps down.** Each thing the source never records becomes a
  `CURATION_TODO` on the record, attached to the section it belongs in.
- **Skip loudly.** An entry the script cannot convert is a `Skip` with a
  reason. A network failure is a skip too, and a rerun picks it up.
- **Cache what you fetch** under `build/`, so reruns are cheap and do not
  hit rate limits.

## 5. Trial

Convert the trial set with `--apply`. Then:

```bash
just qc-full
```

It must pass. Read each record in full. Then run the Mech's `review-record`
on one. Fix the schema now, while there are five records, with
`extend-schema`, and reconvert: delete the trial records and run again.

## 6. Curate what the source lacks

Use the Mech's `curate-record`. Set the curated field, then add its quote:

```bash
just add-evidence data/.../x.yaml --at 'section[0].field' --ref REF \
  --snippet "..." --source SOURCE_KIND --apply
```

`add-evidence` fetches the source and refuses a quote it cannot find.

- A quote that crosses a link or markup in the source fails. Quote the
  parts on each side, joined with ` ... `.
- A page that refuses scripted requests is not quoted from memory. The
  field stays empty and its discussion becomes a `KNOWLEDGE_GAP` that says
  what was tried.
- A value no source states stays unset. Do not fill a field because its
  likely value is obvious.

Close each discussion the curation answered: `status: RESOLVED`, with
`resolved_date` and `resolution_note`. A record whose sections are filled
or explained is `PROPOSED`. Add a history record per record.

## 7. Batch

Convert the rest in batches of a few dozen per pull request, with
`--only` or by ranges of the source. Each batch is one `--apply` and one
history record. Say in each pull request what was skipped and why.

## 8. Record the source

- `curation/source_queue.tsv`: the knowledge base, its license, and its
  status (`converting`, then `converted`).
- `registry/<slug>.md`: the knowledge base in `data_sources` with
  `relation_type: prov:wasDerivedFrom`. Registries and ontologies used to
  check it are `prov:used`.

## Report

End with: the counts (entries, converted, skipped and why), what `just
qc-full` said, the gaps left open, and the schema decisions the person
should look at.

The IngestMech example in mechmaker's `example/` did all of this for
three Monarch ingests.
