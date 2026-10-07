---
name: curate-record
description: >-
  Create or improve one GoatMech goat breed record end to end:
  scaffold, research, bind terms, quote evidence, validate, record history.
  Use when asked to add, curate, fill in, expand or fix a goat breed
  record in data/goat_breeds/. Not for read-only audits (use review-record)
  or for schema changes (use extend-schema).
---

# Curate one goat breed record

A record is one goat breed. Read `docs/DOMAIN.md` first if you have
not this session. It says what counts as a record and what does not.

## 1. Find or scaffold the record

```bash
ls data/goat_breeds/ | grep -i <word>
just new-record [--id <CURIE>] --name "<name>"            # dry run
just new-record [--id <CURIE>] --name "<name>" --model <model-id> --apply
```

Find the id first, below. An id with the VBO prefix also
takes `--term-label "<its label>"`; `new-record` refuses it without one.

The id is the VBO CURIE when a term exists. Look it up;
never guess it:

```bash
just search-term ols:vbo "<name>"
just term-info ols:vbo <CURIE>
```

A record keyed by a term names it again in `record_term`, with the
ontology's label. `new-record` writes it from `--term-label`, and
`just validate` refuses an id with the VBO prefix without it. The term
check reaches `VBO:0400025` through `record_term`, so this is what
holds the id to the root:

```bash
just new-record --id <CURIE> --name "<name>" --term-label "<label from term-info>" --apply
```

A record's term is a direct child of `VBO:0400025`: not the root,
and not a term below a child. Check it before scaffolding:

```bash
just term-parents <CURIE>     # VBO:0400025 must be among them
```

A term one level too deep is a variant of a record, not a record. Find its
parent and curate that, or add the variant to the parent's record.

If no term fits, leave out `--id`: the record gets a minted
`goatmech:<uuid>`. Open a `CURATION_TODO` discussion that says a term
is missing.

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

Write the `description` last, from what the sections and sources say: two
or three sentences a newcomer can read. Every fact in it needs a quote.
Quote it at the description, where no section states the fact with
evidence already:

```bash
just add-evidence data/goat_breeds/<stem>.yaml --at description --ref PMID:<n> --snippet "..."
```

A fact you cannot quote does not go in the description.

Set `status: PROPOSED` when the record is complete and valid. Never
`REVIEWED`.

## 4. Validate

```bash
just fill-titles data/goat_breeds/<stem>.yaml --apply   # titles from the cache, for items written by hand
just validate data/goat_breeds/<stem>.yaml
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
