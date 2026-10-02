---
name: survey-domain
description: >-
  Survey a knowledge domain before building a Mech for it: define what one
  record is, how records are keyed, which ontologies ground them, which
  sources can feed them, and which existing Mechs overlap. Produces a domain
  brief that drives the mechmaker Copier answers and docs/DOMAIN.md. Use as
  the first step of make-mech, or alone when asked whether a domain suits a
  Mech.
---

# Survey a domain

The output is a brief, written to a file, with the sections below. Every
identifier in it is looked up, never recalled. Every count is measured on a
sample, never estimated from memory.

## 1. The record

A Mech keeps one record per entity. Name the entity. This is the decision
everything else rests on.

- Write one sentence: "One record is one ___." Then list three things a
  person might expect to be records that are **not**, and say where each goes
  instead: a field on a record, a record in another Mech, or nowhere.
- Prefer an entity that has a public identifier, that people argue about
  mechanistically, and that has a literature. DisMech: a disorder. SOMAMech: a
  publication, extracted. CellStructureMech: a cell structure.
- Say the granularity rule. When are two candidates one record? When is a
  subtype its own record? A rule a second agent would apply the same way.
- Estimate the corpus size from a real list (an ontology branch, a database
  table), with the query you used.

## 2. Identity

- Which ontology keys records? Look for the one whose terms match the record
  entity one to one. None may fit; then records mint their own ids.
- Find the root. Take five expected records, look up their CURIEs, and find
  the most specific common is-a ancestor. `<scripts>` is the make-mech
  skill's `scripts/` folder, `../make-mech/scripts` from this skill's own:

  ```bash
  python3 <scripts>/check_terms.py search <ontology> "<name>"
  python3 <scripts>/check_terms.py under <ROOT> <CURIE> <CURIE> ...
  ```

- Look one level down. Do terms under a record's term mean something else,
  such as national populations under a breed? Then only the root's direct
  children are records: say so in the brief, set
  `identity_direct_only: true`, and check the sample with
  `check_terms.py under --direct <ROOT> <CURIE> ...`. Without it, any term
  under the root keys a record, and so does the root itself.
- What fraction of expected records have a term? Measure it on the sample.

## 3. Grounding

For each kind of thing a record will mention (cells, chemicals, taxa,
processes, anatomy, phenotypes, environments, assays), name the ontology,
pick a root, and check that two or three terms you expect to bind sit under
it with `check_terms.py under`. Checking only the root's `label` is not
enough: some ontologies, such as GAZ as OLS serves it, keep terms without an
is-a parent, and a dynamic enum cannot reach them. An ontology need not be on
OLS: anything OAK reads works (OBO Foundry SQLite, BioPortal, a local file),
checked with `check_terms.py --adapter`. Note gaps: kinds of thing no
ontology covers well. Those become `preferred_term` text with open
`CURATION_TODO` discussions, or a case for a new ontology.

## 4. Sources

List what can feed curation. For each: what it gives, license (read the
terms; write UNKNOWN if not found), access (API, bulk, pages), whether its
identifiers are CURIEs the Mech can use, and a size measured on a sample.

- Literature is always a source. Write a PubMed query that finds the core
  papers and report its hit count.
- Existing databases and knowledge bases can seed records but never replace
  evidence. A seeded claim still needs a quoted source.

These rows become `curation/source_queue.tsv` in the new Mech.

Say whether deep research would help. It helps when a record's subject has
a large literature a curator cannot read in one sitting; it adds little
when the facts come from one database. Put the answer in the brief, as
`deep_research: true` or `false`.

## 5. Neighbors

Read the registry. The whole thing is one JSON file:
https://monarch-initiative.github.io/mechregistry/registry/mechs.json.
Each entry's `record_type`, `ontologies` and `description` say what it
covers. For each Mech that overlaps:

- what it records, and where the boundary between it and this Mech lies;
- whether this Mech should link to its records (`consumes`), hand off to it
  (`hands_off_to`), or share its vocabulary (`shares_vocabulary_with`).

If an existing Mech already records this entity, say so first. Extending it
may be better than starting a new one.

## 6. Mechanism

Does this domain have causal chains worth a graph? DisMech's pathographs
link a cause through processes to phenotypes. If the domain's literature
talks in mechanisms, set `causal_graphs: true`. If it talks in attributes
and measurements, set it false.

## The brief

Write it as markdown with these headings: Record, Identity, Grounding,
Sources, Neighbors, Mechanism, Open questions. End with a draft
`answers.yml` for the parts the survey decides. Leave the user's own facts
(names, org, licenses) for the user.
