---
name: search-bioregistry
description: >-
  Look up namespaces in the Bioregistry (https://bioregistry.io/): find the
  prefix and resource that identify a kind of thing, say what an unfamiliar
  prefix is and who maintains it, check that a CURIE is well formed and
  write it in standard form, turn an IRI into a CURIE, and find a prefix's
  URI expansion, license, downloads and ids in other registries. Use while
  surveying a domain (choosing identifiers and ontologies), converting a
  knowledge base whose data carry prefixes or IRIs, or adding a prefix to a
  Mech's schema.
---

# Look up namespaces in the Bioregistry

The Bioregistry lists about 2,900 prefixes. Each is a namespace: the
resource behind it, the pattern its local ids follow, the URI a CURIE
expands to, its license, its downloads, its ids in other registries (OBO
Foundry, OLS, BioPortal, identifiers.org, FAIRsharing, Wikidata), and how
it relates to other prefixes: part of, provides for, depends on, appears in.

## The script

A script comes with this skill, in the `scripts/` folder beside this file;
`<scripts>` stands for that folder's path. It needs only Python 3, and
runs where it is.

```bash
python3 <scripts>/bioregistry.py search microbial strain --any
python3 <scripts>/bioregistry.py search breed
python3 <scripts>/bioregistry.py show mondo NCBITaxon EC
python3 <scripts>/bioregistry.py curie MONDO:0005015 chebi:15377 PMID:12345
python3 <scripts>/bioregistry.py iri http://purl.obolibrary.org/obo/ENVO_00002001
```

The registry is one file. The script downloads it on first use and keeps it
for a week (`--refresh` takes a new one). Every word given to `search` must
match, at the start of a word in the prefix, a synonym, the name, the
keywords, the description, or an id in another registry; `--any` ranks by
how many match. Deprecated prefixes are left out unless `--deprecated`.
`--json` gives output to read in a program. Exit 1 means nothing matched,
a prefix is unknown or an id breaks its pattern; exit 2 means the registry
could not be downloaded.

## Questions it answers

**What identifies this kind of thing?** Before a survey picks how records
are keyed or what a field binds to, search the kind of thing (`strain`,
`breed`, `medium`). Each hit is a namespace someone already
mints ids in. `show` says whether it is an ontology (an `obofoundry` or
`ols` id, an OWL download) or a database's own ids. An ontology goes on to
`check_terms.py` in the make-mech skill's `scripts/`; the `ols` id is the
ontology id that script takes.

**What is this prefix?** A source's data, a knowledge base to convert, or
another Mech may use prefixes you do not know. `show` takes a prefix in any
case or as any synonym (`taxid`, `EC number`) and names the resource, its
homepage and license, and what it is part of.

**Is this CURIE well formed?** `curie` checks each local id against its
prefix's pattern and prints the standard form and its URI. A pass means
the id has the right shape, not that the term exists: for ontology terms,
`check_terms.py label` checks that. A fail is worth reading before the id
goes into a record.

**What CURIE is this IRI?** `iri` finds the prefix whose URI format fits
best, across the prefix's own format, its RDF form, its providers,
identifiers.org and bioregistry.io. Use it when a source gives full URIs.

**What does a prefix expand to?** `show` prints the URI prefix. A Mech's
schema lists its prefixes under `prefixes:`; a new one takes its expansion
from here. For an OBO ontology that is the OBO PURL,
`http://purl.obolibrary.org/obo/<PREFIX>_`.

**Which other namespaces does a domain use?** `show` lists what depends on
a prefix and what it appears in. An ontology that imports another names it
there; that is a hint at what the domain's records will mention.

## The Mech's prefixes govern

The Bioregistry's preferred form is advice. A Mech writes CURIEs as its
schema's `prefixes:` say, and the template's are fixed: evidence cites
`PMID:`, which the Bioregistry calls `pubmed`, and the reference validator
expects `PMID:`. When the script reports a different preferred prefix for
one the schema already has, keep the schema's. Use the Bioregistry's for a
prefix the schema lacks.

A prefix is often also a KG-Registry id (`mondo`, `chebi`, `envo`), where
the `search-kg-registry` skill finds what is built from that resource and
who ingests it.
