# mechmaker

A [Copier](https://copier.readthedocs.io/) template and a set of agent skills
for making Mechs.

A Mech is an AI agent-curated, ontology-grounded, evidence-backed knowledge
base. It keeps one validated YAML record per entity, a LinkML schema, cited
evidence with verbatim quotes checked against the source, and an
append-only curation history. The pattern comes from
[DisMech](https://github.com/monarch-initiative/dismech). The Mechs are listed
in [MechRegistry](https://github.com/monarch-initiative/mechregistry).

mechmaker splits making a Mech in two.

- **The template** lays down everything that does not depend on the domain.
  It does it the same way every time.
- **The skills** guide an agent through what does depend on the domain: what
  a record is, how it is keyed, which ontologies ground it, which sources feed
  it, and what shape the schema takes.

## Quick start

With an agent (Claude Code):

```
/plugin marketplace add monarch-initiative/mechmaker
/plugin install mechmaker@mechmaker
```

Then ask for a Mech: *"Make a Mech for bacterial biofilm matrix components."*
The `make-mech` skill takes it from there.

By hand:

```bash
uvx copier copy gh:monarch-initiative/mechmaker my-new-mech
cd my-new-mech
git init -b main
just install
just qc
```

Copier asks the questions. To answer from a file, pass
`--data-file answers.yml --defaults`. See `tests/answers/habitat.yml` for a
small example.

## What the template makes

| Path | What it is |
|---|---|
| `src/<slug>/schema/<slug>.yaml` | A starting LinkML schema: the record class, a descriptor class and dynamic enum per chosen ontology, evidence, causal graph, curation events |
| `src/<slug>/schema/mech_shared.yaml` | Discussion and Dataset classes, byte-identical to the Mech fleet canon |
| `src/<slug>/schema/history.yaml` | The curation history schema, byte-identical to the fleet canon |
| `src/<slug>/` | Closed-schema validation, record and history scaffolding, corpus report, OLS helpers, the QC gate, the site renderer |
| `justfile` | The repository's interface. `just qc` is the one definition of green |
| `conf/oak_config.yaml` | Which ontology service checks which prefix, for linkml-term-validator |
| `.linkml-reference-validator.yaml` | Settings for the verbatim-quote check |
| `data/<records>/`, `history/` | Records, and their append-only history |
| `docs/DOMAIN.md`, `docs/CURATION.md` | The domain model to fill in, and the curation rules |
| `curation/source_queue.tsv` | The ranked list of sources |
| `registry/<slug>.md` | A draft MechRegistry entry |
| `.claude/skills/` | Six curation skills: `curate-record`, `ontology-terms`, `evidence-references`, `review-record`, `extend-schema`, `source-queue` |
| `.claude/hooks/` | A pre-edit hook that blocks an edit leaving a record invalid |
| `.github/workflows/qc.yaml` | CI: `just qc`, then terms and quotes |

A fresh copy passes `just qc`. Three checks guard every record:

1. **Schema.** Closed LinkML validation. An unknown field is an error.
2. **Terms.** [linkml-term-validator](https://github.com/linkml/linkml-term-validator)
   checks that each bound CURIE exists, sits under its enum's root, and carries
   the ontology's own label.
3. **Quotes.** [linkml-reference-validator](https://github.com/linkml/linkml-reference-validator)
   fetches each cited source and checks the snippet appears in it verbatim.

## The questions

| Question | What it decides |
|---|---|
| `mech_name`, `mech_slug` | Names, package, CURIE prefix, registry id |
| `record_class`, `record_noun`, `records_dir` | What one record is called and where it lives |
| `identity_prefix`, `identity_root` | Which ontology keys records, and the root every key must descend from. The root is required when a prefix is given; without one no identity term is checked |
| `ontologies` | Which ontologies records bind. Each adds a descriptor class, a dynamic enum with a verified root, and a record section |
| `causal_graphs` | Mechanism nodes and causal edges, as in DisMech's pathographs |
| `domains`, `taxon_scope`, `collection` | MechRegistry metadata |
| `data_license`, `code_license` | CC BY 4.0 or CC0 for data. BSD-3-Clause, MIT or Apache-2.0 for code |
| `include_site`, `include_claude_hook` | The static browser and the pre-edit hook |

The ontology roots in `copier.yml` were each checked against OLS.

## The skills

In `skills/`, for the agent making the Mech:

| Skill | Does |
|---|---|
| `make-mech` | The whole path: survey, answers, generate, design, seed, register |
| `survey-domain` | Defines the record, its identity, its grounding, its sources and its neighbors |
| `design-mech-schema` | Turns the scaffold schema into a domain model, with the DisMech patterns |
| `register-mech` | Brings the registry entry up to date and validates it with the registry's tools |

`skills/make-mech/scripts/check_terms.py` checks CURIEs, labels and roots
against OLS with the standard library alone, before a Mech exists.

The generated Mech carries its own skills for everyday curation.

## Updating a Mech from the template

```bash
just update-template      # in the Mech; runs `copier update`
```

## Developing mechmaker

```bash
just install
just test              # render under four answer sets and check the output
just test-generated    # generate three Mechs, install them, run their `just qc`
just sample /tmp/x     # render a sample to look at
```

`template/` is the Copier subdirectory. Files ending `.jinja` are rendered.
Everything else is copied as is. The two vendored schemas must stay
byte-identical to the fleet canon; a test checks their hashes.

## License

Code: BSD-3-Clause. See [LICENSE](LICENSE).
