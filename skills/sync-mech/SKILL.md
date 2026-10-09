---
name: sync-mech
description: >-
  Bring an existing Mech up to date with a newer mechmaker: find what changed
  in the template since the Mech was made or last synced, show the person
  each change (by mechmaker pull request) and how it meets the Mech's own
  edits, take the ones they choose, merge them into the Mech's schema,
  records, site and workflows, and act on the upgrade notes. Use when asked
  to update, sync, upgrade or refresh a Mech made from mechmaker, to check
  whether a Mech is behind the template, or to pull in a new mechmaker
  feature. Not for changing a Mech's own answers alone (that is
  `copier update --vcs-ref=:current: --data`), nor for a knowledge base not
  made with mechmaker.
---

# Sync a Mech with mechmaker

A Mech made from mechmaker keeps two kinds of files. Some the template wrote
and the Mech never touched: those can simply take the new version. Others the
Mech made its own: the designed schema, `docs/DOMAIN.md`, the site settings,
adapted prompts, and every record. A newer template has to be merged into
those, and some of its changes are design decisions the Mech's records must
follow. Copier can carry the files. Deciding what to take, merging it into
what the Mech owns, and migrating the records is judgment: yours, and the
person's.

| Step | Who | Output |
|---|---|---|
| 0. Prepare | you | a clean branch, a readable template source |
| 1. Check | script | how far behind the Mech is |
| 2. Plan | script | every update, every file, every new question |
| 3. Choose | you and the person | the updates to take, the answers to give |
| 4. Apply | script, with Copier | the chosen changes in the working tree |
| 5. Merge | you | conflicts resolved, owned files merged |
| 6. Upgrade notes | you | records and settings brought in line |
| 7. Verify | script | `just qc` passes |
| 8. Record | you | a commit, a history record, a pull request |

The script is in the `scripts/` folder beside this file. Below, `<scripts>`
stands for that folder's path: `.agents/skills/sync-mech/scripts` after
`npx skills add`, a folder under `~/.claude/plugins/` for the Claude Code
plugin, `skills/sync-mech/scripts` in a mechmaker checkout. It needs PyYAML,
which `uv run` installs for it, plus git and Copier. Run it where it is; do
not copy it into the Mech.

## 0. Prepare

- The Mech must have `.copier-answers.yml` with `_src_path` and `_commit`.
  Without them it was not made with Copier, and this skill does not apply.
- `_src_path` must be `gh:monarch-initiative/mechmaker`, a URL, or an
  absolute path to a mechmaker checkout. A relative path cannot be
  followed: change it in its own commit first.
- The Mech's git tree must be clean. Make a branch:
  `git switch -c sync-mechmaker`.
- **A Fleet member** (its answers set `fleet_name`) takes its shared schema
  modules and `fleet/pin.yaml` from its Coordinator, not from mechmaker: an
  update leaves them alone, and a plan that shows them changed is
  mechmaker's newer canon, which reaches the member through the
  Coordinator's `change-canon`. Its fleet answers (`fleet_links` and the
  identity answers) follow the Coordinator's `fleet.yaml`; do not change
  them here.
- **A Coordinator** (its answers set `kind: coordinator`) syncs the same
  way, from its own folder. The script follows `coordinator/` for it, and
  shows it only the upgrade notes marked `kind: coordinator`. A change to
  the canon then needs a release to every member: the Coordinator's
  `change-canon` skill.

## 1. Check

```bash
uv run <scripts>/sync_mech.py check <mech>
```

This lists the mechmaker pull requests that changed the template since the
Mech's `_commit`, without rendering anything. Exit 0: up to date, stop
here. Exit 1: there is something to plan. Some of what it lists may not
reach this Mech (a change to a workflow it does not use); the plan knows.

The target is the latest mechmaker release. Use `--to HEAD` for
mechmaker's main branch, when the person wants a change not yet released,
or `--to <tag>` for a particular release. A Mech made from main is already
past the latest release: `check` exits 2 and says it is newer than the tag.
That Mech is fine; run again with `--to HEAD`.

## 2. Plan

```bash
uv run <scripts>/sync_mech.py plan <mech> [--to HEAD]
```

It renders the Mech's own answers at its `_commit`, at each pull request
since, and at the target, all at once: a Mech two dozen pull requests
behind takes about twenty seconds. Each pull request that changes this
Mech's files is one **update**, named by its number (`#65`). Under each,
every file it changes is marked:

| Mark | Means | Usually |
|---|---|---|
| `take` | the Mech never changed the file | safe to take as it is |
| `add` | a new file | safe |
| `remove` | the template dropped the file; the Mech never changed it | safe |
| `merge` | the Mech changed the file too | Copier merges; you check the result |
| `clash` | a new file where the Mech has its own | you decide which wins |
| `edited` | the template dropped a file the Mech changed | keep or delete, with the person |
| `deleted` | the Mech deleted a file the template changed | usually stays deleted |

Each file also has an **area**: data model, shared schema, site and
browser, workflows, agent guidance, documentation, tools, tests,
dependencies. `(also #N)` means another update changes the same file.

An answer given with `--data` (a new question's answer, or a changed one)
shows as one more update, `answers`, holding what that answer changes.
`apply` always takes it: to undo it, leave the `--data` out.

The plan also lists **new questions**, with the defaults they would take,
and the **upgrade notes** that apply: changes the Mech must act on beyond
taking files, from mechmaker's `upgrade-notes.yml`.

`--json` prints the same plan as data.

## 3. Choose

The person chooses. You prepare the choice so they can make it in a few
minutes.

1. **Learn what each update does.** The title is the pull request's title.
   For more, read it: `gh pr view <N> --repo monarch-initiative/mechmaker`,
   or its diff in the template. Say in one plain sentence what it gives
   *this* Mech.
2. **Recommend.** Recommend taking an update unless there is a reason not
   to, and give the reason when there is one:
   - It conflicts with a deliberate choice the Mech made. Look at its
     `merge` files: did the Mech change that place on purpose? Its
     `docs/DOMAIN.md` and git history say why.
   - It adds something the person said they do not want.
   - It is a large change to an area the person has customized heavily (the
     record browser's templates, say), and they would rather keep theirs.
   Changes to the agent workflows' permissions or to what an agent may read
   (the comment guard, the trust checks) protect the repository. Recommend
   those strongly.
3. **Mind the order.** Later updates build on earlier ones. Declining an
   early update that a later, accepted one also changes leaves files that
   need hand work (the apply step lists them). Declining a recent,
   self-contained update is clean. To keep one part of the Mech exactly as
   it is, whatever changes it, `--keep` a path instead (step 4).
4. **New questions.** For each, say what it controls and whether the default
   fits this Mech. The help text is in mechmaker's `copier.yml`. Ask the
   person where the default may not fit.
5. **Show the upgrade notes.** They say what work comes with an update.
6. Ask. Present the updates grouped by area or by theme, with your
   recommendation, the new questions, and the notes. Wait for the answer.

A declined update is declined for good. `_commit` moves to the target
either way, so the next sync does not offer it again. To take it later,
copy its change by hand from the template.

## 4. Apply

```bash
uv run <scripts>/sync_mech.py apply <mech> [--to HEAD] --all
uv run <scripts>/sync_mech.py apply <mech> --accept '#63' '#65'
uv run <scripts>/sync_mech.py apply <mech> --decline '#64' --keep 'src/*/templates/*'
uv run <scripts>/sync_mech.py apply <mech> --all --data tabular_layout=flat
```

Use the same `--to` as the plan. `apply` runs `copier update` to the target
with the Mech's answers (and any `--data`), then puts back each file only
declined updates changed, and each file matching `--keep`. It refuses a
dirty Mech, and a template checkout with uncommitted changes (Copier would
record a commit that does not exist).

It reports:

- **conflict markers to resolve**: Copier could not merge a hunk and wrote
  `<<<<<<< before updating` ... `>>>>>>> after updating` into the file;
- **touched by accepted and declined updates**: keep only the accepted part;
- **changed outside the plan**: look at each one;
- the new answers, and the upgrade notes of the accepted updates.

It exits 1 when any of the first two is left. Nothing is committed: the
whole update is `git diff` until you commit it, and `git checkout .` with
`git clean -fd` undoes it.

## 5. Merge

Read the whole diff before you call anything done. A merge without markers
is not proof that it is right.

- **Conflict markers.** Resolve each one. Keep the Mech's intent and the
  template's change both where you can; ask the person where they conflict.
- **Partly declined files.** See what each update did to the file in the
  template's history (`git log -p` on the template file in a mechmaker
  checkout), and remove the declined part.
- **The data model** (`src/<slug>/schema/<slug>.yaml`). The template changed
  its starting schema; the Mech's schema is a design built from it. A text
  merge of the two is unreliable even when it applies cleanly. If the
  update did more than add a line, put the file back
  (`git checkout HEAD -- <path>`), work out what the template's change
  means for this design, and make that change with the Mech's
  `extend-schema` skill, which migrates the records. When a change does not
  fit the design, tell the person, and leave it out.
- **The shared schema** (`mech_shared.yaml`, `history.yaml`). These are
  vendored and should always be `take`. If one is `merge`, the Mech edited
  a file it must not: take the new one, and move the Mech's change into its
  own schema.
- **Files the Mech owns** (`docs/DOMAIN.md`, `conf/*.yaml`, adapted prompts
  in `.github/prompts/`, `research/templates/`). Take the template's
  structure and fixes; keep the Mech's domain content.
- **`clash`, `edited`, `deleted`.** Decide each with the person. Do not
  delete a file the Mech wrote without asking.
- **The site and browser.** If the Mech customized
  `src/<slug>/templates/`, check its customizations survived, and build the
  site (`just docs-build`) and look at it.

## 6. Upgrade notes

For each note of an accepted update, do its `action`. Each says how to tell
whether the Mech needs it. Some migrate records: do that with the Mech's
own skills (`extend-schema`, `curate-record`), keep every quote verbatim
and every CURIE checked, and append a `curation_history` event to each
record you change. Never change a record's `id` to follow a new
convention: ids are permanent.

If a note cannot be done now (a migration that needs curation time), leave
it for later in the report and say what remains.

## 7. Verify

```bash
cd <mech>
just install    # takes new dependencies; uv.lock changes with them
just qc
```

`just qc` must pass. When the network is up, run `just qc-full` too: a
template change can tighten a term or identity check, and only the full gate
runs those. A failure in the Mech's own tests after a `take` usually means
the Mech changed something the template's test assumes; fix the Mech or the
test, not the template's file. If the Mech has an issue tracker, also run
`just labels` when the workflows changed.

For a large update, run the `audit-mech` skill afterwards: it checks the
answers against the files, including the new ones.

## 8. Record

- Commit on the branch: "Sync with mechmaker <target>", with the accepted
  and declined updates in the message.
- Add a history record:

  ```bash
  just new-history --kind infrastructure --slug mechmaker-sync --event EDIT \
    --outcome changed --summary "Synced with mechmaker <target>" \
    --details "Took #..., declined #... (why). Notes acted on: ... Left: ..." \
    --actor claude-code --agent-tool claude-code --model <model-id> --apply
  ```

  Use `--outcome needs_followup` when a note or merge was left for later.
- Ask the person before you push or open a pull request. The pull request
  says, for a reviewer: the target version, each update taken in one line,
  each declined and why, each upgrade note and what was done for it, and
  what is left.

## Report

End with: the Mech's version before and after, the updates taken and
declined (and why), the new answers, the upgrade notes and what was done for
each, what `just qc` (and `just qc-full`) said, and anything left for the
person.
