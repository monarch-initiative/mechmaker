---
name: make-mech
description: >-
  Create a new Mech (an AI agent-curated, ontology-grounded, evidence-backed
  knowledge base in the DisMech pattern) from the mechmaker Copier template,
  end to end: survey the domain, choose the template answers, generate the
  repository, design the schema, seed the first records, prepare the
  MechRegistry entry, and audit the result. Use when asked to make, start, scaffold or set up a new
  Mech or knowledge base for some domain.
---

# Make a Mech

mechmaker splits the work in two. Copier lays down everything that does not
depend on the domain, the same way every time. You do the rest: the parts
that need judgment about the domain.

| Step | Who | Output |
|---|---|---|
| 0. Check the machine | script | a ready machine |
| 1. Survey the domain | you, with `survey-domain` | a domain brief |
| 2. Choose the answers | you, checked by script | `answers.yml` |
| 3. Generate | Copier | the repository |
| 4. Design the schema | you, with `design-mech-schema` | `docs/DOMAIN.md`, the schema |
| 4b. Choose workflows | you and the person | the GitHub automation |
| 4c. Style the site | you, with `site-design` | `conf/site.yaml` |
| 5. Seed records | you, with the new Mech's `curate-record` | 3 to 5 exemplar records |
| 6. Register | you, with `register-mech` | a registry entry; an issue or pull request if the person wants one |
| 7. Audit | script and you, with `audit-mech` | a checklist of what was asked for |

If the person wants several Mechs whose records link to each other's, use
`make-fleet`: it makes a Coordinator and then runs this skill once per
member, with answers from the Coordinator. A member's identity and fleet
answers (`mech_name`, `mech_slug`, `github_org`, `repo_name`,
`record_class`, `records_dir`, `fleet_name`, `fleet_coordinator`,
`fleet_links`) come from `just answers <member>` there; merge them into
`answers.yml` and do not change them here.

If the person already has a knowledge base to bring in, use
`convert-knowledge-base` instead. It follows these steps and adds the
survey of the old knowledge base, the conversion script and its trial.

Do not skip to step 3. A Mech generated from unexamined answers has the wrong
record type, the wrong identity ontology, or the wrong root, and every one
of those is expensive to change once records exist.

## 0. Check the machine

Two scripts come with this skill, in the `scripts/` folder beside this
file. Below, `<scripts>` stands for that folder's path. It depends on how
the skill was installed: `.agents/skills/make-mech/scripts` after
`npx skills add`, a folder under `~/.claude/plugins/` for the Claude Code
plugin, and `skills/make-mech/scripts` in a mechmaker checkout. Both
scripts need only Python 3. Run them where they are; do not copy them
into the Mech.

```bash
python3 <scripts>/check_env.py --network
```

If the Mech will use deep research (see step 2), add `--research`: at
least one provider must be ready.

It checks for git, uv, just and Copier (and Claude Code and gh, which are
optional), and that GitHub and PyPI answer. OLS and PubMed are checked too,
as optional: warn the person if one is down and the Mech will depend on it. Exit 0 means ready.
Otherwise it prints the command that fixes each problem on this operating
system. Show those to the person; installing software on their machine is
their call. Run them only when they say so. A service that does not answer is usually a passing outage:
wait and run it again rather than working around it.

## 1. Survey

Run the `survey-domain` skill. It answers: what is one record, what keys it,
which ontologies ground it, what sources feed it, and which existing Mechs
overlap. Do not continue until the brief names the record entity in one
sentence.

Start `requests.yml` now, beside where `answers.yml` will go. Put in each
thing the person asks for, in their words, as they ask: a section, a
source, an import, a page. Add to it at every step. Step 7 checks the Mech
against it. The `audit-mech` skill gives the format.

## 2. Answers

Some answers belong to the user. Ask for them; do not invent them:

- the maintainer's name, email, ORCID and GitHub login;
- the GitHub organization that will own the repository;
- the data and code licenses;
- the collection (`monarch`, `xmech` or `none`);
- the site's colors and light or dark mode (`site_palette`, `site_accent`,
  `site_theme`), if they care; the defaults are fine otherwise;
- whether to add deep research (`deep_research`), and which provider they
  can use and pay for. Recommend it when the survey found a large
  literature; skip it when records come from one database.

The rest come from the brief. Write them to a data file:

```yaml
# answers.yml
mech_name: HabitatMech
mech_slug: habitatmech
full_title: Habitat Mechanisms Knowledge Base
description: >-
  HabitatMech records microbial habitats: ...
record_class: Habitat
record_noun: habitat
records_dir: data/habitats
identity_prefix: ENVO
identity_root: ENVO:01000813        # verified below, never guessed
identity_direct_only: false         # true when only the root's children are records
ontologies: [ENVO, NCBITaxon, CHEBI, GO_BP]
causal_graphs: true
taxon_scope: ""
domains: [environment, microbiology]
author_name: ...
author_email: ...
author_orcid: ...
github_org: ...
github_user: ...
collection: none
data_license: CC-BY-4.0
code_license: BSD-3-Clause
include_site: true
include_claude_hook: true
site_palette: teal        # Material color names; see the site options page
site_accent: amber
site_theme: auto          # auto, light or dark
workflows: [sweep, docs, comment-guard]   # step 4b revisits this
deep_research: true      # literature-heavy domain; see the deep research page
output_formats: [yaml, json, jsonld, ttl, sqlite, sql, csv]   # what just export writes; add kgx for a knowledge graph
# kgx_biolink: false   # with kgx: when Biolink does not fit the domain
tabular_layout: per_class   # or flat: one row per record in CSV/TSV
python_min: "3.11"
```

`ontologies` takes these keys: `GO_BP`, `GO_MF`, `GO_CC`, `CL`, `UBERON`,
`CHEBI`, `HP`, `MONDO`, `NCBITaxon`, `ENVO`, `PATO`, `OBI`, `UO`, `PR`, `SO`,
`MAXO`, `FOODON`, `VBO`, `VT`, `NCIT_COUNTRY`. Each adds one descriptor
class, one dynamic enum with a verified root, and one record section. Pick
what the records will really bind. `term_backend: sqlite` checks them
against downloaded copies instead of OLS.

Any other ontology OAK can read goes in `extra_ontologies`, and gets the
same three things. It can be on OLS, an OBO Foundry ontology read as SQLite,
on BioPortal, or a file the Mech will keep under `ontologies/`:

```yaml
extra_ontologies:
  - {prefix: ZFA, root: "ZFA:0100000", root_label: zebrafish anatomical entity, noun: anatomy, slot: anatomy_terms}
  - {prefix: <ACRONYM>, root: "<ACRONYM>:<root id>", root_label: <its label>,
     noun: <one word or two>, adapter: "bioportal:<ACRONYM>", uri: "<its term URI base>"}
  - {prefix: LAB, root: "LAB:0000001", root_label: lab protocol, noun: protocol,
     adapter: "simpleobo:ontologies/lab.obo", uri: "https://example.org/lab/LAB_"}
```

`adapter` defaults to `ols:<prefix>` and `uri` to the OBO PURL; give both for
anything else. An OLS ontology with its own IRIs keeps the default adapter but
needs `uri`: EFO's is `http://www.ebi.ac.uk/efo/EFO_`. Check each root and two or three expected terms through the
same adapter before generating:

```bash
python3 <scripts>/check_terms.py --adapter bioportal:<ACRONYM> label <ACRONYM>:<root id>
python3 <scripts>/check_terms.py --adapter simpleobo:lab.obo under LAB:0000001 LAB:0000042
```

BioPortal needs `BIOPORTAL_API_KEY`, here and as a repository secret for CI;
the person sets it. Never print the key, and mask `apikey=` in any output you
show: a failed BioPortal request prints its URL with the key in it. Tell them a local file must be copied into
`ontologies/` and committed after generation.

If `output_formats` includes `jsonld` or `ttl`, the schema's prefixes and
URIs are part of the design: `design-mech-schema` says what to declare, and
`just export` fails until they are right.

**Check the identity root before generating.** Take three to five entities
you expect to be records, find their CURIEs, and check they sit under the
root:

```bash
python3 <scripts>/check_terms.py search envo "hot spring"
python3 <scripts>/check_terms.py under ENVO:01000813 ENVO:00000051 ENVO:00000022
```

The script exits 1 if any term is missing or outside the root. A root that
rejects expected records is wrong. Choose the most specific root that
accepts them all. If the brief says only direct children are records, add
`--direct`: then each must be a child of the root itself.

## 3. Generate

```bash
copier copy --data-file answers.yml --defaults \
  gh:monarch-initiative/mechmaker <dest>
cd <dest>
git init -b main
just install
just qc
```

Use an absolute local path instead of `gh:...` when working from a
checkout; Copier records it, and a relative one breaks `copier update`. Copier
then copies the latest release tag; add `--vcs-ref HEAD` to use the
checkout as it is. `just qc`
must pass on the fresh copy. If it does not, the template is broken: stop
and report it, do not patch the output.

Commit the untouched output as its own first commit. Every later change is
then a readable diff against the template.

## 4. Design

If the person has an existing schema for the domain, the design starts
from it: `just import-schema` (see `design-mech-schema`).

Run the `design-mech-schema` skill in the new repository. It fills in
`docs/DOMAIN.md`, reshapes the scaffold schema to the domain, and, if deep
research is on, rewrites the research prompt from the same sections and
tries it with the free mock provider. Commit.

## 4b. Choose the workflows

`docs/WORKFLOWS.md` in the new Mech lists every GitHub workflow the template
knows. The deterministic ones (`sweep`, `docs`, `comment-guard`) are cheap
and safe. Agent workflows cost money per run and need secrets and, for some,
a GitHub App.

A sound first set for a Mech a person will curate with agents:
`sweep`, `docs`, `comment-guard`, `claude`, `review`, `triage`, `dedupe`, and
`literature-scan` if the domain is fed by literature. Add `curation-scanner`
and `compliance` only once the person has created an agent GitHub App and
wants unattended curation. Leave `agent_schedules` off at first; run each
agent once by hand and read its summary.

Ask the person which to turn on, and whether they will create the Apps.
Then:

```bash
uvx copier update --vcs-ref=:current: --skip-answered --defaults --data 'workflows=[...]'
```

`--vcs-ref=:current:` keeps the Mech at the template commit it was made
from, so only the answer changes. Without it Copier moves to mechmaker's
latest tag: it takes every newer template change along with the answer, or,
for a Mech made with `--vcs-ref HEAD`, stops because that would be a
downgrade. It needs Copier 9.8.0 or newer.

Adapt `.github/prompts/` to the domain, and tune `conf/literature_scan.yaml`
until a trial `just literature-scan --days 30` returns mostly relevant
papers. The Mech's `github-workflows` skill has the details. Setting
secrets and creating Apps act on the live repository: the person does
those, or you do them only after they say so.

## 4c. Style the site

Optional. Colors, mode, the browser's front-page columns and the sections
shown on record pages are in `conf/site.yaml`. Once the schema is settled,
choose `index_columns` that help someone scan the corpus (for example
`name`, `status`, and `record_term` when records are keyed by an
ontology), and hide sections that are noise to a
reader (`curation_history` is hidden by default). The Mech's `site-design`
skill covers each setting; run `just site-check`, and look with
`just docs-serve`.

## 5. Seed

Pick three to five records that span the domain: one typical, one hard, one
at the edge of scope. Curate each with the new Mech's `curate-record` skill.
If deep research is on and the person agrees to the cost, run it on one
seed record first (`just research <provider> <stem>`) and use its leads:
it is the real test of the research prompt.
Real sources, real quotes, `status: PROPOSED`. Run `just qc-full`.

Seeding tests the design. When a record will not fit, change the schema now
with `extend-schema`, while there are five records and not five hundred.

## 6. Register

Run the `register-mech` skill. It brings the draft entry up to date and
validates it, then asks the person whether to list the Mech in MechRegistry
now: not yet, by an issue for the registry's maintainers, or by a pull
request. A Mech that is not ready to be seen keeps its draft for later.

## 7. Audit

Run the `audit-mech` skill on the new Mech, with `requests.yml`. It checks
every answer and every ask against the files, and you judge what a script
cannot. Do not fix what it finds in the same breath: report it, and let the
person choose.

## Publishing

Creating the GitHub repository and pushing are visible to others. Ask the
user before either one. Tell them what will be created and where.

## Report

End with: the repository path, what `just qc-full` said, the records seeded,
the registry issue or pull request (or that the person chose not yet),
the decisions you made that the user should look at (record type, identity
root, sections cut or added), and anything you could not source. Then the
audit from step 7: its checklist, what was not implemented and why, and
its next steps.
