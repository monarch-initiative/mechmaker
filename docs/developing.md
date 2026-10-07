# Developing mechmaker

## Layout

| Path | What it is |
|---|---|
| `copier.yml` | The questions, their validators, and `ontology_catalog`, the table of ontologies with verified roots |
| `template/` | The files that become a Mech. Files ending `.jinja` are rendered; everything else is copied as is. Paths may contain Jinja, such as `{{mech_slug}}` or `{% if 'review' in workflows %}` |
| `skills/` | Skills for the agent that makes a Mech. `.claude/skills` links here |
| `.claude-plugin/` | Makes the repository a Claude Code plugin and marketplace |
| `upgrade-notes.yml` | What an existing Mech must do, beyond taking files, to follow a template change. `sync-mech` shows each note to the Mechs it reaches |
| `AGENTS.md` | Where an agent pointed at this repository starts |
| `example/` | Two Mechs made with the skills, with their answers and survey briefs |
| `docs/`, `mkdocs.yml`, `scripts/gen_docs.py` | This site. Reference pages are generated |
| `tests/` | Tests that generate sample Mechs and check them |

## Commands

```bash
just install          # dev tools
just test             # render under six answer sets and check the output
just test-generated   # generate five Mechs, install them, run their `just qc`
just lint             # ruff
just sample /tmp/x    # render one sample Mech to look at
just docs-serve       # this site, locally
just docs-build       # this site, built strictly: a broken link fails
```

`docs-serve` and `docs-build` first install and build both example Mechs
(`just example-sites`), which needs the network.

`just test-generated` needs network access: each sample Mech installs its
dependencies and builds its own documentation.

## Rules

- **A fresh Mech must pass `just qc`.** Run `just test-generated` after any
  change under `template/`.
- **The examples follow the template.** After a change under `template/`,
  run `just sync-examples` and each changed example's `just qc`. `just test`
  fails while an example's template files differ from a fresh render. The
  files each example owns, its design and its links, are listed in
  `scripts/sync_examples.py` and left alone.
- **Changes that existing Mechs must act on get an upgrade note.** If a
  Mech taking the change must also do something by hand (migrate records,
  fill a newly required field, stop tracking a file, use a renamed
  command), add an entry to `upgrade-notes.yml` in the same pull request,
  with `pr:` set to its number. `sync-mech` shows it to every Mech whose
  update includes that pull request. A test checks the file's shape.
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
