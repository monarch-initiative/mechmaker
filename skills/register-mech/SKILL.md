---
name: register-mech
description: >-
  Add a Mech to MechRegistry (monarch-initiative/mechregistry): update the
  draft entry that mechmaker generated in registry/<slug>.md, validate it
  with the registry's own tooling, and prepare the pull request. Use when a
  new Mech is ready to be listed, or when a listed Mech's entry needs
  updating.
---

# Register a Mech

MechRegistry keeps one entry per Mech at `mech/<id>/<id>.md`: markdown with
a YAML header that validates, closed, against the registry's LinkML schema.
mechmaker wrote a draft at `registry/<slug>.md` in the Mech's repository.

## 1. Bring the draft up to date

In the Mech repository:

- `record_count` and `record_count_date` from `just report`, today's date.
  Records, not files.
- `maturity`: `seeded` until records are merged, `curating` after.
- `ontologies`: every prefix records actually bind. Check against
  `conf/oak_config.yaml`.
- `data_sources`: every source in `curation/source_queue.tsv` with status
  `ADOPTED`.
- `features`: only what exists. `static_browser` only if the site is
  published. `causal_mechanism_graphs` only if records carry graphs.
- `homepage_url`: the published site if there is one, else the repository.
- `cross_references`: the neighbors named in the domain survey, with
  relations from the registry's `MechRelationEnum`: `follows_pattern_of`,
  `consumes`, `provides_to`, `hands_off_to`, `shares_vocabulary_with`,
  `adopts_practice_of`, `sibling_of`. Targets must be ids already in the
  registry.
- The body below the header: a short plain paragraph on the Mech's state.
  Dated facts, no promises.

## 2. Validate with the registry's tools

```bash
git clone https://github.com/monarch-initiative/mechregistry
cd mechregistry
mkdir -p mech/<slug>
cp <mech-repo>/registry/<slug>.md mech/<slug>/<slug>.md
uv sync --dev
uv run mechregistry validate mech/<slug>/<slug>.md
make check-prefixes
```

Validation is closed. An unknown field or enum value fails. Product ids
must start with `<slug>.`. `collection` accepts only values in the
registry's `CollectionEnum`; drop the field if the Mech is in none.

## 3. Open the pull request

Opening a pull request on a shared repository is visible to others. Ask the
user first. Show them the entry. Then branch, commit, and open it against
`main`, or use the registry's new-Mech issue template if the user prefers.

Keep the Mech's own `registry/<slug>.md` in step with what was submitted.
