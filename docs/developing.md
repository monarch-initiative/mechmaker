# Developing mechmaker

## Layout

| Path | What it is |
|---|---|
| `copier.yml` | The questions, their validators, and `ontology_catalog`, the table of ontologies with verified roots |
| `template/` | The files that become a Mech. Files ending `.jinja` are rendered; everything else is copied as is. Paths may contain Jinja, such as `{{mech_slug}}` or `{% if 'review' in workflows %}` |
| `skills/` | Skills for the agent that makes a Mech. `.claude/skills` links here |
| `.claude-plugin/` | Makes the repository a Claude Code plugin and marketplace |
| `docs/`, `mkdocs.yml`, `scripts/gen_docs.py` | This site. Reference pages are generated |
| `tests/` | Tests that generate sample Mechs and check them |

## Commands

```bash
just install          # dev tools
just test             # render under five answer sets and check the output
just test-generated   # generate four Mechs, install them, run their `just qc`
just lint             # ruff
just sample /tmp/x    # render one sample Mech to look at
just docs-serve       # this site, locally
```

`just test-generated` needs network access: each sample Mech installs its
dependencies and builds its own documentation.

## Rules

- **A fresh Mech must pass `just qc`.** Run `just test-generated` after any
  change under `template/`.
- **Shared files stay unchanged.** `mech_shared.yaml` and `history.yaml`
  come from [culturebotai-claw](https://github.com/CultureBotAI/culturebotai-claw)
  byte for byte. A test checks their hashes. To update them, copy the new
  versions and change the hashes in the tests.
- **Check every ontology root** before adding it to the catalog:
  `python skills/make-mech/scripts/check_terms.py label <CURIE>`.
- **Keep GitHub's `${{ }}` out of Jinja's way.** Workflow templates put it
  inside `{% raw %}` blocks, and put Mech values in a top-level `env:`.
- **Agent workflows share blocks on purpose**: the pinned action, the
  credential lines, the optional tracing, the run check. Change them in
  every file together. A test checks the pin and credentials match, and
  `actionlint` checks every workflow.
- **Agents that read text anyone can write get no write access.** They
  return structured output, and a step with no model publishes it.
- **Generated Python passes ruff** at line length 110, even with a long
  slug.

## This site

`just docs-build` generates the reference pages from the source and builds
the site in strict mode. The `docs` workflow publishes it on every push to
`main`.
