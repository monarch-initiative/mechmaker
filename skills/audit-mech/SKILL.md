---
name: audit-mech
description: >-
  Check a Mech against everything asked for it and report a checklist: each
  feature the person or the Copier answers asked for, whether it exists,
  why any missing one is missing, and what to do next. Part script (the
  answers and make-mech's steps, checked against the files), part judgment
  (the person's own asks, and whether what exists does what they meant).
  Use as the last step of make-mech or convert-knowledge-base, or alone on
  any Mech made from mechmaker, when asked to audit it, QA it, check it is
  complete, or say what is left.
---

# Audit a Mech

`just qc` says the Mech is valid. It does not say the Mech is what the
person asked for. This skill does. Its output is a checklist the person can
read in two minutes: every feature asked for, done or not, and for each one
not done, why, and what comes next.

| Step | Who | Output |
|---|---|---|
| 1. Gather the asks | you | `requests.yml` |
| 2. Run the checks | script | a draft checklist |
| 3. Judge what the script cannot | you | each `[?]` resolved |
| 4. Explain what is missing | you | a reason for each `[ ]` |
| 5. Report | you | the checklist, the gaps, next steps |

The script is in the `scripts/` folder beside this file. Below, `<scripts>`
stands for that folder's path: `.agents/skills/audit-mech/scripts` after
`npx skills add`, a folder under `~/.claude/plugins/` for the Claude Code
plugin, `skills/audit-mech/scripts` in a mechmaker checkout. It needs
PyYAML, which `uv run` installs for it. Run it where it is; do not copy it
into the Mech.

## 1. Gather the asks

The person's asks come from three places. Collect all three.

- **The Copier answers** in the Mech's `.copier-answers.yml`. The script
  reads these itself.
- **make-mech's own steps**: a designed schema, seed records, a registry
  entry. The script checks these too.
- **What the person said.** Their first request, the domain brief, and
  anything they asked for on the way: a section, an import, a page, a
  front-page column, a source. Only you know these. Write them to
  `requests.yml` beside `answers.yml`, outside the Mech, one item each:

```yaml
- feature: Country of origin on each record
  said: "I want to see where each breed comes from"
  check: {slot: countries}
- feature: An import from DAD-IS
  check: {recipe: import-dad-is}
- feature: Records read like a breed society's description
```

`check` takes `class`, `slot` (in the schema), `recipe` (in the justfile),
`path` (a file exists), `contains: {path, text}`, or `records` (at least
this many). Give one where the ask has a plain sign in the files. Leave it
out where it needs judgment; the script lists that item for you to check.
Quote the person in `said` when you have their words. Do not add asks they
did not make. An ask you think they should have made is a next step, not
a request.

If make-mech kept `requests.yml` from step 1, start from it and add what
came later.

## 2. Run the checks

```bash
uv run <scripts>/audit_mech.py <mech> --requests requests.yml --qc
```

`--qc` runs `just qc`. Use `--qc-full` instead when the network is up and
the person can wait: it checks every term and quote. `--json` gives the
same items for a program.

Each item is `[x]` done, `[ ]` missing, or `[?]` to check. The script
exits 1 when anything is missing. That is a finding, not a failure of the
audit. It exits 2 when the folder is not a Mech, and 64 when it cannot read
`requests.yml`: not a list, an item that is not a mapping, or a `check`
that is not shaped as above. The message names the item. Fix the file and
run it again.

What it checks from the answers: the package and schema, the record class
as tree root, the records folder, the identity prefix, root, direct rule
and adapter, each ontology's enum, root, binding slot and adapter (a
section the design renamed still counts, if a slot binds the enum), local
ontology files, causal graphs, taxon scope, domains and collection in the
registry entry, both licenses, each workflow's files and prompt, agent
schedules, Langfuse, deep research, the record browser, the site colors,
the Claude Code hook, export formats, tabular layout, KGX on Biolink, and
load targets. From make-mech's steps: a first commit, `docs/DOMAIN.md`
with no TODO left, a schema changed from the scaffold, three or more seed
records, their status, and the registry draft's record count.

A file "changed since the template" was compared with the Mech's first
commit, which make-mech says must be the untouched Copier output. A Mech
without its own git history gets `[?]` on those items.

## 3. Judge what the script cannot

Resolve every `[?]` to done or missing. Read the thing itself.

- A prompt or research template that changed may still be wrong for the
  domain. Read it. A prompt that did not change may already fit; say so.
- A site color that differs from the answer was changed after generation.
  Ask whether that was the person's choice, or find the commit that did it.
- A request with no `check`: find the evidence. Name the file, the slot or
  the record that shows it, or say it is absent.
- A `[x]` can be hollow. A slot that exists but that no seed record fills
  is present in the schema and absent from the data. Spot-check two `[x]`
  items that matter most to the person against the records.

## 4. Explain what is missing

For each `[ ]`, find the real reason. The script's guess is a starting
point. Look in this order:

1. `docs/DOMAIN.md`. The design step records what it cut and why, often in
   "Out of scope".
2. `git log -- <path>` on the file, and the commit messages.
3. This conversation, if the Mech was made in it.

Sort each into one of these, and say which:

- **Decided against.** Someone chose to drop it, for a reason you can
  quote. State the reason. If DOMAIN.md does not record it, it should.
- **Not reached.** A step was not done: seeds not curated, the registry
  not updated, a workflow left for later.
- **Blocked.** Something outside the Mech stopped it: a service down, a
  key or GitHub App the person has not created, a source behind a paywall.
- **Broken.** It was meant to exist and does not, with no reason found.
  This one matters most. Say so plainly.

Do not invent a reason. "No reason found" is an answer.

## 5. Report

Give the person, in this order:

1. One line: the Mech, how many features asked for, how many done.
2. **The checklist.** Every item, `[x]` or `[ ]`, after step 3 left no
   `[?]`. Keep the script's evidence; add yours where you judged.
3. **Not implemented.** Each missing feature, its kind from step 4, the
   reason, and the evidence for the reason.
4. **Next steps.** Three to five, most important first. Prefer the ones
   that unblock others and the ones that are cheap now and expensive later
   (a schema change while there are five records, not five hundred). Give
   the command or skill for each: `design-mech-schema`, the Mech's
   `extend-schema` or `curate-record`, `register-mech`, `uvx copier update`.

Do not fix anything during the audit. The audit reports. Fixing is the
next step, and the person chooses it.
