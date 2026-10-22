---
name: search-mappings
description: >-
  Find and read identifier mappings in SSSOM (https://mapping-commons.github.io/sssom/),
  the Simple Standard for Sharing Ontological Mappings: the mapping sets
  that already link a Mech's identifiers to others (an ontology's own
  cross-references, Mondo's, Bioregistry's, the sets KG-Registry lists),
  what each maps to what, and the rows that name an entity. Also: when a
  new Mech should publish its own mappings as SSSOM (the `sssom` output
  format), and how sssom-py validates, converts and merges sets. Use while
  surveying a domain or a knowledge base to convert, when records will be
  keyed by or linked to identifiers in other databases, or when asked about
  SSSOM, crosswalks, cross-references or identifier mapping.
---

# Search mappings

A mapping says that an entity in one namespace is the same as, close to,
broader or narrower than, or related to an entity in another: `MONDO:0007739`
(Huntington disease) is an exact match of `OMIM:143100`. Records are
keyed by one namespace; users join on many. Mappings let them.

[SSSOM](https://mapping-commons.github.io/sssom/) is the standard way to
publish them: a TSV file, one row per mapping, with the set's metadata in
`#` lines above it.

| Column | What it holds |
|---|---|
| `subject_id`, `subject_label` | One entity, as a CURIE |
| `predicate_id` | How they relate. SSSOM recommends the [SKOS](https://www.w3.org/TR/skos-reference/#mapping) relations: `skos:exactMatch`, `skos:closeMatch`, `skos:broadMatch`, `skos:narrowMatch`, `skos:relatedMatch` |
| `predicate_modifier` | `Not`: the mapping is stated not to hold |
| `object_id`, `object_label` | The other entity |
| `mapping_justification` | How it was found, from [SEMAPV](https://mapping-commons.github.io/semantic-mapping-vocabulary/): `semapv:ManualMappingCuration`, `semapv:LexicalMatching`, `semapv:MappingChaining`, ... |
| `confidence` | 0 to 1, optional |

The metadata holds the `curie_map` (every prefix the rows use, with its
URI), a `mapping_set_id` and a `license`, which SSSOM requires, and
usually a version and title. SEMAPV names the processes; SKOS names the
relations.

## The scripts

Two scripts, each needing only Python 3. `<scripts>` is the `scripts/`
folder beside this file; `<kg-scripts>` is the `search-kg-registry`
skill's.

```bash
# Mapping sets KG-Registry lists, touching every resource named (KG-Registry ids)
python3 <kg-scripts>/kg_registry.py mappings mondo --sssom
python3 <kg-scripts>/kg_registry.py mappings chebi --sssom --search metabolite

# One set: its metadata, and what it maps to what, with counts
python3 <scripts>/sssom_sets.py summary <file-or-url>
# The rows naming a CURIE, or whose labels hold every word; --to keeps one target prefix
python3 <scripts>/sssom_sets.py find <file-or-url> MONDO:0007739 --to OMIM
python3 <scripts>/sssom_sets.py find <file-or-url> "huntington disease"
```

`sssom_sets.py` reads a file or a URL, gzipped or not, and keeps a
downloaded set for a week (`--refresh` takes a new one). `--json` gives
output for a program. Exit 1 means nothing matched; exit 2, the set could
not be read.

## Where mappings already are

1. **KG-Registry.** `kg_registry.py mappings <id>` lists the mapping
   products listed on a resource's page or naming it as a source: about
   110, 43 of them SSSOM (checked 2026-10-22). Among them: Mondo's
   (`mondo.sssom`, Mondo to OMIM, Orphanet, DOID, NCIT, MeSH, ICD and
   more), Bioregistry's (prefixes across registries), and one per source
   from the biopragmatics database ingests (`obo-db-ingest.*`). Products
   that are not SSSOM (a `mim2gene` table, a cross-reference file) still
   map identifiers; drop `--sssom` to see them.
2. **The ontology itself.** An ontology lists cross-references on its
   terms. OAK gives them as SSSOM:

   ```bash
   runoak -i sqlite:obo:doid mappings DOID:12858 -O sssom --autolabel
   ```

   The first run downloads the ontology (Disease Ontology: 22 MB). An
   `ols:` adapter asks EBI's OxO for mappings instead, which may not
   answer. Most come back as `oio:hasDbXref`: the two are linked, but the
   relation is not stated. Read the definitions before calling one exact.
3. **Bioregistry**, for prefixes rather than entities: which prefix other
   registries use for a namespace. The `search-bioregistry` skill covers it.
4. **The source's own downloads.** Many databases publish a cross-reference
   table (`kg_registry.py show <id>` lists a resource's products).

A set with `semapv:UnspecifiedMatching` throughout, like Mondo's, says
nothing about how each mapping was made; its maintainers' curation is the
warrant. Read a set's license before a Mech reuses its rows.

## What the survey decides

**Does the Mech need its own mappings?** Mostly, no:

- **Records keyed by an ontology term** (a Mondo disease, an ENVO habitat)
  inherit that ontology's mappings. Users get them from the ontology; the
  Mech need not copy them. The brief names the set.
- **Records with minted ids**, or keyed by a namespace few others use,
  need mappings for anyone to join them to other data. Such a Mech
  publishes its own: the `sssom` output format.
- **A Mech whose purpose is reconciliation** (which entries in two
  databases are the same thing) is a mapping Mech: `sssom` on, and its
  records' `mappings` are the main curation.
- **A knowledge base to convert** with columns of other ids (an OMIM
  column, a Wikidata column) holds mappings already. Each column becomes
  mappings on the record, with the predicate the column means, and the
  conversion keeps the column's provenance as evidence.

**Which namespaces?** For each, the prefix and its URI from Bioregistry,
and whether an existing set already covers it.

## What `sssom` gives a Mech

With `sssom` in `output_formats`, the schema gets a `mappings` section on
the record (the `Mapping` class: `predicate_id`, `predicate_modifier`,
`object_id`, `object_label`, `mapping_justification`, `confidence`,
`evidence`, `notes`), and `just export` writes every record's mappings as
`<slug>-mappings.sssom.tsv`, checked with sssom-py. The Mech's own
`curate-mappings` skill says how to curate them. In short:

- The record is the subject; every mapping needs evidence, like any claim.
- `predicate_id` is one of the five SKOS relations; `predicate_modifier:
  Not` states a mapping that does not hold.
- `mapping_justification` is one of the nine SEMAPV processes that the
  released SSSOM schema (sssom-py 0.4) accepts. An agent's mapping is
  `semapv:UnspecifiedMatching`: SEMAPV now has
  `semapv:AgentBasedMatching` and `semapv:LLMBasedMatching`, but sssom-py
  0.4.17 rejects both (checked 2026-10-22).
- Each `object_id` prefix is declared in the schema's `prefixes` with its
  full URI. The export fails on one that is not.

To add it to a Mech made without it: bring the Mech up to a mechmaker
that has it (the `sync-mech` skill), then add `sssom` to its
`output_formats` answer (`copier update --vcs-ref=:current: --data
'output_formats=[...]'`), which adds the schema's section, the skill and
the dependency. The Output formats page of mechmaker's docs says what to
add by hand instead.

## sssom-py

[sssom-py](https://github.com/mapping-commons/sssom-py) is the reference
library and command line (`pip install sssom`, or `uvx --from sssom sssom`
to run it once). A Mech with `sssom` on has it installed.

```bash
sssom validate my.sssom.tsv                    # against the SSSOM schema
sssom convert my.sssom.tsv -O owl -o my.owl    # also json, rdf, ttl, fhir_json, ontoportal_json
sssom parse xrefs.tsv -I tsv -m meta.yml       # other formats (obographs-json, alignment-api-xml) to SSSOM
sssom merge a.sssom.tsv b.sssom.tsv -o ab.sssom.tsv
sssom diff a.sssom.tsv b.sssom.tsv
sssom dosql -Q "SELECT * FROM df WHERE object_id LIKE 'OMIM:%'" mondo.sssom.tsv
```

`sssom_sets.py` is for a quick look without installing anything;
sssom-py is for checking, converting and combining.

## In the brief

A **Mappings** section: each existing set the Mech can lean on (its
KG-Registry id or URL, maker, license, and what it maps to what, from
`summary`); the namespaces the Mech's users will want to join on, each with
its Bioregistry prefix and URI; and whether the Mech turns `sssom` on, with
the reason. A listing is a lead, not evidence: a mapping the Mech states
still quotes its source.
