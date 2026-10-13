---
name: search-mechregistry
description: >-
  Search MechRegistry (https://monarch-initiative.github.io/mechregistry/)
  for existing Mechs that a planned Mech would duplicate or overlap, by
  record type, ontologies, domains and data sources; read how registered
  Mechs link to each other; and look into a Mech's repository for what a
  new Mech can reuse: its conversion and ingest scripts, its records at a
  pinned commit, its released exports. Use while surveying a domain or a
  knowledge base to convert, when asked whether a Mech already exists for
  something, or when a new Mech should link to, draw on or hand off to an
  existing one.
---

# Search MechRegistry

MechRegistry lists published Mechs. Each entry says what one record is
(`record_type`), how many records there are, how mature the Mech is, its
ontologies, domains and data sources, its products (records, schema,
browser, exports), its license, and its `cross_references`: how it relates
to other Mechs (it `consumes` their records, `hands_off_to` them for a
class of entity, `shares_vocabulary_with` them, and so on).

A planned Mech may duplicate one of these, overlap it, or need it. Find
that before generating anything. Many registered Mechs were not made with
mechmaker: DisMech came from linkml-project-copier, and the CultureBotAI
Mechs carry no Copier answers at all. `repo` says which. The `register-mech` skill adds
new ones.

## The script

A script comes with this skill, in the `scripts/` folder beside this file;
`<scripts>` stands for that folder's path. It needs only Python 3, and
runs where it is.

```bash
python3 <scripts>/mech_registry.py search culture medium
python3 <scripts>/mech_registry.py search --ontology CHEBI --domain microbiology
python3 <scripts>/mech_registry.py overlap --ontology GO --ontology ECO --domain genomics \
    --source GOA --words "gene annotation"
python3 <scripts>/mech_registry.py show culturemech
python3 <scripts>/mech_registry.py repo culturemech
```

The registry is one file. The script downloads it on first use and keeps it
for a day (`--refresh` takes a new one). `search` matches every word against
a Mech's id, name, record type, description, ontologies, domains, data
sources and collection; `--any` ranks by how many match. `--json` gives
output to read in a program. `repo` asks GitHub, seven requests a Mech and
more for one with many packages; set `GITHUB_TOKEN`
(`export GITHUB_TOKEN=$(gh auth token)`) to lift GitHub's limit of 60 an
hour. Exit 1 means nothing matched; exit 2 means
the registry or GitHub could not be reached.

## 1. Is there already a Mech for this?

Run `overlap` with what the survey has so far: the record entity in words,
the ontologies, the domains, the main sources. It lists every Mech sharing
any of them, most first, and says what each shares. Then `search` the
record entity's words and their synonyms. Read `show` for each close hit.

Sort what you find:

- **The same record entity.** Another Mech already keeps one record per
  this thing. Say so first in the brief and tell the person before going
  on. Their choices: contribute to that Mech instead (its repository and
  contacts are in `show`); narrow the new Mech to what the other leaves
  out, and hand the rest to it; or go ahead with a reason the brief states.
  This is the person's decision.
- **A neighbor.** A different entity, but records will mention the other
  Mech's records (a community names the medium it grew in), or the two
  share ontologies or sources. Plan a link (section 3) and a
  cross-reference.
- **A pattern to follow.** A Mech in a similar domain whose schema,
  sections or curation practice fit. Read its schema (`show` gives the
  URL) before designing the new one.

`show` also lists the links each Mech makes and receives. A Mech that many
others `consume` or `hand_off_to` is the domain's hub; a new Mech near it
probably links to it too.

## 2. Reuse its ingest

`repo <id>` reads the Mech's repository at its current commit and lists the
scripts whose names say they bring data in (`convert_`, `fetch_`,
`import_`, `ingest`, `parse` ...; the template's own modules, such as
`load.py`, are left out), its records folder with sample files,
whether mechmaker made it, and its latest release's files.

- **A mechmaker Mech** keeps its conversions in `scripts/convert_<source>.py`,
  each built on `src/<slug>/convert.py`. The new Mech has the same helper,
  so porting one is mostly changing the import and the field mapping. The
  `convert-knowledge-base` skill explains the helper.
- **Another Mech** has its own layout: read its README and the script.
  Often the useful part is a fetcher for a source, or a mapping table
  (source strings to ontology terms) that took real curation.

Before copying code, read the license: `show` gives the code license when
the registry has one, `repo` the repository's. `NOASSERTION` means GitHub
could not tell; read the `LICENSE` file. Copy into the new Mech's
`scripts/`, with a first comment naming the source repository, path and
commit. Credit it in the registry entry: `adopts_practice_of` for a method,
a `data_sources` entry with `prov:used` for a mapping table.

## 3. Work with its records

A new Mech can use another's curated records three ways. Pin each to a
commit (`repo` prints it) or a release, never to `main`.

**Link to them.** A record names another Mech's record, the way a
community names the medium it grew in. Every Mech's shared schema module
has `CrossCorpusLink` for this: `corpus` (the target Mech's name),
`identifier` (its record id, verbatim), `relation`, `basis` (how the link
was established) and `source_version` (the commit checked). Add a subclass
with the Mech's own `extend-schema` skill, with an enum of relations, and
require `source_version`. Check each target id exists in the target's
records at that commit before writing it. In the registry entry, the
relation is `consumes`. If both Mechs are made with mechmaker and their
maintainers agree, a Fleet declares such links and checks every one: see
`make-fleet`, and its Coordinator's `onboard-mech` for an existing Mech.

**Seed from them.** The other Mech's records can seed the new one's, as a
knowledge base to convert (`convert-knowledge-base`). Read them from the
pinned commit, or from a release's export (`json`, `jsonl`) when it has
one. A record's evidence items already quote their sources: carry the
reference and snippet over, and the new Mech's validator checks them again.
A fact the other record states without evidence is cited to that record,
at its pinned raw URL, like any other knowledge base. Read the data license
first: CC BY needs attribution, and the registry's `license` says which.

**Share vocabulary.** Two Mechs grounded in the same ontologies, under the
same roots, can join records on those terms without linking. Use the same
roots where the domains meet, and say `shares_vocabulary_with`. Copy
another Mech's enums only with a pin, and say where they came from.

## 4. Record what you decided

Each neighbor goes in the brief's Neighbors section, with what it records,
the boundary, and the relation. These become the registry entry's
`cross_references`, which `register-mech` fills in. A link in one
direction is worth telling the other Mech about: draft an issue for its
repository proposing the reverse cross-reference. Opening it is public;
ask the person first.

## What the registry is not

- **Not complete.** It lists Mechs whose makers registered them. Others
  exist; a search of GitHub may find them. Absence means unregistered.
- **Not current to the day.** Counts are dated (`record_count_date`); the
  repository is the truth.
- **Not evidence.** A Mech's records carry their own evidence. Cite that,
  not the registry.

KG-Registry (`search-kg-registry`) lists the knowledge graphs, data sources
and ingests that are not Mechs. The survey reads both.
