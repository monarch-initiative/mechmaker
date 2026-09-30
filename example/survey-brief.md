# Domain brief: goat breeds

Written with the `survey-domain` skill on 2026-09-30. Every identifier below
was looked up in OLS; every count was measured.

## Record

**One record is one goat breed**, as VBO names it: a direct child of
`VBO:0400025` (Goat breed).

Not records:

| Candidate | Where it goes instead |
|---|---|
| A national population of a breed, such as `VBO:0009093` Saanen, Argentina | A field on the breed's record, if at all. VBO keeps these one level below the breed, from FAO DAD-IS national reporting |
| A single herd, farm, or animal | Nowhere. Out of scope |
| A breed of another species (VBO also covers sheep, dogs, rabbits) | Another Mech, if one is made |

Granularity rule: a candidate is a record if and only if its VBO term is a
direct child of `VBO:0400025`. VBO's own split decides whether two names are
one breed; a synonym in VBO is not a second record. A breed VBO lacks is a
`CURATION_TODO` and a candidate new-term request to VBO, not a minted record.

Corpus size: 715 direct children of `VBO:0400025` (OLS
`/ontologies/vbo/terms/<VBO_0400025>/children`). 199 of them are named
without a country, such as `Saanen (Goat)`; 516 carry one, such as
`Mosaico Lagunero, Mexico (Goat)`, and are local breeds reported by one
country. 1468 terms descend from the root in all, national populations
included.

## Identity

- **Keyed by VBO.** Every expected record has a VBO term: 8 of 8 sampled
  (Saanen, Boer, Angora, Nigerian Dwarf, Anglo-Nubian, Alpine, Toggenburg,
  Cashmere).
- **Root: `VBO:0400025` Goat breed.** `check_terms.py under` confirms
  `VBO:0000827` Saanen, `VBO:0000736` Boer, `VBO:0000811` Nigerian Dwarf,
  `VBO:0000722` Anglo-Nubian and `VBO:0000846` Toggenburg.
- **Caution.** National populations, such as `VBO:0009093`, also pass the
  root check. The schema's identity enum should accept direct children
  only.
- VBO terms carry a label, a synonym list, `Source: https://www.fao.org/dad-is`
  and an LBO cross-reference. They carry no definition.

## Grounding

| Kind of thing | Ontology | Root checked |
|---|---|---|
| The breed | VBO | `VBO:0400025` Goat breed |
| The species | NCBITaxon | `NCBITaxon:9925` Capra hircus |
| Kind of trait a feature describes | VT (Vertebrate Trait Ontology) | `VT:0000001` vertebrate trait; e.g. `VT:0011348` horn morphology trait, `VT:0002177` outer ear morphology trait, `VT:0010463` coat/hair pigmentation trait, `VT:0011351` wattle morphology trait, `VT:0001253` body height, `VT:0001259` body mass, `VT:0015043` milk amount |
| Country or region of origin | GAZ | `GAZ:00000448` geographic location; e.g. `GAZ:00002941` Switzerland |
| Units of measurements | UO | from the catalog |

Gaps: VT names the kind of trait, not its value. "White coat" and
"pendulous ears" have no terms; they stay as the curator's phrase with the
VT trait attached. Production purpose (dairy, meat, fibre) and FAO risk
status have no fitting ontology here; they become closed enums. ATOL and
LBO, the livestock trait and breed ontologies, are not in OLS.

## Sources

| Source | Gives | License | Access | CURIEs |
|---|---|---|---|---|
| VBO | Breed identity, names, synonyms | CC BY 4.0 (VBO README) | OLS API | yes |
| Wikipedia | Origin, appearance, uses, history | CC BY-SA 4.0 | API; plain-text extracts | `WIKIPEDIA:<title>` through a custom source (see below) |
| PubMed | Characterization studies | per article | E-utilities | PMID |
| FAO DAD-IS | Population, risk status, national reports | UNKNOWN (not verified) | web app | no |

- PubMed: `"goat breed"[tiab] OR "goat breeds"[tiab]` gives 894 hits;
  adding `AND (morpholog*[tiab] OR phenotyp*[tiab] OR characteriz*[tiab])`
  gives 245.
- **Wikipedia needs a custom reference source.** A `url:` reference caches
  the page's HTML, and a quote that crosses a link fails. Tested: "The Saanen
  originates in the historic region of Saanen" failed as `url:`, and passed
  as `WIKIPEDIA:Saanen_goat` through a source that fetches the plain-text
  extract from the MediaWiki API.

## Neighbors

None. No Mech in MechRegistry records animals or breeds (checked against
`registry/mechs.json`, 12 Mechs). GoatMech shares vocabulary with VBO's
maintainers, not with another Mech.

## Mechanism

The sources describe breeds by attributes and measurements, not causal
chains. `causal_graphs: false`.

## Open questions

- Should national populations appear on the breed record (for example, a
  list of VBO population terms)? Not for the first records.
- FAO DAD-IS licensing needs reading before any data are taken from it.

## Draft answers

```yaml
mech_name: GoatMech
mech_slug: goatmech
full_title: Goat Breed Knowledge Base
description: >-
  GoatMech records goat breeds: where each comes from, what it is kept for,
  and the features that tell it apart, with every claim quoted from its source.
record_class: GoatBreed
record_noun: goat breed
records_dir: data/goat_breeds
identity_prefix: VBO
identity_root: "VBO:0400025"
identity_uri: http://purl.obolibrary.org/obo/VBO_
identity_adapter: ols:vbo
ontologies: [NCBITaxon, UO]   # VT and GAZ are added by hand; not in the catalog
causal_graphs: false
taxon_scope: "NCBITaxon:9925"
domains: [organisms, phenotype]
```
