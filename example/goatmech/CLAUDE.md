# CLAUDE.md

Operational guidance for Claude Code and other agents in this repository.
`AGENTS.md` points here.

## What this is

GoatMech (Goat Breed Knowledge Base) is a Mech: an AI agent-curated,
ontology-grounded, evidence-backed knowledge base. GoatMech records goat breeds: where each comes from, what it is kept for, and the features that tell it apart, with every claim quoted from its source.

One record is one goat breed. One record is one YAML file under
`data/goat_breeds/`, validated against the `GoatBreed` class in
`src/goatmech/schema/goatmech.yaml`.

The pattern comes from [DisMech](https://github.com/monarch-initiative/dismech).
The registry of Mechs is [MechRegistry](https://github.com/monarch-initiative/mechregistry).

Read before changing domain content:

- `docs/DOMAIN.md`: what a record is, what it is not, identity, granularity.
- `docs/CURATION.md`: evidence rules, the curation loop, review.
- `curation/source_queue.tsv`: the sources that feed curation, ranked.

## Commands

```bash
just                   # list every recipe
just install           # uv sync
just qc                # the offline gate CI blocks on
just qc-full           # qc plus terms and quotes for every record (network)
just validate FILE     # closed schema, ontology terms, verbatim quotes
just new-record ...    # scaffold a record (dry-run unless --apply)
just import-schema SRC --record-class C   # start the schema from an existing one (dry-run unless --apply)
just new-history ...   # scaffold a history record (dry-run unless --apply)
just add-evidence FILE --at PLACE --ref REF --snippet "..."   # checked evidence (dry-run unless --apply)
just fetch-reference PMID:NNN   # fetch and cache a source; read it before quoting it
just fill-titles [FILE...]      # fill missing reference_title from the cache (dry-run unless --apply)
just search-term ADAPTER "text" # search an ontology, e.g. ols:go
just term-ancestors CURIE       # where a term sits; use when an enum root rejects it
just term-parents CURIE         # direct is-a parents; a record id's must include VBO:0400025
just check-identity [FILE...]   # record ids follow the identity enum's rule (network, in qc-full)
just report            # corpus statistics
just compliance        # completeness per record, lowest first
just export            # every format in conf/export.yaml, into build/export/, each read back
just load TARGET       # fill a database in conf/load.yaml (MongoDB, Neo4j); --replace to overwrite
just labels            # create the GitHub labels the workflows use
just docs-serve        # the documentation site at http://127.0.0.1:8000
just site-check        # check conf/site.yaml: colors, theme, contrast
just research-providers         # which deep-research providers are ready here
just research PROVIDER TARGET   # a deep-research report on one record (costs a run)
```

Quote counts from `just report` or a live command, never from prose.

## Rules that matter most

- **Never guess a CURIE.** Look it up with `just search-term` and
  `just term-info`. An unverified ontology term, PMID or accession is worse
  than none. Leave `term` unset, keep `preferred_term`, and open a
  `CURATION_TODO` discussion.
- **A label is the ontology's label.** `term.label` must match the ontology
  exactly. Put nuance in `preferred_term`, never in `label`.
- **A snippet is a verbatim quote.** Fetch the source with
  `just fetch-reference`, copy the text, and add it with `just add-evidence`,
  which checks the quote before writing. Paraphrase goes in `explanation`.
  `just validate-references` fails a paraphrase, and it should.
- **Bind the most specific accurate term.** If only a broad term fits, bind
  it and say so in `notes`. Do not bind a narrow term because it exists.
- **A deep-research report is a lead, never a source.** Never cite one in a
  record. Fetch the primary source it points to and quote that.
- **Declare every prefix.** Each CURIE prefix a record uses has its full
  URI in the schema's `prefixes`. The RDF exports depend on it, and
  `just export` fails on a prefix with no URI.
- **Closed schema.** An unknown field is an error. If the schema lacks a
  place for something real, use the `extend-schema` skill. Do not stuff it
  into `notes`.
- **An agent-drafted record is `PROPOSED`, never `REVIEWED`.** Promotion to
  `REVIEWED` is a human decision, recorded as a human `REVIEW` event.
- **Record what you did.** Every change appends a `curation_history` event
  to the record, and every session adds a history record with
  `just new-history ... --apply`. Fill `--details`.

## Files not to edit here

- `src/goatmech/schema/mech_shared.yaml` and
  `src/goatmech/schema/history.yaml` are vendored byte-identical from
  the Mech fleet canon. A test checks their hashes. Change them upstream.
- `pages/` is generated. Edit `src/goatmech/templates/`, run
  `just render`, commit the result.
- `docs/elements/`, `docs/schema/`, `docs/records/`, `docs/structure.md`,
  `docs/corpus.md` and `.mkdocs.site.yml` are generated by `just docs-build`
  and not committed. Colors and layout settings live in `conf/site.yaml`. Improve a schema
  page by improving the schema's descriptions.
- `cache/` and `references_cache/` are written by the validators. Commit
  them. Never hand-edit a row.
- `.copier-answers.yml` is written by Copier. Run `just update-template` to
  pull template changes from mechmaker.

## Skills

Project skills live in `.claude/skills/`. Use them.

| Skill | Use it to |
|---|---|
| `curate-record` | create or improve one record end to end |
| `ontology-terms` | choose, bind, check or repair a term |
| `evidence-references` | find a source, quote it, validate the quote |
| `review-record` | audit one record without editing it |
| `extend-schema` | change the data model and migrate records |
| `source-queue` | triage the sources that feed curation |
| `github-workflows` | turn on, configure, adapt or debug the GitHub workflows |
| `site-design` | change how the documentation site and record browser look |
| `deep-research` | run deep research on a record, and turn its leads into evidence |


## Workflows

`docs/WORKFLOWS.md` lists every GitHub workflow, on or off. Agent workflows
read their prompts from `.github/prompts/` and their models from
`.github/agent-config.yaml`. When you run inside one, the prompt is your
task; this file and the skills still apply. Turn workflows on or off through Copier, never by copying
files; see the `github-workflows` skill.

## Git

Branch before the first edit. One pull request per coherent change. The pull
request is the human review gate. Do not merge without approval.
