---
name: extend-schema
description: >-
  Change the IngestMech data model in src/ingestmech/schema/ingestmech.yaml:
  add, narrow, rename or remove a class, slot or enum, and migrate existing
  records. Use when a curation need has no place in the schema, or when
  deciding whether it warrants one. Not for filling existing slots.
---

# Extend the schema

## First, decide whether to

A new slot is cheap to add and costly to fill. Before proposing one:

- Search the schema. The need may already have a place.
- Check `mech_shared.yaml`. Open questions and gaps are `Discussion`, and
  datasets are `Dataset`. Do not rebuild them.
- Write the population strategy. Who fills the slot, from what source, by
  what rule? If an agent fills it by judgment, the rule must be written down
  well enough that two agents fill it the same way.

## Never edit these

`mech_shared.yaml` and `history.yaml` are vendored. A test pins their
hashes. Changes go upstream to the fleet canon and come back by re-vendoring.

## Making the change

1. Edit `src/ingestmech/schema/ingestmech.yaml`. Give every new
   element a `description`.
2. For an ontology-bound slot, use the descriptor pattern: a `Descriptor`
   subclass whose `term` binds to a dynamic enum with a verified root. See
   the `ontology-terms` skill.
3. For evidence, reuse `EvidenceItem`. It carries the `implements` markers
   the reference validator looks for.
4. Update `tests/data/example_record.yaml` to exercise the change.
5. Run `just lint` and `just test`.

## Migrating records

A change that makes existing records invalid ships with its migration in
the same pull request:

1. Write the migration as a script under `scripts/migrations/`, named for
   the change. It reads each record, transforms it, and writes through
   `write_validated_record` in `src/ingestmech/records.py`.
2. Run it. Run `just validate-all`. Commit the script and the records.
3. Add one history record with `--kind schema` describing the change, and
   one with `--kind record` per record changed by hand.

## Afterward

Update `docs/DOMAIN.md` so the design record matches the schema. Update
`CLAUDE.md` if a rule changed.
