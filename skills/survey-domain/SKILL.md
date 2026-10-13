---
name: survey-domain
description: >-
  Survey a knowledge domain before building a Mech for it: define what one
  record is, how records are keyed, which ontologies ground them, which
  sources can feed them, and which existing Mechs, knowledge graphs and
  ingests overlap. Produces a domain brief that drives the mechmaker Copier
  answers and docs/DOMAIN.md. Use as the first step of make-mech, or alone
  when asked whether a domain suits a Mech.
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
  entity one to one. None may fit. Then search the Bioregistry for a
  namespace that already mints ids for the entity (a database's own ids,
  such as culture collection numbers); the `search-bioregistry` skill has
  the script. If none fits either, records mint their own ids.
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
checked with `check_terms.py --adapter`.

Never name an ontology from memory. Find candidates for each kind of thing
by searching where ontologies are listed, and search more than one:

- **OBO Foundry** (https://obofoundry.org/). Its registry is one file,
  https://obofoundry.org/registry/ontologies.jsonld, with each ontology's
  `title`, `description`, `domain`, `activity_status` and `dependencies`.
  Prefer an active OBO Foundry ontology where one fits: these share
  relations and import each other's terms.
- **OLS** (https://www.ebi.ac.uk/ols4/). Search terms across every
  ontology it serves:
  `https://www.ebi.ac.uk/ols4/api/search?q=<words>&fieldList=obo_id,label,ontology_name`.
  Search with `&type=ontology` for ontologies whose title or description
  match. Many ontologies import others' terms, so a term turns up under
  several `ontology_name`s; its CURIE prefix names the ontology that
  defines it.
- **BioPortal** (https://bioportal.bioontology.org/) holds many ontologies
  outside OBO and OLS, clinical terminologies among them. Its API needs a
  key (`BIOPORTAL_API_KEY`, free with an account). Send it in a header, so
  it never appears in a URL that an error or a log could print:

  ```bash
  curl -s -H "Authorization: apikey token=$BIOPORTAL_API_KEY" \
      "https://data.bioontology.org/search?q=goat%20breed&pagesize=10"
  ```

  Each hit's `links.ontology` ends in the ontology's acronym. Without a
  key, ask the person to search the site, or skip BioPortal and say so in
  the brief.
- **The Bioregistry** (`search-bioregistry`) and **KG-Registry** with
  `--category Ontology` (`search-kg-registry`) find ontologies by subject.
  The Bioregistry's `show` gives each one's OBO Foundry, OLS and BioPortal
  ids, where it has them.

Note gaps: kinds of thing no ontology covers well. Those become
`preferred_term` text with open `CURATION_TODO` discussions, or a case for a
new ontology.

## 4. Sources

List what can feed curation. For each: what it gives, license (read the
terms; write UNKNOWN if not found), access (API, bulk, pages), whether its
identifiers are CURIEs the Mech can use, and a size measured on a sample.

- Search KG-Registry for the domain's data sources and aggregators, and
  read the sources of the knowledge graphs nearest the domain: each is a
  candidate row. For a source the Mech will use, `used-by` names the
  graphs that already ingest it; an ingest's repository shows the source's
  format and identifiers. The `search-kg-registry` skill has the script.
- Literature is always a source. Write a PubMed query that finds the core
  papers and report its hit count.
- Existing databases and knowledge bases can seed records but never replace
  evidence. A seeded claim still needs a quoted source.
- News is a source when records are about events: incidents, outbreaks,
  spills, closures. Local news reports many that papers never do. Try one
  dated search for a known event (a Google News search with `after:` and
  `before:` dates) and say whether the stories it finds are archived and
  quotable. If they are, set `news_leads: true` in the draft answers; the
  `ingest-news` skill configures it.

These rows become `curation/source_queue.tsv` in the new Mech.

Say whether deep research would help. It helps when a record's subject has
a large literature a curator cannot read in one sitting; it adds little
when the facts come from one database. Put the answer in the brief, as
`deep_research: true` or `false`.

## 5. Neighbors

Search MechRegistry with the `search-mechregistry` skill. Its `overlap`
command takes what this survey has found (the record entity in words, the
ontologies, the domains, the main sources) and ranks every registered Mech
by what it shares; `search` finds the entity's words and synonyms; `show`
gives each close one in full, with the Mechs it links to and from. For
each Mech that overlaps:

- what it records, and where the boundary between it and this Mech lies;
- whether this Mech should link to its records (`consumes`), hand off to it
  (`hands_off_to`), or share its vocabulary (`shares_vocabulary_with`);
- what this Mech can reuse: its conversion or ingest scripts for a source
  this Mech shares, or its curated records as links, seeds or vocabulary.
  `repo` lists what its repository holds.

If an existing Mech already records this entity, say so first, and tell
the person before going on. Contributing to it, or narrowing this Mech to
what it leaves out, may be better than starting a new one. That choice is
theirs.

Mechs are not the only neighbors. Search KG-Registry (`search-kg-registry`)
for knowledge graphs, data sources, data models and ingests that hold the
same entity or the same domain: by the entity's words, by its domain, and
by the Mech's main sources (`used-by`). For each close one, say what it
holds, whether the Mech should use its identifiers, link to it, align its
schema with it (a data model), or curate what it lacks, and cite its
KG-Registry page.

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
