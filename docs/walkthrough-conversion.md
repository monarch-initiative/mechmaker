# Walkthrough: converting a knowledge base

This page follows one real conversion, on 2026-09-30. The existing
knowledge base is the Monarch Initiative's data ingests: the GitHub
repositories that feed the Monarch knowledge graph. The Mech made from them
is IngestMech. One record is one ingest, and the interesting part is each
ingest's upstream sources: where the data comes from, and under what terms.

The trial converted three ingests, `zfin-ingest`, `omim-ingest` and
`go-ingest`. The result is in the repository at
[`example/ingestmech`](https://github.com/monarch-initiative/mechmaker/tree/main/example/ingestmech).

!!! example "See the result"
    IngestMech's documentation site: [IngestMech](example/ingestmech/index.html),
    and its [record browser](example/ingestmech/records/index.html).

The run was made by Claude Code following the
[`convert-knowledge-base`](skills/convert-knowledge-base.md) skill. The
[GoatMech walkthrough](walkthrough.md) covers the steps shared with any new
Mech, such as checking the tools, in more detail.

## 1. Survey the knowledge base

The request:

> Build a Mech for the Monarch Initiative's data ingests, the repositories
> with "-ingest" in their name. Curate information about the source of each
> ingest. Convert zfin-ingest, omim-ingest and go-ingest.

The knowledge base is not one file. It is spread across repositories, and
the survey measured it with the GitHub API:

| Measured | Result |
|---|---|
| Unarchived repositories named `*ingest*` | 40 |
| With the koza template layout (`download.yaml` and `src/versions.py`) | 25 |
| Upstream source ids (infores) across those 25 | 40 |
| Of those, missing from the Biolink information resource catalog | 13, among them `infores:CHANGEME` |
| Ingests that record the license of their upstream data | 0 |

The last row decided what the Mech is for. The ingests say where data
comes from. None says under what terms. The survey brief is
[`example/ingest-survey-brief.md`](https://github.com/monarch-initiative/mechmaker/blob/main/example/ingest-survey-brief.md).

The licenses of the knowledge base itself were checked first: the three
ingests are BSD-3-Clause or MIT. Copying their metadata into records, with
attribution, is allowed. Had it not been, the skill stops there.

## 2. Map it and generate

One record is one ingest repository in the template layout. No ontology
names ingests, so ids are minted: `ingestmech:omim-ingest`. It was generated from a mechmaker checkout, hence the `.`. The answers are
in [`example/ingest-answers.yml`](https://github.com/monarch-initiative/mechmaker/blob/main/example/ingest-answers.yml).

```console
$ copier copy --trust --defaults --data-file example/ingest-answers.yml . example/ingestmech
$ cd example/ingestmech && just install && just qc
QC passed: 7 gate(s).
```

## 3. Design from the fields

Each file the conversion reads became a section:

| Source file | Section |
|---|---|
| `.copier-answers.yml` | `description`, `code_license` |
| `src/versions.py` | `upstream_sources`: infores id and name |
| `download.yaml` | `upstream_sources[].files` |
| `README.md` | `organisms` (species listed by NCBITaxon id), `associations` (Biolink classes) |
| `src/*.yaml` | `koza_transforms` |
| nothing | `upstream_sources[].data_license`, `description`, `homepage`: curation |

The record also keeps `repository` and `source_commit`, the commit it was
converted from. See IngestMech's
[domain model](example/ingestmech/DOMAIN/index.html).

!!! note "Friction, fixed"
    The template's own conversion tests built bare records, and IngestMech's
    required `repository` rejected them. The tests now start from each
    Mech's example record, so a schema can add required fields.

## 4. The conversion script

[`scripts/convert_monarch_ingests.py`](https://github.com/monarch-initiative/mechmaker/blob/main/example/ingestmech/scripts/convert_monarch_ingests.py)
reads each repository at its current commit and yields one entry per
ingest to the Mech's `just convert` helper. Three things it does are the
point of the skill:

- **Every copied fact is quoted.** Each file, source and license copied
  from a repository carries an evidence item that quotes the line it came
  from, with a `url:` reference pinned to the commit:
  `url:https://raw.githubusercontent.com/monarch-initiative/omim-ingest/de31fd0…/download.yaml`.
- **Identifiers are checked, never trusted.** Each infores id is looked up
  in the Biolink catalog, pinned to a commit. Species labels come from OLS.
- **Gaps are written down.** What no ingest records becomes a
  `CURATION_TODO` on the record.

The first dry run hit a network timeout on one repository. The helper
reported it as a skip, as it should, and a rerun picked it up. Then:

```console
$ just convert scripts/convert_monarch_ingests.py --model claude-opus-5-5 --apply
  written  zfin-ingest -> data/ingests/zfin_ingest.yaml
  written  omim-ingest -> data/ingests/omim_ingest.yaml
  written  go-ingest -> data/ingests/go_ingest.yaml

Wrote 3 record(s); 0 already existed; 0 could not be converted.
History: history/other/convert-monarch-ingest-repositories/2026-09-30T221900Z-claude-code-25e86b.yaml
```

`just qc-full` then fetched every quoted file and checked every quote and
term. Those checks passed. Two others failed: lint, on the new script, and
the check that the record browser is current. Tidying the script and
running `just render` fixed both.

A dry run over the whole organization shows what a full conversion would
do. Nothing was written:

```console
$ just convert scripts/convert_monarch_ingests.py --all
  ok       alliance-ingest -> data/ingests/alliance_ingest.yaml
  ...
  exists   omim-ingest -> data/ingests/omim_ingest.yaml (left alone)
  ...
  SKIPPED  koza-ingest-template: not in the koza template layout: no download.yaml, src/versions.py, .copier-answers.yml
  SKIPPED  ctd-ingest: could not read the repository: Command '['git', 'ls-remote', ...]' timed out after 120 seconds
  ...
Would write 20 record(s); 3 already existed; 17 could not be converted.
```

13 of the 17 skips are repositories outside the layout. 4 are network
timeouts. The 20 records include `aop-validator-and-ingest`, whose
`infores:CHANGEME` would be left out with a `CURATION_TODO`.

!!! note "Friction, fixed"
    The record writer folded long lines and `add-evidence` does not, so
    each rewrote the other's lines. Both now keep each value on one line.

## 5. Curate what the ingests never said

This is the part a conversion cannot do. For each upstream source, the
agent found its terms, homepage and description in the source's own
words, and added each quote with `just add-evidence`, which checks the
quote before writing:

| Source | Data license | Quoted from |
|---|---|---|
| ZFIN | CC BY 4.0 | ZFIN's own terms page |
| Zebrafish Phenotype Ontology | CC BY 3.0 | the OBO Foundry registry |
| GO annotations | CC BY 4.0 | GO's citation policy |
| Evidence & Conclusion Ontology | CC0 1.0 | the OBO Foundry registry |
| OMIM | not recorded | its terms page refused the request |

`add-evidence` refused one quote, correctly. The README's sentence starts
with a markdown link, so the text as written is not in the file:

```console
$ just add-evidence data/ingests/omim_ingest.yaml --at 'upstream_sources[0]' --ref url:…/README.md \
    --snippet "OMIM (Online Mendelian Inheritance in Man) is a comprehensive database of human genes and genetic phenotypes"
ERROR: the snippet was not found in url:…/README.md: Text part not found as substring: …
Nothing was written.
```

The quote was taken again from the text after the link. ZFIN's license
sentence crosses a link too, and was quoted in two parts joined with
` ... `.

OMIM's terms page answered 403 to every scripted request. Its data license
was not written from memory. The record says so:

```yaml
  - discussion_id: omim-ingest-data-licenses
    prompt: The terms OMIM's data is under are not recorded.
    kind: KNOWLEDGE_GAP
    status: OPEN
    rationale: OMIM's terms page, https://www.omim.org/help/agreement, answered 403 to
      scripted requests on 2026-09-30, and neither the ingest nor OMIM's paper states the
      terms. A person with an OMIM account can read them and record them here.
```

`access` was set only for OMIM, whose download URL carries a key
placeholder and whose README says "requires access key". For the others no
source read says what downloading takes, so the field is empty.

The records are `PROPOSED`. `just qc-full` passed all 9 gates.

## 6. Record the source

`curation/source_queue.tsv` lists the ingest repositories as the knowledge
base being converted, and the registry draft lists them as
`prov:wasDerivedFrom`. The Biolink catalog, used to check ids, is
`prov:used`.

## What is left

A full conversion is 20 more records, in batches, with the four timeouts
retried. Each would need the same curation of its sources. Several
sources, such as ZFIN, are read by more than one ingest; a Mech keyed by
source could hold those facts once.
