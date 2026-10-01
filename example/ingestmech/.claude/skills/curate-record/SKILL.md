---
name: curate-record
description: >-
  Create or improve one IngestMech ingest record end to end:
  scaffold, research, bind terms, quote evidence, validate, record history.
  Use when asked to add, curate, fill in, expand or fix an ingest
  record in data/ingests/. Not for read-only audits (use review-record)
  or for schema changes (use extend-schema).
---

# Curate one ingest record

A record is one ingest. Read `docs/DOMAIN.md` first if you have
not this session. It says what counts as a record and what does not.

## 1. Find or scaffold the record

```bash
ls data/ingests/ | grep -i <word>
just new-record --id <CURIE> --name "<name>"            # dry run
just new-record --id <CURIE> --name "<name>" --model <model-id> --apply
```

The id is minted: `ingestmech:<slug>`, where the slug comes from the
name.

Check for duplicates by id and by synonym before creating anything.

## 2. Research

Gather sources before writing. For each source you intend to cite:

```bash
just fetch-reference PMID:<n>
```

Read what came back. If only the abstract is cached, you may quote only the
abstract. A claim you cannot tie to fetched text is not written. It becomes a
`KNOWLEDGE_GAP` discussion.

## 3. Write

Work section by section. For every descriptor:

- `preferred_term`: your words, as specific as the evidence allows.
- `term`: the ontology binding, found with the `ontology-terms` skill. Leave
  it out rather than guess.
- `evidence`: one or more items, added with `just add-evidence` (see the
  `evidence-references` skill). It fetches the source, checks the quote,
  fills the title and logs the change, so no one hand-writes evidence YAML.

Set `status: PROPOSED` when the record is complete and valid. Never
`REVIEWED`.

## 4. Validate

```bash
just fill-titles data/ingests/<stem>.yaml --apply   # titles from the cache, for items written by hand
just validate data/ingests/<stem>.yaml
```

`fill-titles` lists any reference that is not cached yet. Fetch it with
`just fetch-reference` and run it again.

Fix every error. Do not change a correct term to silence a lookup outage.
Do not weaken a quote to make it pass. Find the real text.

## 5. Record

Append one event to the record's `curation_history`:

```yaml
  - timestamp: "<ISO-8601 UTC>"
    curator: <harness or login>
    llm_assisted: true
    model: <model-id>
    action: EDIT
    description: <what changed, one or two sentences>
```

Then one history record for the session:

```bash
just new-history --kind record --slug <stem> --event EDIT --outcome changed \
  --summary "..." --details "..." --actor <harness> --agent-tool <harness> \
  --model <model-id> --apply
```

## 6. Hand off

Run `just qc`. Open a pull request with the record, the history record, and
any new files under `cache/` and `references_cache/`. List in the pull
request what you could not source.
