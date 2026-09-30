# The GoatMech domain model

This file is the design record for what GoatMech knows. Every schema change
updates it. The survey behind it is `example/survey-brief.md` in mechmaker.

## What a record is

One record is one goat breed, as the Vertebrate Breed Ontology (VBO) names
it: a direct child of `VBO:0400025` Goat breed.

Not records:

| Candidate | Where it goes |
|---|---|
| A national population of a breed, e.g. `VBO:0009093` Saanen, Argentina | Nowhere yet. VBO keeps it one level below the breed |
| A herd, a farm, a single animal | Out of scope |
| A breed of another species | Out of scope; VBO covers many species |
| A variety a source mentions that VBO lacks | A `CURATION_TODO` discussion on the nearest breed, and a new-term request to VBO |

## Identity

Records are keyed by the breed's VBO CURIE, and `record_term` repeats it
with VBO's label. The identity enum accepts direct children of
`VBO:0400025` only, so a national population cannot be a record.

The filename stem is derived from `name`, e.g. `saanen.yaml`. `name` is the
breed's common English name, usually VBO's label without the `(Goat)`
suffix.

Granularity: VBO decides. Two names are one breed when VBO has one term for
them; a VBO synonym is a `synonyms` entry, not a second record.

## Sections

| Section | Question it answers | Grounding | Cardinality | Filled from |
|---|---|---|---|---|
| `origins` | Where did the breed arise? | NCIT, under `NCIT:C25464` Country | one or more | the source's own words for the region; the country as the bound term |
| `purposes` | What is it kept for? | `ProductionPurposeEnum` | one or more | what the source says the breed is kept for |
| `distinguishing_features` | How do you tell it apart? | VT, under `VT:0000001` vertebrate trait, for the kind of trait | one or more | each feature a source states, one feature per entry |
| `horns` | Is it horned? | `HornStatusEnum` | at most one | the breed description or standard |
| `measurements` | How big, how productive? | VT for the trait, UO for the unit | any | a number a source states, with its sex, statistic and unit |
| `related_breeds` | What is it descended from, or what came from it? | VBO, under `VBO:0400025` | any | history sections and breed studies |
| `population` | How many are there? | none; a count, an area, a date | any | each figure a source reports, kept separate. Added after the paper test: Wikipedia states population figures for most breeds |
| `risk_status` | How endangered is it? | `RiskStatusEnum` (FAO categories) | at most one | FAO DAD-IS, or a source that quotes it |
| `evidence` | Record-level claims, such as the description | citations | any | as above |
| `discussions`, `datasets` | Gaps, to-dos, public datasets | `mech_shared` | any | as needed |

### Worked examples, from `saanen.yaml`

- **Origin.** preferred_term "Saanental, Bernese Oberland, Canton of Bern",
  term `NCIT:C17181` Switzerland. The bound term is always a country; the
  phrase keeps the finer detail. (GAZ has finer places, but its countries
  have no is-a parent in OLS, so a dynamic enum cannot reach them.)
- **Purpose.** `DAIRY`, quoting "It is a productive dairy goat".
- **Feature.** preferred_term "short white coat", term `VT:0010463`
  coat/hair pigmentation trait. The VT term names the kind of trait; the
  phrase states the breed's value. One feature per entry: "white skin" is a
  second feature, under `VT:0002095` skin pigmentation trait.
- **Horns.** `VARIABLE`, quoting "It may be horned or hornless".
- **Measurement.** trait `VT:0001253` body height, sex `MALE`, statistic
  `TYPICAL`, value 90, unit `UO:0000015` centimeter.
- **Related breed.** relation `GAVE_RISE_TO`, breed "Banat White".

### Rules for features

- A feature is something a source says distinguishes the breed, or
  characterizes it: coat, skin, ears, horns, profile, size, adaptation.
- Use the source's words in `preferred_term`, shortened, never embellished.
- Bind the most specific VT trait that names the kind of trait. If none
  fits, leave `term` out and open a `CURATION_TODO`.

## Evidence

Every section entry carries evidence. Sources, in order of preference:

1. Peer-reviewed breed characterization studies: `PMID:`.
2. Wikipedia: `WIKIPEDIA:<Article_title>`, fetched as plain text through
   the custom source in `.linkml-reference-validator-sources.yaml`. Never
   `url:`; its cached HTML breaks quotes that cross a link.
3. FAO DAD-IS, once its terms of use are read (see the source queue).

Wikipedia text changes over time. The committed `references_cache/` holds
the text as it was quoted.

## Out of scope

Individual animals, herds, and husbandry advice. Breeds of other species.
Genomic variants, until a curator proposes a section with a population
strategy.

## Related Mechs

None in MechRegistry records animals or breeds. VBO is maintained by the
Monarch Initiative; missing breeds go to its tracker.
