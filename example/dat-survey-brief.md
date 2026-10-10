# Domain brief: drainage and treatment of US regions

Written with the `survey-domain` skill on 2026-10-09. Every identifier
below was looked up, and every count was measured; the query is given
with each.

The domain has no single ontology whose terms are the records, and no
existing list of entries to convert. Records are places, keyed by an
identifier from outside any ontology, and most of what makes a record
worth curating (its incidents) is scattered across news, government
reports, Wikipedia and the literature.

## Record

**One record is one US ZIP code area: where its water drains, where it is
treated, and what has gone wrong with it.**

| Candidate | Where it goes instead |
|---|---|
| A watershed, such as the Flint River's | A section of each ZIP area it drains. A watershed-keyed Mech could come later |
| A treatment plant, such as Toledo's Collins Park plant | A section of each ZIP area it serves. One plant serves many ZIP areas, and appears in each |
| An incident, such as the Flint water crisis | A section of each ZIP area it touched. An incident-keyed Mech is the natural neighbor if incidents outgrow the records |
| A city or county | Nowhere. A city spans several ZIP areas and a ZIP area can cross city lines; the ZIP area is the unit |

Granularity rule: a record is one five-digit ZIP code with a Census ZIP
Code Tabulation Area (ZCTA). Two ZIP codes are two records, even in one
city. A ZIP code without a ZCTA (a post office box ZIP, a single large
building) is out of scope: it has no area to drain.

Corpus size: 33,791 ZCTAs in the 2020 Census (TIGERweb layer
`PUMA_TAD_TAZ_UGA_ZCTA/MapServer/1`). The Mech will never hold most of
them. See Priority.

## Identity

No ontology names ZIP areas. Ids are minted from the ZIP code:
`datmech:<ZIP>`, for example `datmech:48502`. ZIP codes are US Postal
Service delivery routes, not areas; the ZCTA is the Census Bureau's area
built from them, and is what a record's geography means. A ZIP code the
Postal Service retires keeps its record, with a note.

## Grounding

| Kind of thing | Vocabulary | Root | Checked |
|---|---|---|---|
| The drainage area itself | ENVO | `ENVO:00000291` drainage basin | label checked. ENVO's `watershed` (`ENVO:00000292`) is the divide between basins, not the basin: do not bind it |
| Source water bodies | ENVO | `ENVO:00000063` water body | `ENVO:00000020` lake and `ENVO:00000022` river under it. `ENVO:00012408` aquifer is **not** under it, nor under `ENVO:01000813`; groundwater sources take the EPA source type and `preferred_term` |
| Treatment facilities | ENVO | `ENVO:00003861` industrial building | `ENVO:03600004` drinking water treatment plant and `ENVO:00002043` wastewater treatment plant both under it |
| What happened in an incident | ENVO | `ENVO:02500000` environmental system process | `ENVO:02500039` water pollution under `ENVO:02500036` environmental pollution |
| Contaminants | CHEBI | `CHEBI:24431` chemical entity (the template's) | `CHEBI:25016` lead atom, `CHEBI:6925` microcystin-LR, `CHEBI:28509` chloroethene (vinyl chloride) under it |
| Organisms in incidents | NCBITaxon | the template's | `NCBITaxon:446` Legionella pneumophila, `NCBITaxon:1126` Microcystis aeruginosa |
| Watersheds | USGS Hydrologic Unit Codes (HUC8, HUC12) | not an ontology | pattern only; each code looked up in the Watershed Boundary Dataset |
| Water systems and permits | EPA PWSID (drinking water), NPDES permit id (wastewater) | not an ontology | pattern only |

The template's own ENVO root, `ENVO:01000254` environmental system,
rejects drainage basins, plants and lakes alike (checked). The design
replaces it with the four narrower roots above.

Gaps: no ontology covers incident kinds (a boil-water advisory, a
do-not-drink order, a spill) or regulatory actions. These are enums in the
schema.

## Sources

| Source | Gives | License | Access |
|---|---|---|---|
| Census TIGERweb, 2020 ZCTAs | the ZIP area: interior point, land and water area, polygon | US Government work, public domain | ArcGIS REST query by `ZCTA5` |
| USGS Watershed Boundary Dataset | the HUC8 and HUC12 watersheds a ZIP area lies in | public domain | ArcGIS REST query by point or polygon (`hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer`, layers 4 and 6) |
| Water Quality Portal (EPA, USGS, NWQMC), and its beta at https://waterqualitydata.us/beta/ | monitoring locations and results in a watershed | public domain | `wqx3/Station/search?huc=<HUC8>`; the Flint HUC8 `04080204` has 1,923 monitoring locations in the classic profile |
| EPA ECHO and SDWIS | public water systems, their source type, population served, violations | public domain | `echodata.epa.gov/echo/sdw_rest_services.get_systems`, two-step (query id, then results) |
| Utility and municipal pages | plant names, capacity, intakes | varies | pages |
| Wikipedia | the first account of an incident, with its citations | CC BY-SA 4.0 | pages |
| News and government reports (EPA, state agencies, CDC) | incident dates, advisories, affected populations | mostly public domain or quotable | pages |
| Literature | health effects and causes of incidents | per paper | PubMed: `"Flint" AND "water" AND "lead"` and similar per incident |

Deep research helps here: an incident such as Flint's has hundreds of
papers, reports and articles, more than a curator reads in a sitting.
`deep_research: true`.

## Priority

Most ZIP areas have no recorded incident, and a record without one says
little a database lookup would not. **A ZIP area is curated when an
incident touched its water.** Each record carries `curation_priority`,
set from its incidents, and `curation/record_queue.tsv` lists candidate
ZIP areas with the incident that puts each in the queue.

## Trial set

Chosen to span the domain:

| ZIP | Place | Why |
|---|---|---|
| 48502 | Flint, Michigan | Typical: a treatment change caused the incident; a large literature |
| 43604 | Toledo, Ohio | Hard: one regional plant serves many ZIP areas, the source is Lake Erie, and the toxin came from a bloom outside the region |
| 44413 | East Palestine, Ohio | Edge: a train derailment spilled chemicals into streams; the incident was not a failure of the water system, and the village draws groundwater |

Watersheds, from the ZCTA polygon against the Watershed Boundary
Dataset (2026-10-09):

| ZIP | HUC8 | HUC12 at the ZCTA's interior point |
|---|---|---|
| 48502 | 04080204 Flint | 040802040410 Gilkey Creek-Flint River |
| 43604 | 04100009 Lower Maumee; 04100001 Ottawa-Stony | 041000090804 Heilman Ditch-Swan Creek |
| 44413 | 05030101 Upper Ohio | 050301010606 Leslie Run-Bull Creek |

## Neighbors

From the registry (`mechs.json`, 2026-10-09). No Mech records places,
watersheds, utilities or water incidents. The nearest:

- **HabitatMech** records microbial habitats with ENVO. It
  `shares_vocabulary_with` this Mech for water bodies and materials.
- **SOMAMech** extracts environmental health papers. A paper on an incident
  here may be one of its records; DaTMech could consume them.
- **DisMech** records disorders; lead poisoning and Legionnaires' disease
  are its, not this Mech's.

## Mechanism

Incidents have causes: a change of source water leaches lead from pipes;
a bloom releases a toxin past a plant's treatment. These are short chains,
told in prose with evidence, not graphs worth drawing. `causal_graphs:
false`.

## Open questions

- A plant serves many ZIP areas and an incident touches many. When the
  Mech grows, incidents may need their own ids so ZIP areas share them.
- ZCTA boundaries change with each census. Records name the 2020 vintage.
- Population served and violation history come from SDWIS, whose two-step
  API is awkward to cite by URL. A conversion script could cache it.

## Draft answers

See `dat-answers.yml`.
