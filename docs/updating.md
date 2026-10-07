# Updating a Mech

mechmaker keeps improving: new checks, new commands, fixes to the record
browser and the workflows, and now and then a change in how every Mech
should do something. A Mech made months ago can take those improvements
without starting over, and without losing what it made its own.

## Ask your agent

Open your agent in the Mech's folder and paste this:

```text
Update this Mech to the latest mechmaker.

1. Install the mechmaker skills if they are not here: npx skills add monarch-initiative/mechmaker -y
2. Read the sync-mech skill and follow it.
3. Show me every update and what you recommend before you apply anything.
   Ask me before you push or open a pull request.
```

The agent works through it with you:

1. **Check.** It finds which version of mechmaker your Mech came from, and
   what changed since.
2. **Plan.** It lists each change, one per mechmaker pull request, with the
   files it touches. For each file it says whether your Mech changed it
   too. A file you never touched can take the new version as it is. A file
   you made your own, such as your data model or your site settings, needs
   the two sets of changes combined.
3. **Choose.** It explains what each change does for your Mech, recommends
   which to take, and asks you. You can decline a change, or keep a part of
   the Mech exactly as it is whatever changes touch it. Any new template
   questions are asked too.
4. **Apply and merge.** Copier brings in the chosen changes. The agent
   combines them with your own edits, and changes your data model by hand
   where the template's starting schema changed.
5. **Follow the upgrade notes.** Some changes need more than new files:
   records that must gain a field, a folder to stop tracking. mechmaker
   keeps a note for each, and the agent does what it says.
6. **Check and record.** `just qc` must pass. The agent commits on a
   branch, adds a history record saying what was taken and declined, and
   asks before it opens a pull request.

Nothing reaches your repository's main branch without your review.

## What can be updated

| Part | How it is updated |
|---|---|
| Commands, checks, tests | Taken as they are, unless you changed them |
| Agent skills and guidance (`.claude/`, `CLAUDE.md`) | Taken, merged with your edits |
| GitHub workflows and prompts | Taken; your adapted prompts keep their domain wording |
| Record browser and site | Taken, merged with any templates you customized |
| The data model | The template's change is made to your schema by hand, with the `extend-schema` skill, which migrates your records |
| Records | Changed only where an upgrade note says so, with the same evidence rules as any curation |
| Shared schema (`mech_shared.yaml`, `history.yaml`) | Taken as they are; a Mech never edits them |

A declined change is not offered again. If you change your mind later, the
agent can copy it in by hand.

## Only checking

To see whether a Mech is behind without changing anything:

```bash
uv run <skills>/sync-mech/scripts/sync_mech.py check .
uv run <skills>/sync-mech/scripts/sync_mech.py plan .
```

`<skills>` is where the mechmaker skills are installed, such as
`.agents/skills`. `check` reads only mechmaker's history. `plan` renders
your answers at each version and lists every file each change would touch.

## Without an agent

`just update-template` runs Copier's own update. It takes every change at
once and writes conflict markers where your edits and the template's meet.
That works for a Mech that has changed little. For one with a designed
schema and real records, the agent's way is safer: it lets you choose, and
it migrates records.

## For mechmaker developers

A change that existing Mechs must act on beyond taking files gets an entry
in `upgrade-notes.yml`, in the same pull request. The file's header says
what each field means. See [Developing mechmaker](developing.md).
