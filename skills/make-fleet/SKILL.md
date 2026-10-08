---
name: make-fleet
description: >-
  Create a Fleet: several Mechs, each its own full repository, with declared
  relationships between their records, and a Coordinator repository that
  holds the Fleet's definition (fleet.yaml), the files every member shares,
  and the checks that read the members together. Survey the Fleet, generate
  the Coordinator from mechmaker, declare members and relationships, make
  each member with make-mech from its fleet answers, sync the shared files,
  and audit. Use when asked to make, deploy or set up several coordinated
  Mechs at once, a family or suite of linked knowledge bases, a Fleet, or a
  Coordinator. For one Mech, use make-mech.
---

# Make a Fleet

A Fleet is a set of Mechs whose records link to each other's. Each member
is a complete Mech, made with `make-mech`, in its own repository. The
Coordinator is one more repository, made from the same mechmaker template
with `kind: coordinator`. It holds no records. It holds:

- `fleet.yaml`: the members, what one record of each is, and the
  relationships through which one member's records may link to another's;
- `canon/`: the files every member carries byte for byte (the shared schema
  modules `mech_shared.yaml` and `history.yaml`), and the commit each member
  is pinned to;
- the `fleet` command: answers for each member, the canon sync, and the
  audit of the whole Fleet.

The design follows CultureBotAI's
[culturebotai-claw](https://github.com/CultureBotAI/culturebotai-claw), which
coordinates the CultureBotAI Mechs, and adds what claw keeps only in prose:
the relationships, as data, checked.

| Step | Who | Output |
|---|---|---|
| 0. Check the machine | script | a ready machine |
| 1. Survey the Fleet | you, with `survey-domain` | a Fleet brief, and a domain brief per member |
| 2. Generate the Coordinator | Copier | the Coordinator repository |
| 3. Declare | you | `fleet.yaml`: members `planned`, relationships |
| 4. Publish the Coordinator | the person | the Coordinator on GitHub |
| 5. Make each member | you, with `make-mech` | one Mech per member, from its fleet answers |
| 6. Sync the canon | script | `fleet/pin.yaml` in each member |
| 7. Link and audit | you and script | links in seed records; `just audit` passes |

Do not start with the members. The relationships are part of each member's
schema, and the order members are made in follows them.

## 0. Check the machine

As `make-mech` step 0: `python3 <make-mech scripts>/check_env.py --network`,
where `<make-mech scripts>` is the `scripts/` folder of the `make-mech`
skill beside this one.

## 1. Survey the Fleet

Write `fleet-brief.md`. It answers, in this order:

1. **The members.** One per kind of thing, and one sentence each: "one
   record is one ___". Two members never own the same kind of thing. If two
   would, they are one Mech, or the line between them is wrong. Check
   MechRegistry for an existing Mech that already owns one; it can join
   instead of being made again (the Coordinator's `onboard-mech`).
2. **The relationships.** For each pair whose records refer to each other:
   which side holds the link (the subject: the side whose curators know the
   fact and cite it), the slot name, the relations (UPPER_SNAKE_CASE, each
   with a meaning), and the bases (how a link is established: `LITERATURE`,
   an exact structure match, and so on). A shared ontology term between two
   records is a lead for a link, never a link by itself.
3. **The order.** A link names a record that already exists in the object
   Mech, at a commit. Make objects before subjects. A pair that links both
   ways is made object-first by the direction with more links.
4. **Scope notes.** Where one member's scope stops and another's starts, in
   a sentence for each side.

Then run `survey-domain` for each member, as `make-mech` step 1 does. Each
member's brief names its record entity, keys and ontologies. Start
`requests.yml` for the Fleet, beside the brief: what the person asks for,
in their words.

Show the person the members and relationships before generating anything.

## 2. Generate the Coordinator

Some answers belong to the person: the Fleet's name, the maintainer's name,
email, ORCID and GitHub login, the GitHub organization, the code license.
Ask for them. Then:

```yaml
# coordinator-answers.yml
kind: coordinator
fleet_name: MicrobeFleet              # CamelCase, ending in Fleet by convention
fleet_slug: microbefleet
fleet_description: >-
  MicrobeFleet records microbial taxa, the habitats they live in, and ...
author_name: ...
author_email: ...
author_orcid: ...
github_org: ...
github_user: ...
code_license: BSD-3-Clause
coordinator_workflows: [fleet-audit, docs]
```

```bash
copier copy --data-file coordinator-answers.yml --defaults \
  gh:monarch-initiative/mechmaker <dest>/microbefleet-coordinator
cd <dest>/microbefleet-coordinator
git init -b main
just install
just qc
```

As with a Mech, an absolute local path can stand in for `gh:...`, with
`--vcs-ref HEAD` to use a checkout as it is. `just qc` must pass on the
fresh copy; if it does not, stop and report it. Commit the untouched output
first.

## 3. Declare

Write the members and relationships from the brief into `fleet.yaml`. Its
header comment shows the shape; the Coordinator's `onboard-mech` and
`add-relationship` skills explain each field. Every member starts
`status: planned`. Each member's fields must be what its Mech will be:

| fleet.yaml | the member's Copier answer |
|---|---|
| key (`habitatmech`) | `mech_slug`, also its CURIE prefix |
| `name` | `mech_name` |
| `github` | `github_org`/`repo_name` |
| `record_class`, `records_dir` | the same names |
| `identity_prefix` | the same, when records are keyed by an ontology |

```bash
just validate        # fleet.yaml against the Fleet model and its rules
just docs-serve      # the members and the relationship diagram
```

Commit.

## 4. Publish the Coordinator

The members' canon pins name a commit of the Coordinator on GitHub, and
each member's `just check-fleet --online` reads it there. So the
Coordinator goes to GitHub before the first sync. Creating a repository and
pushing are visible to others: ask the person first, and say what will be
created and where.

## 5. Make each member

In the order from the brief, objects first. For each member:

1. In the Coordinator: `just answers <member> > <member>-fleet.yml`.
2. Follow `make-mech` from its step 2, with the member's domain brief from
   step 1. Merge `<member>-fleet.yml` into its `answers.yml`; those answers
   are fixed. Do not change `mech_name`, `mech_slug`, `github_org`,
   `repo_name`, `record_class`, `records_dir`, `fleet_name`,
   `fleet_coordinator` or `fleet_links` there: change `fleet.yaml`, and
   print the answers again.
3. The generated schema has one link class per relationship the member is
   the subject of (`<Object>Link`, a `CrossCorpusLink`), and a slot for it
   on the record. Keep them through `design-mech-schema`; a design that
   moves the slot onto a sub-object keeps the class.
4. Seed records as `make-mech` step 5 says. Links come in step 7 below,
   once the objects have records.
5. Stop before `make-mech`'s registration, and come back here. Register
   each member at the end, when the Fleet passes its audit.

## 6. Sync the canon

Each member was made with mechmaker's copies of the shared files and an
empty pin. Sync them from the Coordinator, from its checkout:

```bash
just sync <member> <path to the member>            # the plan
just sync <member> <path to the member> --apply
```

In the member, `just qc`, then commit `fleet/pin.yaml`. Then set the
member's `status: active` in `fleet.yaml` and commit that.

## 7. Link and audit

For each subject member, add links to its seed records. Each link names
the object Mech, the target record's id verbatim, a relation and basis from
the relationship, and the object's full commit that was checked:

```yaml
habitats:
  - corpus: HabitatMech
    identifier: ENVO:00002149
    relation: FOUND_IN
    basis: LITERATURE
    source_version: <git rev-parse HEAD in the HabitatMech checkout>
```

Read the target record in the object Mech at that commit; never type an id
from memory. The quote that supports the link goes in the record's evidence,
as for any claim.

Then, in the Coordinator, with every member's local checkout:

```bash
just audit --root habitatmech=<path> --root taxonmech=<path> ...
```

Once the members are on GitHub, `just fetch && just audit` does the same
from clean clones, and the `fleet-audit` workflow runs it daily. Every error
names the member and what to do.

Then run `audit-mech` on each member, register each with `register-mech`
if the person wants them listed, and report.

## Report

End with: the Coordinator's path and its `just qc`; each member's path and
`just qc-full`; the `just audit` output; the relationships declared and how
many links the seed records make; the decisions the person should look at
(the member boundaries, which side holds each link, the relations and
bases); and what is not done (members not yet on GitHub, registrations).

## Afterwards

- A new member, or an existing Mech joining: the Coordinator's
  `onboard-mech` skill.
- A new or changed relationship: its `add-relationship` skill.
- A change to a shared file, or a newer canon from mechmaker: its
  `change-canon` skill. In a member, an update from mechmaker leaves the
  canon files and the pin alone.
- Updating the Coordinator or a member from a newer mechmaker:
  `sync-mech`, in that repository.
