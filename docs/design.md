# Design decisions

This page is the register of what every Mech shares, and why. mechmaker is
where a Mech is defined: the template writes these decisions into each new
Mech, and its checks enforce them. People and AI agents both need one place
that answers *why is a Mech built this way, and what may differ from one Mech
to the next?*, without working it out again from the template each time.

Much of this was first decided in
[DisMech](https://github.com/monarch-initiative/dismech), the knowledge base
of disease mechanisms that the pattern comes from. Its own
[design decisions](https://github.com/monarch-initiative/dismech/blob/main/docs/explanation/design-decisions.md)
cover diseases in depth. This page keeps what holds for a Mech in any
field, and says where mechmaker has since gone its own way.

**How to use this page**

- **Agents**: read it before a structural, scope, ontology or evidence
  decision, in mechmaker or in a Mech. When a decision here bears on a
  change, cite it. Do not silently contradict one. If one looks wrong or
  stale, say so to the person.
- **People**: to change a decision, open an issue on mechmaker with the
  change and the reason. Change the template and this page in the same pull
  request. If existing Mechs must act on the change by hand, add an entry to
  `upgrade-notes.yml` too (see [Developing mechmaker](developing.md)).
- This page **describes** decisions. Where a file enforces one, that file is
  canonical, and is named below under *Enforced by*.

**Where other decisions live**

| Document | What it decides |
|---|---|
| This page | What every Mech shares |
| A Mech's `docs/DOMAIN.md` | That Mech's own decisions: what a record is, its identity and granularity, its sections, what is out of scope. Where a Mech departs from this page, it says so there, and why |
| A Mech's `CLAUDE.md` and `docs/CURATION.md` | The rules an agent follows while curating, as the template wrote them for that Mech |
| [DisMech's design decisions](https://github.com/monarch-initiative/dismech/blob/main/docs/explanation/design-decisions.md) | DisMech's own: disease granularity, its ontologies, its evidence axes |
| [The Mech standard](https://github.com/CultureBotAI/culturebotai-claw/blob/main/docs/guides/MECH_STANDARD.md) in culturebotai-claw | What the CultureBotAI fleet's repositories must hold: files, CI and fleet membership, measured across its Mechs |

## 1. What a Mech is

**Decision.** A Mech is a knowledge base curated mostly by AI agents and
reviewed by people. It holds one kind of thing, one record per thing, and
follows five rules:

1. **One file per thing.** Each record is one YAML file.
2. **Standard vocabulary.** Records name things with terms from established
   ontologies.
3. **Every claim has a source.** Each claim cites a source and quotes it word
   for word, and a program checks the quote.
4. **A full history.** Every change records who made it, human or AI, and
   why.
5. **People review.** Agents propose. People accept or not.

**What a Mech is not.**

- **Not an ontology.** A Mech uses ontology terms; it does not mint them. A
  term that is missing is a finding, sent to the ontology as a new-term
  request (§4).
- **Not a copy of a database.** An ingest row or a converted record is a
  seed. A Mech earns its place by the curated, quoted claims it adds, which
  a database lookup would not give. DaTMech says this outright: it curates a
  ZIP code area when an incident touched its water, because a record with
  none "says little a database lookup would not".
- **Not a knowledge graph.** A Mech exports one (KGX), but its own model is
  built for curating and reviewing records (§6).
- **Not a source of truth by itself.** The checks prove that citations
  exist, quotes are exact and terms are real. They do not prove the science
  is right. That is what review is for (§7).

**Rationale.** These rules are what made DisMech trustworthy with agents
doing most of the work. Each one closes a way an agent goes wrong: a made-up
identifier, a paraphrase passed off as a quote, a change nobody can trace, a
claim nobody checked.

## 2. One record, one file, one thing

**Decision.** A Mech has one record class. Each record is one YAML file
under the records folder, validated against that class. The filename stem
comes from the record's `name`: lowercase, each run of other characters made
one underscore.

Each Mech decides, in its `docs/DOMAIN.md`, what counts as one record, what
does not, and where the near misses go instead: a field on a record,
another Mech, or nowhere.

**Rationale.** One file per record means two people, or two agents, rarely
touch the same file, and a pull request shows one record's change whole.
Plain YAML can be read and edited by curators and agents alike.

**Enforced by.** `records_dir` and `record_class` (Copier answers); the
schema; `just validate`; `docs/DOMAIN.md`, whose TODOs `design-mech-schema`
fills.

**How Mechs diverge.** Granularity is each Mech's own:

| Mech | One record is | Granularity rule |
|---|---|---|
| GoatMech | A goat breed | The Vertebrate Breed Ontology decides: one VBO term, one record. A national population of a breed is not a record |
| IngestMech | A Monarch ingest | One repository, one record, however many transforms it holds |
| DaTMech | A US ZIP code area | One ZIP code, one record. Watersheds, plants and incidents are sections, repeated on each area they touch |
| DisMech | A disorder | Close variants are subtypes inside one file; a separate file needs its own MONDO identity and an independent mechanism |

## 3. Identity

**Decision.** Every record has an id that never changes when the record is
renamed, and no two records share one.

- Where an ontology names the things a Mech holds, records are keyed by its
  CURIE, which must sit under the identity root (or be its direct child,
  when the Mech asks for that). `record_term` repeats the id with the
  ontology's label.
- Where no term exists yet, or no ontology names the things at all, the
  record takes a stable identifier from a source that names it uniquely, or
  a minted id, `<slug>:<uuid>`. A minted record can be re-grounded later.
- A record that should no longer be current is kept as `DEPRECATED`, not
  deleted, so links to it still resolve.

**Rationale.** Other Mechs, exports and people link to records by id.
An ontology id ties a record to what the field already calls the thing; a
minted id is the honest fallback when the field has no name for it.

**Enforced by.** `identity_prefix`, `identity_root`, `identity_direct_only`
(Copier answers); the schema's `IdentityTerm` enum; `just check-identity`;
the duplicate-id check in `just qc`; `just new-record`, which mints an id
when given none.

**How Mechs diverge.** GoatMech keys by VBO and accepts direct children of
`VBO:0400025` Goat breed only, so a national population cannot be a record.
IngestMech mints `ingestmech:<repository-name>`; DaTMech mints
`datmech:<ZIP>`. Neither has an ontology to key by.

## 4. Ontologies: reused, checked, never guessed

**Decision.** A Mech names things with terms from established ontologies.
It does not invent identifiers.

- **Descriptors.** A mention of something is a descriptor: `preferred_term`
  (the curator's words, required), `term` (an optional `{id, label}`
  binding), a description and evidence. Each role gets its own descriptor
  class, whose `term.id` is bound to a dynamic enum.
- **Dynamic enums, checked roots.** A dynamic enum admits terms under one
  root of an ontology. Every root in mechmaker's catalog was checked against
  the ontology before it was added, and a Mech's own roots are checked
  against the terms they are meant to admit.
- **The label is the ontology's.** `term.label` matches the ontology
  exactly. Nuance goes in `preferred_term`.
- **Never guess a CURIE.** An unverified term is worse than none. Leave
  `term` unset, keep `preferred_term`, and open a `CURATION_TODO`
  discussion. A term the ontology lacks is a finding: consider a new-term
  request to it.
- **Most specific accurate term.** If only a broad term fits, bind it and
  say so. Do not bind a narrower term because it exists.
- **Static enums for the Mech's own values.** A small closed set the Mech
  defines is a static enum, each value described. Ontology terms are never
  copied into one.

**Rationale.** A made-up identifier is the agent error most likely to pass
unnoticed: it looks right. Checking every term against its ontology, offline
from a committed cache, is the defense. Reusing ontologies keeps records
comparable across Mechs.

**Enforced by.** `ontology_catalog` in `copier.yml`, with each root checked
by `skills/make-mech/scripts/check_terms.py`;
[linkml-term-validator](https://github.com/linkml/linkml-term-validator) in
`just validate`; `conf/oak_config.yaml`, which says which service checks
which prefix; `cache/`.

**How Mechs diverge.** Each Mech chooses its ontologies and roots
(`ontologies`, `extra_ontologies`). Where an ontology cannot serve, the Mech
picks another and records why: GoatMech binds a breed's origin to an NCIT
country rather than a GAZ place, because GAZ's countries have no is-a parent
a dynamic enum can reach, and keeps the finer place in `preferred_term`.

## 5. Evidence: every claim quoted, every quote checked

**Decision.** Every claim that could be wrong carries evidence: a reference
and a snippet copied word for word from it.

- **Exact quotes.** The snippet is checked against the fetched source.
  `...` joins two exact spans; `[...]` marks an editorial note; nothing else
  may differ. Paraphrase goes in `explanation`, and a paraphrased snippet
  fails.
- **Fetch before quoting.** Sources are fetched and cached
  (`just fetch-reference`), and quotes are added with `just add-evidence`,
  which checks the quote before writing it. The caches are written only by
  the tools, never by hand, and are committed so the check runs offline.
- **The description is a claim too.** Each fact in it is quoted in
  `description_evidence` or stated with evidence in a section.
- **Disagreement is kept.** `REFUTE` evidence stays on the record, with a
  `CONTROVERSY` discussion. A record that shows disagreement is better than
  one that hides it.
- **No source, no claim.** A gap is recorded as a `KNOWLEDGE_GAP`
  discussion, not filled from memory.
- **Leads are not sources.** A deep-research report, a news lead, an ingest
  row and a knowledge graph edge point to sources. None is cited. The
  primary source it points to is fetched and quoted instead.

**Rationale.** The exact-quote check is the main defense against an agent
inventing a citation or putting words in a source's mouth. It is cheap to
run on every pull request, and it makes every claim auditable by a reader
who has never seen the Mech before.

**Enforced by.** `EvidenceItem` in the schema, whose `reference` and
`snippet` slots carry the markers
[linkml-reference-validator](https://github.com/linkml/linkml-reference-validator)
looks for (a new evidence class without them is never checked);
`just validate`; checks in `validate.py` that a snippet is more than the
source's title and that a cited title matches the source; `references_cache/`.

**How Mechs diverge.** What a source *is* depends on the field.
`EvidenceSourceEnum` is meant to be replaced, and each example did:
GoatMech's values are `ENCYCLOPEDIA`, `BREED_STANDARD`,
`CHARACTERIZATION_STUDY` and others; IngestMech's include
`INGEST_REPOSITORY` (a file in the ingest's repository, pinned to a commit)
and `REGISTRY`; DaTMech's include `GOVERNMENT_RECORD`,
`GEOSPATIAL_DATASET` and `MONITORING_DATA`. Reference types differ too:
IngestMech quotes repository files by URL at a pinned commit, where DisMech
quotes papers by PMID.

## 6. LinkML, a closed schema, and the export layer

**Decision.** A Mech's data model is a [LinkML](https://linkml.io/) schema
in the repository, and it is closed: a field the schema does not define is
an error. Shared standards such as Biolink are used at the export layer, not
inside the curation model.

- **Closed.** If something real has nowhere to go, the schema gets a slot
  (the Mech's `extend-schema` skill), and records migrate. It does not go in
  `notes`.
- **One schema, many formats.** `just export` writes the records as JSON,
  RDF, SQL, tables and knowledge graph files from the one schema, and reads
  each back.
- **Biolink at export.** `conf/kgx.yaml` maps sections to Biolink
  categories and predicates for KGX. A Mech whose things Biolink does not
  cover sets `biolink: false` and names its own.
- **Every prefix declared.** Each CURIE prefix a record can carry has its
  full URI in the schema, so the RDF exports expand it.

**Rationale.** LinkML gives YAML that people and agents can edit, ontology
binding through dynamic enums, generated documentation, and many output
formats from one source. A closed schema means every piece of meaning has a
named place a check can see. Keeping the curation model apart from exchange
formats lets each change without forcing churn on the other; DisMech made
the same choice for Biolink.

**Enforced by.** `src/<slug>/schema/<slug>.yaml`; `just validate`;
`conf/export.yaml` and `conf/kgx.yaml`; `just export`, which fails on a
prefix with no URI.

**How Mechs diverge.** The schema is each Mech's own, designed with
`design-mech-schema` from its `docs/DOMAIN.md`; the scaffold sections are a
start, cut and renamed to the field's words. IngestMech stores
`biolink:` class CURIEs as data, because what its records describe is which
Biolink associations an ingest writes. DaTMech adds places (bounding boxes)
for its map.

## 7. Status and review

**Decision.** A record is `DRAFT`, then `PROPOSED` when complete and valid,
then `REVIEWED` when a person accepts it. An agent takes a record no
further than `PROPOSED`. `DEPRECATED` keeps a record for provenance. The
pull request is the review gate: nothing reaches `main` without a person's
approval.

**Rationale.** Agents do most of the work, so the one step they never take
is the one that says a person has checked it. A reader can always tell
reviewed content from proposed content.

**Enforced by.** `CurationStatusEnum`; a check that a `REVIEWED` record has
a review event in its history by a person, not marked as assisted by a
model; the pull request, and the `review` workflow where turned on.

## 8. History

**Decision.** Every change appends a `curation_history` event to the record:
who (human or agent), when, what and why. Every curation session also adds
one file under `history/`, which is never edited afterwards.

**Rationale.** The record's own events say what happened to it; the session
files say what a session did across records. One new file per session means
parallel sessions never conflict over a shared log.

**Enforced by.** `history.yaml` (shared, §9); `just new-history`;
`just qc`.

## 9. Shared modules

**Decision.** Classes every Mech needs the same way come from two shared
schema modules, copied byte for byte into each Mech:

- `mech_shared.yaml`: `Discussion` (open questions, knowledge gaps,
  controversies, to-dos), `Dataset`, `CrossCorpusLink` and
  `SupportingReference`;
- `history.yaml`: curation history.

A Mech never edits them. They change upstream, in culturebotai-claw, and
reach a Mech through mechmaker or, in a Fleet, through its Coordinator.

**Rationale.** Tools that read every Mech (fleet audits, MechRegistry, a
Fleet's checks) can rely on these classes meaning the same thing
everywhere. A copy that drifts silently breaks that, so the copies are
checked by hash.

**Enforced by.** The sha256 and md5 checks in mechmaker's tests and in each
Mech's `tests/test_schema.py`; in a Fleet, `fleet/pin.yaml` and
`just check-fleet`. See [Fleets](fleets.md).

## 10. Links between Mechs

**Decision.** A link from a record in one Mech to a record in another is a
subclass of `CrossCorpusLink`: the target Mech, the target record's id
verbatim, a relation from an enum, a basis, and the commit of the target
that was checked. A shared ontology term is a lead for a link, not a link.

**Rationale.** Mechs are separate repositories that change on their own.
Naming the commit that was checked makes a link verifiable later, and keeps
a reader from following a link to a record that has since changed.

**Enforced by.** `CrossCorpusLink` in `mech_shared.yaml`; in a Fleet, the
relationships in the Coordinator's `fleet.yaml` and its audit, which checks
that each link's target exists.

**How Mechs diverge.** A Mech outside a Fleet adds link classes itself, when
it needs them. A Fleet member gets them from its `fleet_links` answer.
DaTMech names the point where it would split: when records start repeating
the same incident many times, incidents get their own Mech.

## 11. Agents and automation

**Decision.** Agents do most of the curation, started by people or by
GitHub workflows. Every agent reads the Mech's `CLAUDE.md` (or `AGENTS.md`)
and uses its skills.

- An agent that reads text anyone can write (an issue, a comment, a news
  story) gets no write permission. It returns structured output, and a step
  with no model publishes it.
- Agent workflows are opt-in, chosen per Mech, and pin the action they run.

**Rationale.** Text from the public can carry instructions. An agent that
reads it must not be able to act on them with the repository's credentials.

**Enforced by.** The workflow templates under `template/.github/`; the
`workflows` answer; mechmaker's tests, which check the pinned action and
credential lines match across workflows, and `actionlint`.

## 12. Checks run offline, and the same everywhere

**Decision.** `just qc` is every check that needs no network, and is what CI
requires. It passes on a fresh Mech. `just qc-full` adds the live checks of
every term and quote. Answers from ontology services and copies of cited
sources are committed, so the offline checks are repeatable.

**Rationale.** A check that passes on one machine and fails on another, or
fails because a service is down, teaches people to ignore it.

**Enforced by.** The `justfile`; `cache/` and `references_cache/`;
mechmaker's `just test-generated`, which generates sample Mechs and runs
their `just qc`.

## 13. Optional parts stay off until the field needs them

**Decision.** Causal graphs, the record browser, maps, deep research, news
leads, structured ingests, agent workflows, output formats and database
loads are Copier answers. A Mech turns on what its field needs, and its
`.copier-answers.yml` records the choice.

**Rationale.** Each part has a cost: files to read, checks to keep green,
and for some, money per run. A Mech that carries parts it does not use is
harder to curate and to review.

**How Mechs diverge.** DisMech is built around causal graphs; none of the
three examples has one. DaTMech turns on news leads, because local news
covers water incidents that papers may never report; GoatMech and DaTMech turn on deep
research; IngestMech loads its records into MongoDB and Neo4j.

## What a Mech may change, and what it keeps

A Mech owns its domain. It keeps the rules that make it a Mech.

| A Mech decides | Every Mech keeps |
|---|---|
| What one record is, and its granularity (§2) | One record, one file (§2) |
| Its identity scheme: an ontology root, a source's ids, or minted ids (§3) | Ids that never change and never repeat (§3) |
| Its ontologies and roots (§4) | Checked terms, ontology labels, no guessed CURIEs (§4) |
| Its sections, slots and static enums, including `EvidenceSourceEnum` (§5, §6) | A closed LinkML schema (§6) |
| Its reference types and sources (§5) | Exact, checked quotes; leads are never sources (§5) |
| Its curation priorities, such as DaTMech's `curation_priority` rule | Agents stop at `PROPOSED`; people review (§7) |
| Its optional parts (§13) | History on every change (§8) |
| Whether and how it links to other Mechs (§10) | The shared modules, unedited (§9) |

A departure from the right-hand column is a departure from being a Mech. If
a Mech's field truly needs one, record it in that Mech's `docs/DOMAIN.md`
with the reason, and open an issue here: it may be a decision this page
should change.

## Open questions

Decisions not yet made, or where mechmaker and DisMech now differ.

| Area | Status |
|---|---|
| Evidence direction | **Open.** The template's `EvidenceSupportEnum` still has `PARTIAL` and `WRONG_STATEMENT`. DisMech retired both on 2026-08-29, keeping `supports` for direction only (`SUPPORT`, `REFUTE`, `NO_EVIDENCE`) and adding an optional `directness` slot, because `PARTIAL` was carrying several unrelated judgments. Whether mechmaker follows, and how existing Mechs would migrate, is undecided |
| A Mech's decision register | **Open.** A Mech records its own decisions in `docs/DOMAIN.md`. DisMech, at scale, keeps a separate register with dated decisions and the alternatives it rejected. Whether the template should give every Mech one, or when a Mech should start one, is undecided |
