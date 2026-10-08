---
name: register-mech
description: >-
  Add a Mech to MechRegistry (monarch-initiative/mechregistry): update the
  draft entry that mechmaker generated in registry/<slug>.md, validate it
  with the registry's own tooling, and, if the person chooses, ask the
  registry to list it: by an issue for its maintainers or by a pull
  request. Use when a new Mech is ready to be listed, or when a listed
  Mech's entry needs updating.
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
- `collection`: the registry's `CollectionEnum` value for the Copier
  `collection` answer. `monarch` is `monarch`. `xmech` is `x-mech-suite`.
  `none` has no field. The generated draft writes it; check it is there.
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

## 3. Ask whether to list it, and how

A new Mech may not be ready to be seen. Listing it is the person's choice,
and anything opened on MechRegistry is public. Ask them, and show them the
entry. Three answers:

- **Not yet.** Stop here. The draft stays in `registry/<slug>.md`, up to
  date, for when they are ready. Say so in the report.
- **An issue.** The registry's maintainers add the entry. The issue
  follows the registry's "Suggest a new Mech" form and carries the whole
  draft. Use it when the person would rather not open a pull request, or
  could not run step 2: then say in the issue that the draft is not yet
  validated.
- **A pull request.** The person adds the entry themselves, validated in
  step 2.

The issue needs `gh`, signed in. One script comes with this skill, in the
`scripts/` folder beside this file; `<scripts>` stands for that folder's
path. Write the body, show it to the person, then open the issue:

```bash
uv run <scripts>/registry_issue.py <mech-repo> > registry-issue.md
gh issue create --repo monarch-initiative/mechregistry \
  --title "$(uv run <scripts>/registry_issue.py <mech-repo> --title)" \
  --body-file registry-issue.md
```

Do not pass `--label new-mech`. The form names that label, but the
registry does not have it, and `gh` refuses a label that does not exist.
Without `gh`, give the person the body and the link
<https://github.com/monarch-initiative/mechregistry/issues/new?template=new-mech.yml>.

For the pull request, branch the clone from step 2, commit
`mech/<slug>/<slug>.md`, and open it against `main`.

Either way, give the person the link, and keep the Mech's own
`registry/<slug>.md` in step with what was submitted.
