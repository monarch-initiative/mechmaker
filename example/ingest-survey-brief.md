# Domain brief: Monarch data ingests

Written with the `convert-knowledge-base` and `survey-domain` skills on
2026-09-30. The existing knowledge base here is spread across GitHub: the
Monarch Initiative's ingest repositories. Every count below was measured,
and every identifier was looked up.

## The existing knowledge base

| Question | Answer, measured |
|---|---|
| Where | GitHub organization `monarch-initiative`: 40 unarchived repositories with `ingest` in the name |
| Entries | 25 of the 40 have the koza template layout: a `download.yaml` and a `src/versions.py`. The other 15 are tools (`koza-ingest-template`, `monarch-ingest`, `monarch-ingest-commons`, `ingest-artifacts`, `monarch-ingest-dashboard`) or older and differently laid out ingests (`alliance-*-ingest`, `zfin-orthology-ingest`, `umls-ingest`, and others) |
| Format | Files in each repository, not a table. `download.yaml` (kghub-downloader) lists the files fetched; `src/versions.py` names each upstream source by infores id and name; `.copier-answers.yml` has a one-line description and the code license; `README.md` has prose, the Biolink classes produced, a citation and a license line; `src/*.yaml` are the koza transforms |
| Identifiers | The repository name. Upstream sources are named by infores ids, 40 of them across the 25 repositories |
| Identifier quality | 13 of the 40 infores ids are not in the Biolink information resource catalog (`infores_catalog.yaml` at `1d5fa99`), among them `infores:CHANGEME` in `aop-validator-and-ingest` and `infores:agr` in two repositories |
| Citations | A free-text citation in each README. OMIM's gives a PMID; ZFIN's and GO's give journal references with no identifier |
| License of the ingest code | BSD-3-Clause for `zfin-ingest` and `omim-ingest`, MIT for `go-ingest` (each repository's `.copier-answers.yml` and `LICENSE`). Copying their metadata into records, with attribution, is allowed |
| License of the upstream data | Not recorded in the ingests at all. It has to be curated from each source's own terms: this is the gap the Mech fills |

Trial set, chosen to span the corpus: `zfin-ingest` (one source plus an
ontology mapping file, eight files), `omim-ingest` (one file behind an
access key), `go-ingest` (two sources, fourteen files, thirteen species).

## Record

**One record is one ingest repository** in the koza template layout.

| Candidate | Where it goes instead |
|---|---|
| An upstream source, such as ZFIN | A section of each ingest that reads it. A source read by several ingests appears in each; a source-keyed Mech could come later |
| One koza transform inside an ingest, such as `zfin_orthology` | A field on the ingest's record |
| A tool repository, such as `koza-ingest-template` | Nowhere. Out of scope |

Granularity rule: a repository is a record if it has a `download.yaml` and
a `src/versions.py`. A repository without them is out of scope until it is
moved to the template.

## Identity

No ontology names ingests. Ids are minted: `ingestmech:<repository-name>`,
for example `ingestmech:omim-ingest`. The repository URL and the commit a
record was converted from are kept as fields.

## Grounding

| Kind of thing | Vocabulary | Checked |
|---|---|---|
| Upstream source | infores ids, from the Biolink information resource catalog | not an ontology on OLS; the conversion checks each id against the catalog |
| Species covered | NCBITaxon | `NCBITaxon:9606` Homo sapiens, `NCBITaxon:7955` Danio rerio |
| What the ingest produces | Biolink association classes, as `biolink:` CURIEs | not on OLS; kept as CURIEs with a pattern |
| Data and code licenses | SPDX identifiers | pattern only |

## Sources

| Source | Gives | License | Access |
|---|---|---|---|
| The ingest repositories | everything the conversion reads | BSD-3-Clause or MIT | raw files at a pinned commit |
| Biolink information resource catalog | infores ids, names, homepages | Apache-2.0 (repository `LICENSE`) | one YAML file |
| Each upstream source's own site | description, data license, access terms | varies | pages; omim.org answers 403 to scripted requests |

## Neighbors

No Mech in the registry records data sources or ingests. The nearest are
the Monarch Mechs, which consume the knowledge graph these ingests build.

## Mechanism

None. The records are attributes of a pipeline. `causal_graphs: false`.

## Open questions

- Upstream data licenses are the main curation work. OMIM's terms page
  refuses scripted requests, so its license may stay a knowledge gap.
- The 13 infores ids missing from the catalog: missing from the catalog, or
  wrong in the ingest? Each is a `CURATION_TODO` on its record.

## Draft answers

See `ingest-answers.yml`.
