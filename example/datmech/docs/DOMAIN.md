# The DaTMech domain model

This file is the design record for what DaTMech knows. mechmaker
wrote the skeleton; the `design-mech-schema` skill filled it in from the
domain survey (mechmaker's `example/dat-survey-brief.md`). Every later
schema change updates it.

## What a record is

One record is one US ZIP code area: where its water drains, where its
drinking water and wastewater are treated, and what has gone wrong with
its water.

A ZIP code is a Postal Service delivery route, not an area. The area a
record means is the Census Bureau's ZIP Code Tabulation Area (ZCTA) for
that code, 2020 vintage. A ZIP code with no ZCTA (post office boxes, a
single large building) is not a record: it has no area to drain.

Not records here:

| Candidate | Where it goes |
|---|---|
| A watershed | `watersheds`, on each ZIP area it drains |
| A treatment plant | `treatment_facilities`, on each ZIP area it serves |
| An incident, such as the Flint water crisis | `incidents`, on each ZIP area it touched |
| A city or county | Nowhere. Cities span several ZIP areas; the ZIP area is the unit |

## Identity

No ontology names ZIP areas. The id is minted from the ZIP code itself:
`datmech:<ZIP>`, for example `datmech:48502`. The id is the ZIP code,
and no other field repeats it.

An id never changes when a record is renamed, and no two records share one.
A ZIP code the Postal Service retires keeps its record, `DEPRECATED`.

`name` is the ZIP code and the place the Postal Service names for it:
`48502 Flint, Michigan`. The filename stem is derived from `name`:
`48502_flint_michigan.yaml`.

Granularity: one ZIP code, one record. Two ZIP codes in one city are two
records, and share their watersheds, plants and incidents by repeating
them. When records start repeating the same incident many times, that is
the signal to give incidents their own Mech (see Related Mechs).

## Priority

Most ZIP areas have no recorded incident, and a record without one says
little a database lookup would not. **A ZIP area is curated when an
incident touched its water**, and `curation_priority` says how urgently:

| Value | Rule |
|---|---|
| `HIGH` | At least one incident with an advisory to the public (boil water, do not drink, bottled water) or a declared emergency |
| `MEDIUM` | At least one incident, none with an advisory |
| `LOW` | Searched (see `curation/record_queue.tsv`), no incident found |
| `UNASSESSED` | Not searched yet |

`validate.py` enforces the rule against `incidents`: a record with an
advisory must be `HIGH`, a record with incidents cannot be `LOW` or
`UNASSESSED`, and a `LOW` record has no incidents. `curation/record_queue.tsv`
lists candidate ZIP areas, each with the incident that puts it in the
queue, so the next record curated is the one with the most to say.

## Sections

### `zcta`: the area

The Census ZCTA for the ZIP code: vintage, interior point, land and water
area. One. Filled from Census TIGERweb (`PUMA_TAD_TAZ_UGA_ZCTA/MapServer/1`,
queried by `ZCTA5`), quoted from the query's JSON.

Its `bounding_box` is the ZCTA's extent in WGS84, from the same layer
asked for `returnExtentOnly=true&outSR=4326`, quoted and rounded to six
decimals. The record browser draws it on the record's map.

Example, 48502: vintage 2020, interior point 43.0146449, -83.6891591,
1,185,564 m² of land, 17,992 m² of water; box -83.696946, 43.006408 to
-83.679611, 43.02246.

### `watersheds`: where the water drains

The USGS hydrologic units (HUC) the area lies in. Many: the HUC12 at the
ZCTA's interior point and its HUC8, and others the area crosses. Each
`Watershed` is a drainage basin (`class_uri` ENVO:00000291, *drainage
basin*). ENVO's *watershed* (ENVO:00000292) is the divide between basins,
not the basin, so it is not used. Filled from the USGS Watershed Boundary
Dataset (`hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer`,
layer 4 for HUC8, layer 6 for HUC12), queried at the interior point.

Each watershed links to the Water Quality Portal's monitoring locations in
it (`water_quality_portal`), by HUC: the place to look for measurements.
Each has a `bounding_box`, its extent from the same dataset queried by HUC
code, so the map shows the area beside the watersheds it drains to.
mechmaker's `add-record-map` skill has the script that prints a box and its
quote.
`water_bodies` names the main rivers and lakes, bound to ENVO under
`ENVO:00000063` (*water body*).

Example, 48502: HUC12 `040802040410` Gilkey Creek-Flint River, in HUC8
`04080204` Flint; water body Flint River, ENVO:00000022 *river*.

### `bounding_box`

On `zcta` and on each watershed: `west`, `south`, `east`, `north` in
decimal degrees. Treatment plants and incidents have no box: the sources
give a plant an address or a point at most, and an incident no extent.

### `treatment_facilities`: where the water is treated

The plants that treat the area's drinking water and its wastewater. Many.
`facility_type` binds ENVO under `ENVO:00003861` (*industrial building*):
ENVO:03600004 *drinking water treatment plant* or ENVO:00002043
*wastewater treatment plant*. A facility names its operator, its EPA
identifier (`PWSID` for a public water system, NPDES permit for a
discharger), its `service_status` (current, former, emergency backup), and
its waters: `source_waters` for drinking water, with the EPA source type,
and `receiving_waters` for wastewater, both water bodies under ENVO.

A plant outside the ZIP area that serves it belongs here. A ZIP area on
private wells with no public system has no drinking water facility; say so
in a discussion.

Example, 48502: the Flint Corrosion Control Plant, current, which buys
treated Lake Huron water from the Great Lakes Water Authority and Genesee
County; the Flint Water Treatment Plant, former, which treated Flint River
water in 2014 and 2015 and which EPA lists as inactive; and the Flint
Water Pollution Control Facility, discharging to the Flint River.

### `incidents`: what went wrong

Events that harmed, or threatened, the safety or quality of the area's
water. Many. Each has a kind (contamination, treatment failure, spill,
toxic bloom, outbreak, infrastructure failure), dates, a cause in prose,
and the following, each bound where an ontology covers it:

| Field | Ontology, root |
|---|---|
| `processes` | ENVO under `ENVO:02500000` (*environmental system process*), e.g. ENVO:02500039 *water pollution* |
| `contaminants` | CHEBI under `CHEBI:24431` (*chemical entity*), e.g. CHEBI:25016 *lead atom* |
| `organisms` | NCBITaxon under `NCBITaxon:1`, e.g. NCBITaxon:446 *Legionella pneumophila* |
| `affected_waters` | ENVO under `ENVO:00000063` (*water body*) |
| `advisories` | none: `AdvisoryKindEnum`, with who issued it, when, and how many people |

Filled from Wikipedia first (its articles cite the primary reports), then
from government reports, the literature, news and deep research. Every
date and number is quoted.

Example, 48502: the Flint water crisis, April 2014 to 2019, lead and
Legionella; a state of emergency declared on January 5, 2016.

### `curation_priority`

See Priority.

### `evidence`, `discussions`, `datasets`

Record-level citations, open questions (mech_shared `Discussion`), and
public datasets (mech_shared `Dataset`).

## Evidence sources

`evidence_source` says what kind of source a quote comes from:
`GOVERNMENT_RECORD`, `GEOSPATIAL_DATASET`, `MONITORING_DATA`,
`UTILITY_RECORD`, `ENCYCLOPEDIA`, `NEWS`, `PUBLICATION`, `OTHER`.

References are PMIDs and DOIs for the literature, `WIKIPEDIA:<title>` for
Wikipedia (fetched as plain text through Wikipedia's API; see
`.linkml-reference-validator-sources.yaml`), and `url:` for everything else,
including the Census and USGS queries.

## Sources

Ranked in `curation/source_queue.tsv`: Census TIGERweb, the USGS
Watershed Boundary Dataset, the Water Quality Portal
(https://www.waterqualitydata.us/, beta at https://waterqualitydata.us/beta/),
EPA ECHO and SDWIS, Wikipedia, government reports, the literature, news,
and deep research reports (leads only, never cited).

## Out of scope

- Water quality measurements themselves. The Water Quality Portal holds
  them; records link to it by watershed.
- Health outcomes of an incident beyond what the incident's sources say.
  Lead poisoning and Legionnaires' disease are DisMech's.
- Legal proceedings, except as a source of facts about the incident.
- Places outside the United States: ZIP codes are American.

## Related Mechs

- **HabitatMech** (ENVO): shares vocabulary for water bodies and
  environmental materials.
- **SOMAMech**: extracts environmental health papers; a paper about an
  incident here may be one of its records.
- **DisMech**: the disorders an incident can cause.

None is linked by id yet.
