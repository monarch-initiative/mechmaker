# CLAUDE.md

This repository is mechmaker: a Copier template (`copier.yml`, `template/`)
and agent skills (`skills/`) for making Mechs. See README.md.

## Layout

- `copier.yml`: questions, validators, and `ontology_catalog`, the table of
  ontologies with their verified roots.
- `template/`: the Copier subdirectory. `.jinja` files render; the rest
  copy verbatim. Paths may contain Jinja (`{{mech_slug}}`, `{% if ... %}`).
- `skills/`: skills for the agent that makes a Mech. `.claude/skills` is a
  symlink to it. `.claude-plugin/` makes the repository a Claude Code plugin.
- `tests/`: `just test` renders four answer sets; `just test-generated`
  installs three generated Mechs and runs their `just qc`.

## Rules

- A fresh copy must pass `just qc`. Run `just test-generated` after any
  change under `template/`.
- `template/src/{{mech_slug}}/schema/mech_shared.yaml` and `history.yaml` are
  vendored byte-identical from culturebotai-claw
  (`src/kg_microbe_governance/artifacts/schema/`, copied at claw commit
  306e975a, 2026-09-30). Never edit them here. To
  update, copy the new canon and change the md5s in `tests/test_template.py`
  and `template/tests/test_schema.py.jinja`.
- Every root added to `ontology_catalog` is checked first:
  `python skills/make-mech/scripts/check_terms.py label <CURIE>`.
- Files that contain their own `{{ }}` (the justfile, HTML templates) either
  lack the `.jinja` suffix or wrap that syntax in `{% raw %}`.
- Generated Python must pass ruff at line length 110 with a long slug.
