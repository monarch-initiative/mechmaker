# Walkthrough: a Mech with no ontology and no list

This page follows one real run, on 2026-10-09. GoatMech's records are keyed
by an ontology, and IngestMech's come from a knowledge base that already
lists them. DaTMech has neither. One record is one US ZIP code area: where
its water drains, where it is treated, and what has gone wrong with it. No
ontology names ZIP areas, no list says which ones to curate, and the part
that makes a record worth having, its incidents, is scattered across
Wikipedia, government pages, utility reports and papers.

The result is in the repository at
[`example/datmech`](https://github.com/monarch-initiative/mechmaker/tree/main/example/datmech).

!!! example "See the result"
    DaTMech's documentation site: [DaTMech](example/datmech/index.html),
    and its [record browser](example/datmech/records/index.html).

The run was made by Claude Code following the [`make-mech`](skills/make-mech.md)
skill. The [GoatMech walkthrough](walkthrough.md) covers the shared steps in
more detail.

## 1. The request

> Each entry is a US geographic region; we can use ZIP code as an ID for
> this. DaTMech tracks three main things: watersheds, water treatment
> plants, and incidents impacting water safety/quality. [...] the priority
> for curating an entry relies on whether it has any related safety/quality
> incidents. The EPA provides a source of water quality data too. [...]
> just three entries. Alignment with the ENVO ontology would be useful.

The asks went into
[`example/dat-requests.yml`](https://github.com/monarch-initiative/mechmaker/blob/main/example/dat-requests.yml),
for the audit at the end.

## 2. Survey: the record, its key, and where the data lives

A ZIP code is a Postal Service delivery route, not an area. The Census
Bureau's ZIP Code Tabulation Area (ZCTA) is the area built from it, so a
record means the 2020 ZCTA: 33,791 of them, counted from Census TIGERweb.
Ids are minted from the code itself, `datmech:48502`.

Each source was queried before it was written down:

| Source | What it gives | How it is cited |
|---|---|---|
| Census TIGERweb | the ZCTA's interior point and area | `url:` the query, quoted from its JSON |
| USGS Watershed Boundary Dataset | the HUC8 and HUC12 at that point | `url:` the query |
| Water Quality Portal ([beta](https://waterqualitydata.us/beta/)) | monitoring locations by HUC; 1,923 in the Flint River's HUC8 | a link on each watershed |
| EPA SDWIS (Envirofacts), ECHO | water systems, their plants and sellers; wastewater permits | `url:` the record |
| Wikipedia, EPA, utilities, PubMed | incidents | `WIKIPEDIA:`, `url:`, `PMID:` |

ENVO fits everything a record mentions, but no single root does. The
template's ENVO root, *environmental system*, rejected drainage basins,
treatment plants and lakes alike. The survey checked four narrower roots
instead, each against the terms it must admit:

| Section | ENVO root |
|---|---|
| watersheds | the class itself is *drainage basin* (`ENVO:00000291`); ENVO's *watershed* is the divide between basins, so it is not used |
| water bodies | *water body* (`ENVO:00000063`): lake, river, stream. *Aquifer* is not under it |
| treatment plants | *industrial building* (`ENVO:00003861`): both *drinking water treatment plant* and *wastewater treatment plant* |
| what happened | *environmental system process* (`ENVO:02500000`): *water pollution*, *algal bloom process* |

Contaminants bind CHEBI and organisms NCBITaxon. The brief is
[`example/dat-survey-brief.md`](https://github.com/monarch-initiative/mechmaker/blob/main/example/dat-survey-brief.md);
the answers,
[`example/dat-answers.yml`](https://github.com/monarch-initiative/mechmaker/blob/main/example/dat-answers.yml).

## 3. Priority, made a rule

"Curate a ZIP area when an incident touched its water" became
`curation_priority`, and a rule in the Mech's `validate.py`:

| Value | When |
|---|---|
| `HIGH` | an incident with a public advisory or a declared emergency |
| `MEDIUM` | incidents, none with an advisory |
| `LOW` | searched, nothing found |
| `UNASSESSED` | not searched yet |

A record whose priority disagrees with its incidents fails validation.
`curation/record_queue.tsv` lists the next ZIP areas to curate, each with
the incident that puts it there and the article to start from. The queue
is built by searching for incidents, not by walking 33,791 codes.

## 4. Three records

Chosen to span the domain:

| Record | Why | Incidents | Priority |
|---|---|---|---|
| 48502 Flint, Michigan | typical: the treatment change caused the harm | lead, boil-water advisories, Legionnaires' outbreak, trihalomethanes | `HIGH` |
| 43604 Toledo, Ohio | hard: one plant serves about 500,000 people across many ZIP areas, and the toxin came from a bloom in Lake Erie | microcystin do-not-drink advisory, August 2014 | `HIGH` |
| 44413 East Palestine, Ohio | edge: a train derailment, not the water system, harmed the water; the village draws groundwater | chemical spill into Sulphur Run and Leslie Run, February 2023 | `MEDIUM` |

East Palestine is `MEDIUM` because of what could not be sourced. News
reports say residents were told to drink bottled water after the
derailment, but the state's own pages for those updates now answer 404.
No advisory was written from a news summary. The record says so, and says
what would change its priority:

```yaml
  - discussion_id: east-palestine-bottled-water-advice
    prompt: Were residents advised to drink bottled water after the derailment, by whom, and until when?
    kind: KNOWLEDGE_GAP
    status: OPEN
    rationale: ... The state's own pages for those updates answered 404 on 2026-10-09, so no
      advisory is recorded. Sourced, it would make curation_priority HIGH.
```

EPA's own records corrected the first draft of Flint. The design's first
example called the city's own plant a backup. EPA's inventory of the
system's facilities says otherwise: the old plant and its Flint River
intake are inactive, and an active corrosion control plant treats water
bought from the Great Lakes Water Authority and Genesee County. The record
follows EPA.

The sources named *Microcystis* and microcystin in Toledo, not a species or
a congener, so the record binds the genus (`NCBITaxon:1125`) and the
toxin class (`CHEBI:48041`), and says why in `notes`.

```console
$ just qc-full
...
=== records: verbatim quotes: just validate-references-all
  Issues found: 0
  All validations passed!
QC passed: 11 gate(s).
```

## 5. Friction

!!! note "Wikipedia, as text"
    A `url:` reference caches the page's HTML, and a Wikipedia sentence
    crosses tags (`The <b>Flint water crisis</b> was`), so most quotes
    fail. DaTMech adds a `WIKIPEDIA:<title>` source in
    `.linkml-reference-validator-sources.yaml` that fetches the article as
    plain text through Wikipedia's API. Wikimedia refuses requests without
    a descriptive User-Agent, so the source sends one.

!!! note "Required fields and `new-record`"
    `just new-record` writes a bare record and refuses it if the schema
    requires more than a name. `state` and `curation_priority` are
    therefore `recommended`, and `validate.py` requires them once a record
    leaves `DRAFT`.

!!! note "Personal details in a source"
    EPA's `WATER_SYSTEM` table names each system's staff, with their
    email addresses and phone numbers. The records cite
    `WATER_SYSTEM_FACILITY` instead, which carries what they need (the
    plants, intakes and sellers) and no one's contact details.

!!! note "Smaller things"
    The template's schema-import test defines a `latitude` slot, which a
    Mech's own `latitude` collides with; DaTMech's are
    `interior_latitude` and `interior_longitude`. A PDF's text splits a
    drop capital (`T reatment`); the quote starts after it. The audit
    script looks for the template's own ENVO enum and reports ENVO missing
    when the design splits it into narrower ones.

## 6. Audit

The `audit-mech` checklist: 37 features asked for. The script marked 33
done. The other four were the ENVO item above and three it could not judge
without the Mech's own git history. Read by hand against mechmaker's
history and the records, all 37 are done. Every record fills its
watersheds, treatment facilities and incidents.

## What is left

- The four candidate ZIP areas in `curation/record_queue.tsv`.
- Toledo's second subbasin and East Palestine's private wells, open as
  `CURATION_TODO` on their records.
- A first deep research run on one record, as leads for the next.
