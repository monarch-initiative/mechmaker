# Design decisions

These are the design decisions behind every Mech. mechmaker's template
builds them into each new Mech, and its checks enforce them. Each decision
below gives the reason for it, the files that enforce it, and how a Mech can
adapt it to its own uses and curation criteria.

This is a general standard, and it changes as Mechs are built and used. The
pattern began with [DisMech](https://github.com/monarch-initiative/dismech),
whose own
[design decisions](https://github.com/monarch-initiative/dismech/blob/main/docs/explanation/design-decisions.md)
cover disease curation in detail.

**How to use this page**

- **Agents**: read it before making a structural, scope, ontology or
  evidence decision, in mechmaker or in a Mech. Cite the decision a change
  depends on. Do not silently contradict one. If one looks wrong or out of
  date, tell the person.
- **People**: to change a decision, open an issue on mechmaker with the
  change and the reason. Change the template and this page in the same pull
  request. If existing Mechs must act on the change by hand, also add an
  entry to `upgrade-notes.yml` (see [Developing mechmaker](developing.md)).
- This page describes decisions. Where a file enforces one, that file is
  canonical, and is named under *Enforced by*.

**Where other decisions live**

| Document | What it covers |
|---|---|
| This page | Decisions for all Mechs |
| A Mech's `docs/DOMAIN.md` | That Mech's own decisions: what a record is, identity and granularity, sections, scope. Where the Mech adapts a decision on this page, it says how, and why |
| A Mech's `CLAUDE.md` and `docs/CURATION.md` | The rules an agent follows while curating that Mech |
| [The Mech standard](https://github.com/CultureBotAI/culturebotai-claw/blob/main/docs/guides/MECH_STANDARD.md) in culturebotai-claw | The files, CI and fleet membership the CultureBotAI fleet's Mechs must have |

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
5. **People review.** Agents propose changes. People accept them or not.

**What a Mech is not.**

- **Not an ontology.** A Mech uses ontology terms. It does not mint them. A
  missing term is a finding, sent to the ontology as a new-term request
  (§4).
- **Not a complete catalog.** A Mech holds what its curation criteria
  select, not every thing of its kind. A Mech about water safety may cover
  only the places where incidents happened, not every place in a region.
  Rows from a database can seed records, but a record is worth keeping for
  the curated, quoted claims it adds.

**Rationale.** Each rule closes a way an agent goes wrong: a made-up
identifier, a paraphrase passed off as a quote, a change nobody can trace,
a claim nobody checked.

## 2. A Mech is not a source of truth

**Decision.** A Mech records claims that sources make, with the sources
quoted. It does not decide what is true.

- **The checks prove less than they seem to.** They prove that each cited
  source exists, each quote is exact, and each term is real. They do not
  prove that a claim is right, that the source is reliable, or that the
  record is complete.
- **`REVIEWED` means a person accepted the record**, not that the question
  is settled. Sources disagree, and later work overturns earlier work.
- **Disagreement stays visible.** Evidence that refutes a claim is kept on
  the record beside the evidence that supports it, with a discussion of the
  disagreement.
- **Cite the source, not the Mech.** Anyone using a record, including
  another Mech, follows it to the sources it quotes and cites those.

**Rationale.** Agents write most of a Mech, and a record that looks
complete and well cited is easy to over-trust. A reader who treats a Mech
as a map to the evidence, rather than a verdict, uses it as it was meant.

**Enforced by.** The evidence rules (§6); review status (§8); each Mech's
`docs/CURATION.md`.

## 3. One record, one file, one thing

**Decision.** A Mech has one record class. Each record is one YAML file
under the records folder, validated against that class.

Filenames follow one convention per Mech, and no two records share a
filename stem, because the record browser, history and research name a
record by its stem. The template's default derives the stem from the
record's `name`: lowercase, with each run of other characters replaced by
one underscore.

Each Mech defines in its `docs/DOMAIN.md` what counts as one record, what
does not, and where the near misses go instead: a section of a record,
another Mech, or nowhere.

**Rationale.** The aim is efficient curation by agents and efficient review
by people, with as little friction from technical problems and parsing as
possible. A record in plain YAML is easy for an agent to write and for a
person to read. Two curators may still edit the same file at once; YAML
makes the conflict easier to resolve, and the validator catches a merge
that leaves a record broken.

**Enforced by.** The `records_dir` and `record_class` answers; the schema;
`just validate`, whose default filename check is in `validate.py`;
`docs/DOMAIN.md`.

**How Mechs adapt it.** Granularity belongs to each Mech:

- Where an ontology already names the things, it can set granularity:
  one term, one record, and a synonym is not a second record.
- Where nothing names them, the Mech states its own rule, such as one
  software repository per record however many components it holds, or one
  postal area per record.
- A Mech may keep close variants as subtypes inside one record, and give a
  variant its own record only when it has its own identity and differs
  enough to need one.

## 4. Identity

**Decision.** Every record has an id that never changes when the record is
renamed, and no two records share one.

- Where an ontology names the things a Mech holds, records are keyed by
  its CURIEs, which must sit under the identity root, or be its direct
  children when the Mech requires that. `record_term` repeats the id with
  the ontology's label.
- Where no term exists, or no ontology names the things, a record takes a
  stable identifier from a source that names it uniquely, or a minted id,
  `<slug>:<uuid>`. A record with a minted id can be keyed to an ontology
  term later.
- A record that is no longer current is kept as `DEPRECATED`, not deleted,
  so links to it still resolve.
- A record's identity in other namespaces (the same disease in OMIM, the
  same breed in another database) is a mapping, not a second id: with the
  `sssom` output format, an item in the record's `mappings`, with a SKOS
  predicate, a SEMAPV justification and evidence, published as SSSOM.

**Rationale.** Other Mechs, exports and people link to records by id. An
ontology id ties a record to what the field already calls the thing. A
minted id is the fallback when the field has no name for it.

**Enforced by.** The `identity_prefix`, `identity_root` and
`identity_direct_only` answers; the schema's `IdentityTerm` enum;
`just check-identity`; the duplicate-id check in `just qc`;
`just new-record`, which mints an id when given none.

## 5. Ontologies

**Decision.** A Mech names things with terms from established ontologies,
and never invents an identifier.

- **Descriptors.** A mention of something is a descriptor: `preferred_term`
  (the curator's words, required), `term` (an optional `{id, label}`
  binding), a description and evidence. Each role has its own descriptor
  class, whose `term.id` is bound to a dynamic enum.
- **Checked roots.** A dynamic enum admits the terms under one root of an
  ontology. Every root is checked against the ontology, and against the
  terms it should admit, before it is used.
- **The label is the ontology's.** `term.label` matches the ontology
  exactly. Nuance goes in `preferred_term`.
- **No guessed CURIEs.** An unverified term is worse than none. Leave
  `term` unset, keep `preferred_term`, and open a `CURATION_TODO`
  discussion.
- **The most specific accurate term.** If only a broad term fits, bind it
  and say so. Do not bind a narrower term just because it exists.
- **Static enums for the Mech's own values.** A small closed set the Mech
  defines is a static enum, with each value described. Ontology terms are
  never copied into one.

**Rationale.** A made-up identifier is the agent error most likely to go
unnoticed, because it looks right. Checking every term against its
ontology, from a committed cache, catches it. Shared ontologies also keep
records comparable across Mechs.

**Enforced by.** `ontology_catalog` in `copier.yml`, whose roots are each
checked with `skills/make-mech/scripts/check_terms.py`;
[linkml-term-validator](https://github.com/linkml/linkml-term-validator) in
`just validate`; `conf/oak_config.yaml`, which says which service checks
each prefix; `cache/`.

**How Mechs adapt it.** Each Mech's creators choose its ontologies and roots. When an
ontology cannot serve (its terms lack the parents a dynamic enum needs, or
it lacks the terms), the Mech binds a broader term from another ontology,
keeps the finer detail in `preferred_term`, and records the choice in
`docs/DOMAIN.md`.

## 6. Evidence

**Decision.** Every claim that could be wrong carries evidence: a reference,
and a snippet copied word for word from it.

- **Exact quotes.** The snippet is checked against the fetched source. `...`
  joins two exact spans and `[...]` marks an editorial note; nothing else
  may differ. Paraphrase goes in `explanation`, and a paraphrased snippet
  fails.
- **Fetch before quoting.** Sources are fetched and cached with
  `just fetch-reference`, and quotes are added with `just add-evidence`,
  which checks each quote before writing it. Only the tools write the
  caches, and the caches are committed so the checks run offline.
- **The description is a claim too.** Each fact in it is quoted in
  `description_evidence`, or stated with evidence in a section.
- **No source, no claim.** A gap is recorded as a `KNOWLEDGE_GAP`
  discussion, not filled from memory.
- **Leads are not sources.** A deep-research report, a news lead, a
  database row or a knowledge graph edge points to sources. None is cited.
  Fetch and quote the primary source it points to.

**Rationale.** The exact-quote check is the main defense against an agent
inventing a citation or putting words in a source's mouth. It is cheap
enough to run on every pull request, and it lets any reader check any
claim.

**Enforced by.** `EvidenceItem` in the schema, whose `reference` and
`snippet` slots carry the markers
[linkml-reference-validator](https://github.com/linkml/linkml-reference-validator)
looks for (an evidence class without them is never checked);
`just validate`; checks in `validate.py` that a snippet is more than the
source's title and that a cited title matches the source;
`references_cache/`.

**How Mechs adapt it.** The kinds of evidence, the reference types and how
evidence is graded belong to each Mech's data model. A Mech about livestock
breeds may cite breed standards and field studies; one about software may
quote files in a repository at a pinned commit; one about disease cites
papers by PMID.

## 7. The data model

**Decision.** A Mech's data model is a [LinkML](https://linkml.io/) schema
in its repository, and the schema is closed: a field it does not define is
an error. Exchange standards are applied in the exports, not in the
curation model.

- **Closed.** When something real has nowhere to go, the schema gets a slot
  (with the Mech's `extend-schema` skill) and records migrate. It does not
  go in `notes`.
- **One schema, many formats.** `just export` writes the records as JSON,
  RDF, SQL, tables and knowledge graph files from the one schema, and reads
  each back.
- **Knowledge graph mapping in the exports.** When a Mech exports a
  knowledge graph (KGX), `conf/kgx.yaml` maps its sections to categories
  and predicates. Biolink is the usual choice in biology and biomedicine,
  the fields it was built for. A Mech in another field sets
  `biolink: false` and names its own categories and predicates, or leaves
  the knowledge graph export out.
- **Every prefix declared.** Each CURIE prefix a record can carry has its
  full URI in the schema, so the RDF exports can expand it.

**Rationale.** LinkML gives YAML that people and agents can edit, ontology
binding through dynamic enums, generated documentation, and many output
formats from one source. A closed schema gives every piece of meaning a
named place that a check can see. Keeping the curation model apart from
exchange formats lets each change without forcing changes on the other.

**Enforced by.** `src/<slug>/schema/<slug>.yaml`; `just validate`;
`conf/export.yaml` and `conf/kgx.yaml`; `just export`, which fails on a
prefix with no URI.

**How Mechs adapt it.** The schema belongs to each Mech, designed with
`design-mech-schema` from its `docs/DOMAIN.md`. The scaffold's sections are
a start, to be cut, renamed and extended. A Mech may store identifiers from
an exchange standard as data when those are what its records describe, and
may add structures its field needs, such as places for a map.

## 8. Status and review

**Decision.** A record is `DRAFT`, then `PROPOSED` when complete and valid,
then `REVIEWED` when a person accepts it. An agent takes a record no
further than `PROPOSED`. `DEPRECATED` keeps a record for provenance. The
pull request is the review gate: nothing reaches `main` without a person's
approval.

**Rationale.** Agents do most of the work, so the one step they never take
is the one that says a person has looked. A reader can always tell reviewed
records from proposed ones.

**Enforced by.** `CurationStatusEnum`; a check that a `REVIEWED` record has
a review event in its history by a person, not marked as assisted by a
model; the pull request, and the `review` workflow where turned on.

## 9. History

**Decision.** Every change appends a `curation_history` event to the record:
who (a person or an agent), when, what and why. Every curation session also
adds one file under `history/`, which is never edited afterwards.

**Rationale.** A record's events say what happened to it. The session files
say what a session did across records. One new file per session means
parallel sessions never conflict over a shared log.

**Enforced by.** `history.yaml` (§10); `just new-history`; `just qc`.

## 10. Shared modules

**Decision.** Classes every Mech needs in the same form come from two shared
schema modules, copied byte for byte into each Mech:

- `mech_shared.yaml`: `Discussion` (open questions, knowledge gaps,
  controversies, to-dos), `Dataset`, `CrossCorpusLink` and
  `SupportingReference`;
- `history.yaml`: curation history.

Nobody edits them inside a Mech. They change upstream in culturebotai-claw, and
reach a Mech through mechmaker or, in a Fleet, through its Coordinator.

**Rationale.** Tools that read many Mechs (fleet audits, MechRegistry, a
Fleet's checks) rely on these classes meaning the same thing everywhere. A
copy that drifts breaks that without warning, so the copies are checked by
hash.

**Enforced by.** The hash checks in mechmaker's tests and in each Mech's
`tests/test_schema.py`; in a Fleet, `fleet/pin.yaml` and
`just check-fleet`. See [Fleets](fleets.md).

## 11. Links between Mechs

**Decision.** A link from a record in one Mech to a record in another is a
subclass of `CrossCorpusLink`: the target Mech, the target record's id
exactly as written there, a relation from an enum, a basis, and the commit
of the target that was checked. A shared ontology term is a lead for a link,
not a link.

**Rationale.** Mechs are separate repositories that change independently.
Naming the commit that was checked makes a link verifiable later.

**Enforced by.** `CrossCorpusLink` in `mech_shared.yaml`; in a Fleet, the
relationships in the Coordinator's `fleet.yaml`, and its audit, which
checks that each link's target exists.

**How Mechs adapt it.** A Mech outside a Fleet adds link classes when it
needs them; a Fleet member gets them from its `fleet_links` answer. When
many records repeat the same thing, such as one event touching many
places, that thing may be better kept in a Mech of its own and linked to.

## 12. Agents and automation

**Decision.** Agents do most of the curation. A person can start one in a
local session, and GitHub workflows start them in the repository itself:
on a schedule, on a new issue or pull request, or when someone with write
access asks. These workflows are a large part of what makes a Mech work.
They keep it checked, keep its work moving between sessions, and put each
change in front of a person in a form that is quick to review.

Every agent, local or in a workflow, reads the Mech's `CLAUDE.md` (or
`AGENTS.md`) and uses the Mech's skills, so it curates by the same rules a
person would.

**The parts.** Each Mech carries a catalog of its workflows,
`docs/WORKFLOWS.md`; [Workflows](workflows.md) lists them all. They fall
into three groups:

| Group | What they do | Examples |
|---|---|---|
| Checks, no model | Run the checks and publish the site. `qc` is always on and is the required check on every pull request | `qc`, the weekly `sweep` against live services, `docs`, `news-watch` |
| Agents that read and report | Read a pull request, an issue or new papers, and return a structured result. A step with no model posts it | `review`, `triage`, `dedupe`, `literature-scan`, `pr-shepherd`, `post-review` |
| Agents that write | Curate: open branches and pull requests that change records | `curation-scanner`, `compliance`, and `claude`, which answers `@claude` from people with write access |

**The loop.** A typical change goes:

1. Work is found. A person opens an issue, `literature-scan` files new papers
   that match records, `news-watch` files new stories, or `just compliance`
   ranks the least complete records.
2. Work is accepted. `triage` labels issues. An issue becomes curation work
   only when it has the `curation` label, which goes on automatically only
   when the author can write to the repository; otherwise a person adds it
   after reading the issue.
3. Work is done. `curation-scanner` takes accepted issues and advances them;
   `compliance` improves the least complete records. Each opens a pull
   request with records at `PROPOSED` at most, and history for what it did.
4. Work is checked. `qc` runs every check on the pull request, and `review`
   reviews it with the `review-record` skill.
5. A person decides. They read the change and the review, and merge it or
   not. `post-review` turns their review comments into suggestions and
   replies; `pr-shepherd` names the most stuck pull request and what would
   unstick it.

**The rules.**

- **No agent merges.** Merging is for people. This is what makes the pull
  request the review gate (§8).
- **An agent that reads text anyone can write gets no write permission.**
  Issues, comments, pull request bodies, abstracts and news stories can
  carry instructions. Agents that read them return structured output, and a
  step with no model checks and publishes it.
- **Agents that write never read the public thread directly.** A step with
  no model gives them the issue's title, body, and the comments of people
  with write access and of the Mech's own Apps.
- **Separate identities.** The agent App pushes, so its pull requests get
  CI. A separate reviewer App approves, so the writer never approves its
  own work.
- **Instructions come from the default branch.** Prompts and helper scripts
  load from `main`, so a pull request cannot change the instructions it is
  reviewed under.
- **Explicit tools.** Each agent has a fixed list of tools. No workflow
  runs with permissions bypassed.
- **Failures are loud.** Every agent run ends with a check that fails the
  job with its cause (out of turns, out of credit, a usage limit), rather
  than a silent pass.
- **Opt-in, and pinned.** Every agent workflow is off until chosen. Each
  pins the exact version of the action it runs. Scheduled agents run only
  when started by hand until `agent_schedules` is turned on.

**Rationale.** Agents curate quickly, and the workflows let them do it
continuously, with every change arriving as a checked, reviewed pull
request. People spend their time on the decision only they can make:
whether a change is right. Text from the public can carry instructions, so
nothing that reads it can act on it with the repository's credentials.

**Enforced by.** The workflow templates under `template/.github/`, and the
prompts in `.github/prompts/`; the `workflows` and `agent_schedules`
answers; `.github/agent-config.yaml` for models and turn budgets;
mechmaker's tests, which check that the pinned action and credential lines
match across workflows, and `actionlint`.

**How Mechs adapt it.** A Mech's creators choose which workflows to turn on,
and when to turn on schedules. They edit the prompts in `.github/prompts/`
to fit the field, set models and turn budgets, tune what
`literature-scan` searches for, and may trace every run with Langfuse. A
Mech at large scale may add workflows of its own. One that lets an agent
merge approved pull requests removes a person from the loop, and is a
policy its creators must choose deliberately.

## 13. Checks

**Decision.** `just qc` runs every check that needs no network, and is what
CI requires. A fresh Mech passes it. `just qc-full` adds live checks of
every term and quote. Answers from ontology services and copies of cited
sources are committed, so the offline checks give the same result
everywhere.

**Rationale.** A check that passes on one machine and fails on another, or
fails because a service is down, teaches people to ignore it.

**Enforced by.** The `justfile`; `cache/` and `references_cache/`;
mechmaker's `just test-generated`, which generates sample Mechs and runs
their `just qc`.

## 14. Optional parts

**Decision.** Causal graphs, the record browser, maps, deep research, news
leads, structured ingests, agent workflows, output formats and database
loads are Copier answers. A Mech's creators turn on what its field needs,
and its `.copier-answers.yml` records the choice.

**Rationale.** Each part has a cost: files to read, checks to keep passing,
and for some, money per run. Parts a Mech does not use make it harder to
curate and review.

**How Mechs adapt it.** A Mech about how diseases work may center on causal
graphs, while one about breeds has no use for them. A Mech about incidents
that local news covers, and papers may never report, turns on news leads.

## What each Mech defines, and what every Mech keeps

| Each Mech defines | Every Mech keeps |
|---|---|
| What one record is, its granularity, and its filename convention (§3) | One record, one file, unique filenames (§3) |
| Its identity scheme: an ontology root, a source's ids, or minted ids (§4) | Ids that never change and never repeat (§4) |
| Its ontologies and roots (§5) | Checked terms, ontology labels, no guessed CURIEs (§5) |
| Its kinds of evidence and reference types (§6) | Exact, checked quotes; leads are never sources (§6) |
| Its sections, slots and enums (§7) | A closed LinkML schema (§7) |
| Its scope and curation priorities (§1) | Agents stop at `PROPOSED`; people review (§8) |
| Its optional parts (§14) | History on every change (§9) |
| Whether and how it links to other Mechs (§11) | The shared modules, unedited (§10) |
| Its workflows, prompts, models and schedules (§12) | No agent merges; agents that read public text cannot write (§12) |

When a Mech's field needs something in the right-hand column to change,
record the reason in that Mech's `docs/DOMAIN.md` and open an issue on
mechmaker. The standard may need to change with it.

The [example Mechs](https://github.com/monarch-initiative/mechmaker/tree/main/example)
show these decisions applied to three different fields, each with its own
`docs/DOMAIN.md`.
