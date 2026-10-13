---
name: search-kg-registry
description: >-
  Search KG-Registry (https://kghub.org/kg-registry/), the catalog of
  biomedical and environmental knowledge graphs, data sources, ontologies,
  aggregators and data models, for what already covers a Mech's domain:
  resources like the Mech in name, domain or sources; the data sources
  available for a domain; what a knowledge graph is built from; and which
  graphs already ingest a source. Use while surveying a domain or a
  knowledge base to convert, when asked whether something like a planned
  Mech exists, or what data sources, ontologies or models a domain has.
---

# Search KG-Registry

KG-Registry lists about 1,100 resources, each with a category
(`KnowledgeGraph`, `DataSource`, `Ontology`, `Aggregator`, `DataModel`,
`Resource`), domains, license, homepage, repository, and its products: the
graphs, files and interfaces it publishes. Each product names its sources,
so the registry also says what each graph is built from and, read the
other way, which graphs take a given source.

A new Mech may overlap with what is listed here: a graph about the same
entity, a database the Mech means to curate from, an ingest that already
parses that database, a data model for the same records. Finding these
first saves rebuilding them, and tells the Mech what to link to.

MechRegistry is a different list: Mechs only. `survey-domain` reads both.

## The script

A script comes with this skill, in the `scripts/` folder beside this file;
`<scripts>` stands for that folder's path. It needs only Python 3, and
runs where it is.

```bash
python3 <scripts>/kg_registry.py search microbe traits
python3 <scripts>/kg_registry.py search "rare disease" --category KnowledgeGraph
python3 <scripts>/kg_registry.py search --domain "water resources" --category DataSource
python3 <scripts>/kg_registry.py show kg-microbe bacdive
python3 <scripts>/kg_registry.py used-by bacdive
python3 <scripts>/kg_registry.py domains
```

The registry is one file. The script downloads it on first use and keeps it
for a week (`--refresh` takes a new one). Every word given to `search` must
match, at the start of a word in the id, name, synonyms, domains or
description; `--any` ranks by how many match instead. `--json` gives output
to read in a program. Exit 1 means nothing matched; exit 2 means the
registry could not be downloaded.

## Questions it answers

**Is there already something like this Mech?** Search the record entity's
words, then its domain. Try the plural and the general word, and phrases
the field uses (`"growth medium"`, `media`). Read `show` for each close hit.
A knowledge graph that already holds the Mech's entities is a neighbor:
the Mech may consume its identifiers, hand off to it, or curate what it
lacks. Say which.

**What sources does the domain have?** `domains` lists the domain words;
`search --domain <word> --category DataSource` lists the sources under one.
Add `Aggregator` for portals that gather many. Each is a candidate row for
the survey's source table.

**What is a graph built from?** `show <id>` lists its sources. A graph
close to the Mech's domain has already found that domain's sources; its
list is a checklist for the Mech's own.

**Who already ingests a source?** `used-by <id>` lists the resources whose
products take it as a source. An ingest that parses the source (its
repository is in `show`) shows its format, its identifiers, and the
mappings it needed. The Monarch graph (`kg-monarch`) and the KG-Hub
graphs are listed with their sources.

**Is there a data model for these records?** `search --category DataModel`,
and `--category Ontology` with the entity's words. A model already used
for the same records (Biolink, MIxS, a LinkML schema) is one to align the
Mech's schema with, or to borrow slot names from.

## What a listing is not

- **Not evidence.** A listing says a resource exists and what it claims to
  hold. A Mech's claims still quote their sources.
- **Not the last word on license or access.** The registry's license field
  is a lead; read the resource's own terms before the brief says what the
  license is. Its warnings (shown by `show`) often say why.
- **Not complete.** A domain missing here may still have sources. Absence
  means not registered, not nonexistent.
- **Not always current.** `show` prints a status when a resource is
  inactive, orphaned or unresponsive, and `use instead` when another
  replaces it.

A resource's KG-Registry id is often its Bioregistry prefix (`mondo`,
`chebi`, `envo`). For namespaces, identifier patterns and CURIEs, use the
`search-bioregistry` skill.

## In the brief

Cite each resource the survey uses by its KG-Registry page, which `show`
prints. A neighbor goes under Neighbors with what it holds and where its
boundary with the Mech lies; a source goes in the source table with what
it gives, its license as read from its own terms, and its access.
