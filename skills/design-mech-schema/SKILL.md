---
name: design-mech-schema
description: >-
  Turn a freshly generated Mech's scaffold schema into a real domain model:
  write docs/DOMAIN.md, choose the record's sections, apply the DisMech
  modeling patterns, and prove the design on real records. Use right after
  `copier copy` from mechmaker, or when a young Mech's schema needs a
  redesign before many records exist. For later incremental changes, use the
  Mech's own `extend-schema` skill.
---

# Design a Mech schema

Work in the generated repository. The scaffold schema has one section per
ontology chosen at generation time. It validates, and it is not a design.

## Order of work

1. Write `docs/DOMAIN.md` before touching the schema. Fill every TODO. The
   schema follows the document, never the other way round.
2. Change `src/<slug>/schema/<slug>.yaml`.
3. Update `tests/data/example_record.yaml` to exercise every section.
4. Write two real records on paper against the schema (the paper test,
   below). Fix what does not fit.
5. `just lint`, `just test`, `just qc`.
6. Record the change: `just new-history --kind schema --slug <slug>
   --event EDIT --outcome changed --summary ... --details ... --apply`.

## Sections

For each section a record will carry, write in `docs/DOMAIN.md`:

| Question | Why |
|---|---|
| What question does it answer about the record? | A section with no question is decoration. |
| What ontology grounds it, under which root? | Sets the dynamic enum. |
| One or many? | Cardinality. |
| Who fills it, from what, by what rule? | A slot nobody can fill reliably is noise. |
| One worked example | Tests that the rule is followable. |

Cut scaffold sections the domain does not need. Rename them to the domain's
words (`chemical_entities` may really be `metabolites_produced`). Split one
when the domain distinguishes two roles for the same ontology (`substrates`
and `products`, both CHEBI).

## Patterns

These come from DisMech. Use them before inventing new structure.

**Descriptor.** A mention of something: `preferred_term` (required, the
curator's words), `term` (optional ontology binding, `{id, label}`),
`description`, `evidence`. One `Descriptor` subclass per role, each binding
`term.id` to a dynamic enum:

```yaml
MetaboliteDescriptor:
  is_a: Descriptor
  slot_usage:
    term:
      bindings:
        - binds_value_of: id
          range: MetaboliteTerm
          obligation_level: REQUIRED
```

```yaml
MetaboliteTerm:
  reachable_from:
    source_nodes: [CHEBI:25212]   # metabolite; check it with check_terms.py
    is_direct: false
    include_self: true
    relationship_types: [rdfs:subClassOf]
```

**Qualified descriptor.** When a mention needs a direction or a context
(increased, decreased, absent; located in an anatomical site; in a life
stage), add explicit slots to the descriptor subclass with enums or bound
terms. Prefer an explicit slot to a generic predicate-value pair.

**Evidence.** Reuse `EvidenceItem`. Its `reference` and `snippet` slots
carry the `implements` markers that linkml-reference-validator looks for.
A new evidence class without them is never checked.

**Causal graph.** `mechanisms` holds `MechanismNode`s named uniquely in the
record; each node's `downstream` edges name other nodes. Give a node bound
terms (a GO process, a cell type) so graphs compare across records. Put
evidence on an edge when it supports the link.

**Discussion and Dataset.** Open questions, knowledge gaps, controversies
and to-dos are `Discussion`. Public datasets are `Dataset`. Both come from
the vendored `mech_shared.yaml`. Never rebuild them.

**Cross-Mech link.** A link to another Mech's record is a `Term`-like pair
`{id, label}` where `id` is that Mech's record id. Say in DOMAIN.md which
Mech and how the link is checked.

**Quantity.** A measured value is a small class: `value` (float), `unit`
(bound to UO), `conditions`, `evidence`. Never a string like "5 mg/L".

**Closed vocabulary.** When the values are the Mech's own and small, use a
static enum with a `description` on each value. When they come from an
ontology, use a dynamic enum. Do not copy ontology terms into a static enum.

## The paper test

Take two real entities, one typical and one awkward. Write their records in
full against the new schema, with real sources fetched and quoted. Anything
that has nowhere to go, or goes in `notes` because nothing else fits, is a
design gap. Anything the schema asks for that no source gives is a slot to
drop or make optional.

## Anti-patterns

- **A `notes` catch-all.** Closed validation exists so that meaning has a
  place. If it keeps landing in `notes`, add the slot.
- **Required fields the sources cannot fill.** They get filled with guesses.
- **Deep nesting.** Past three levels, records become hard to curate and
  hard to review. Flatten or factor a separate record type.
- **Guessed roots.** A dynamic enum root must be checked against the terms
  it is meant to admit.
- **Editing vendored files.** `mech_shared.yaml` and `history.yaml` are
  pinned by hash. Change them upstream.
- **Schema for one record.** A slot used by one record in a hundred is a
  `Discussion` or a note, not a slot.

## When done

`docs/DOMAIN.md` has no TODOs. The example record exercises every section.
`just qc` passes. Run `just docs-serve` and read the schema pages as a
newcomer would: every class, slot and enum should have a description that
says what it is for. They are generated from the schema, so fix a thin page
in the schema. Update `CLAUDE.md` if a rule changed, and
`registry/<slug>.md` if the record type or ontologies changed.
