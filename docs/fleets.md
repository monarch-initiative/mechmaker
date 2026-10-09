# Fleets

A **Fleet** is a set of Mechs whose records link to each other's. Each
member is a complete Mech in its own repository, with its own schema,
records, checks and curators. One more repository, the **Coordinator**,
holds what the members share:

- **`fleet.yaml`**, the Fleet's definition: the members, what one record of
  each is, and the **relationships** through which one member's records may
  link to another's. It follows a LinkML schema, the Fleet model, so the
  collection as a whole is data, checked like a record.
- **The canon**, the files every member carries byte for byte: the shared
  schema modules `mech_shared.yaml` and `history.yaml`, and any others the
  Fleet adds. Each member is pinned to one Coordinator commit.
- **The checks** that need every member at once: that each member's answers
  agree with `fleet.yaml`, that every member carries the canon at one shared
  pin, and that every link between records points at a record that exists.

The Coordinator holds no records and pushes to no member. Changes reach a
member by a pull request in that member.

The design follows [culturebotai-claw](https://github.com/CultureBotAI/culturebotai-claw),
which coordinates the CultureBotAI Mechs: one membership list, a canon of
shared files pinned by full commit, and a daily read-only audit of the whole
fleet. claw keeps the relationships between its Mechs in prose and in each
Mech's own scripts. A mechmaker Fleet declares them in `fleet.yaml`, builds
them into each member's schema, and checks every link.

## Making one

Ask your agent, in the folder where the repositories should live:

```text
I want a Fleet of Mechs about: microbial taxa, their habitats and their traits.

1. Install the mechmaker skills: npx skills add monarch-initiative/mechmaker -y
2. Read the make-fleet skill and follow it, from its step 0.
3. Ask me before you install a tool, and before you create anything on GitHub.
```

The `make-fleet` skill surveys the Fleet (which members, which side of each
relationship holds the links), generates the Coordinator, declares the
members and relationships, makes each member with `make-mech` from its fleet
answers, syncs the canon, and audits. The Coordinator comes from the same
template as a Mech:

```bash
copier copy --data kind=coordinator --data fleet_name=MicrobeFleet \
  gh:monarch-initiative/mechmaker microbefleet-coordinator
```

## A relationship, end to end

In the Coordinator's `fleet.yaml`:

```yaml
relationships:
  taxonmech-habitats:
    subject: taxonmech           # whose records hold the links
    object: habitatmech          # whose records they point to
    slot: habitats
    description: Habitats a taxon is found in.
    relations:
      FOUND_IN: {description: The taxon has been isolated from or observed in the habitat.}
    bases:
      LITERATURE: {description: A cited source reports it, with a quote in the record's evidence.}
```

`just answers taxonmech` in the Coordinator prints TaxonMech's Copier
answers, with this relationship as a `fleet_links` entry. From it,
mechmaker gives TaxonMech's schema a `HabitatMechLink` class (a
`CrossCorpusLink` from `mech_shared`, with `FOUND_IN` and `LITERATURE` as
its only allowed relation and basis) and a `habitats` slot on the record.
A TaxonMech record then says:

```yaml
habitats:
  - corpus: HabitatMech
    identifier: ENVO:00002149
    relation: FOUND_IN
    basis: LITERATURE
    source_version: 0123456789abcdef0123456789abcdef01234567
```

TaxonMech's own `just qc` checks the relation, the basis, the corpus name
and that `source_version` is a full commit. The Coordinator's `just audit`
checks what a member cannot see: that `ENVO:00002149` is a HabitatMech
record at that commit, and still is on HabitatMech's main. A target that
has since gone is a warning: the link was right when made, and someone
should look.

A shared ontology term between two records is a lead for a link, never a
link by itself.

## The canon and its pins

| In the Coordinator | In each member |
|---|---|
| `canon/schema/*.yaml`: the canonical copies | the same files, under `src/<slug>/schema/` |
| `canon/manifest.yaml`: each file's target and sha256 | `fleet/pin.yaml`: the Coordinator commit, and each file's sha256 |
| `just sync <member> <checkout>`: writes both, in the member's checkout | `just qc`: the files match the pin; `just check-fleet --online`: the pin matches the Coordinator |
| `just audit`: every member on one pin, with matching files | |

A member's online check reads the Coordinator's manifest from GitHub. For a
private Coordinator, give each member a repository secret `FLEET_TOKEN`
holding a token that can read it; the member's weekly sweep passes it on.
Until its first sync, a member's pin is empty, and the check says so as a
warning.

A change to a shared file is made once, in the Coordinator, merged, then
synced into every member (the Coordinator's `change-canon` skill). In a
member, an update from mechmaker leaves the canon files and the pin alone.
The Coordinator itself takes a newer canon from mechmaker with
`just update-template`, and releases it the same way.

## What the Coordinator contains

| Path | What it is |
|---|---|
| `fleet.yaml` | members and relationships |
| `src/<fleet>_coordinator/schema/fleet_schema.yaml` | the Fleet model |
| `canon/` | the shared files and their manifest |
| `src/<fleet>_coordinator/` | the `fleet` command |
| `.claude/skills/` | `onboard-mech`, `add-relationship`, `change-canon` |
| `.github/workflows/` | `qc`; `fleet-audit` (daily, read-only, opens an issue here on failure); `docs` |
| `docs/` | the site: members, relationships (with a diagram), the canon, the Fleet model |

| Command | What it does |
|---|---|
| `just qc` | lint, `fleet.yaml`, the canon, tests, docs build |
| `just fetch` | clone or refresh every member under `cache/members/`, anonymously |
| `just audit` | answers, canon pins and links, for every member |
| `just status` | one row per member: commit, records, mechmaker version, pin |
| `just answers <member>` | the member's Copier answers |
| `just sync <member> <checkout>` | the canon into a member (dry run; `--apply` writes) |

Commands that read members take `--root <member>=<path>` to use a local
checkout, for work not yet pushed.

## Joining an existing Mech

A Mech made with mechmaker joins through the Coordinator's `onboard-mech`
skill: declare it in `fleet.yaml`; bring the Mech up to a mechmaker that
knows Fleets (`sync-mech`); take `just answers <member>` in the Mech with
`uvx copier update --vcs-ref=:current: --skip-answered --defaults --data-file`;
sync the canon; and set it `active`. The update to a Fleet-aware mechmaker
comes first because `:current:` renders the mechmaker the Mech was last
updated from, and one from before Fleets drops the Fleet answers. A Mech in the CultureBotAI fleet (`collection: xmech`)
is coordinated by claw, which is not a mechmaker Coordinator; it joins
through claw's own `onboard-mech`.
