# Walkthrough: GoatMech

This page follows one real run, start to finish: checking the tools, making
a Mech for goat breeds with the mechmaker skills, and curating its first
records. Every command and output below comes from that run, on 2026-09-30.
The result is in the repository at
[`example/goatmech`](https://github.com/monarch-initiative/mechmaker/tree/main/example/goatmech).

!!! example "See the result"
    GoatMech's own documentation site is published here, as a Mech would
    publish it: [GoatMech](example/goatmech/index.html), with its schema
    pages, and its [record browser](example/goatmech/records/index.html).

The run was made by Claude Code following the skills. You can repeat it
with an agent, or by hand; each step says what to run.

!!! note "Friction found along the way"
    Where something was harder than it should be, the page says so and
    links the ticket. Some were fixed during the run.

## 0. Check the tools

```console
$ git --version; uv --version; just --version; copier --version; claude --version
git version 2.43.0
uv 0.11.29 (x86_64-unknown-linux-gnu)
just 1.42.4
copier 9.10.1
2.1.285 (Claude Code)
```

If any is missing, see [Getting started](getting-started.md). There is no
single command that checks them all yet
([#2](https://github.com/monarch-initiative/mechmaker/issues/2)).

## 1. Survey the domain

With the mechmaker plugin installed, the request was:

> Make a Mech for goat breeds: one record per goat breed, grounded in the
> Vertebrate Breed Ontology (VBO:0400025 goat breed), with distinguishing
> features from Wikipedia and scholarly sources.

The agent ran [`make-mech`](skills/make-mech.md), which starts with
[`survey-domain`](skills/survey-domain.md). The survey looks things up
rather than recalling them:

```console
$ python skills/make-mech/scripts/check_terms.py search vbo "Saanen goat"
VBO:0009121	Saanen goat, Croatia (Goat)
VBO:0000827	Saanen (Goat)
VBO:0017515	Xinong Saanen (Goat)
VBO:0009093	Saanen, Argentina (Goat)
$ python skills/make-mech/scripts/check_terms.py under VBO:0400025 VBO:0000827 VBO:0000736 VBO:0000811
VBO:0000827	under VBO:0400025
VBO:0000736	under VBO:0400025
VBO:0000811	under VBO:0400025
```

What the survey found, in
[`example/survey-brief.md`](https://github.com/monarch-initiative/mechmaker/blob/main/example/survey-brief.md):

- **One record is one goat breed**: a direct child of `VBO:0400025`. There
  are 715. VBO also has national populations one level lower, such as
  `VBO:0009093` Saanen, Argentina; those are not records.
- **Traits** come from VT, the Vertebrate Trait Ontology. VT names the kind
  of trait ("coat/hair pigmentation trait"); the record states the breed's
  value ("short white coat").
- **Sources**: Wikipedia, PubMed (894 papers mention goat breeds), and FAO
  DAD-IS, whose terms of use were not yet read.
- **No other Mech overlaps.** None in MechRegistry records animals.

Two gaps showed here. The identity enum cannot yet say "direct children
only", so a national population would pass as a record
([#3](https://github.com/monarch-initiative/mechmaker/issues/3)). And VBO,
VT and the gazetteer are not in the template's ontology choices
([#4](https://github.com/monarch-initiative/mechmaker/issues/4)).

### Wikipedia as a source

Every claim in a Mech quotes its source word for word, and a program checks
the quote. A plain `url:` reference to a Wikipedia page caches its HTML, so
a sentence that crosses a link fails:

```console
[ERROR] Text part not found as substring: 'The Saanen originates in the historic region of Saanen'
```

A small file, `.linkml-reference-validator-sources.yaml`, adds a
`WIKIPEDIA:` prefix that fetches the article as plain text. With it,
`WIKIPEDIA:Saanen_goat` passes. GoatMech ships that file; the template does
not yet ([#6](https://github.com/monarch-initiative/mechmaker/issues/6)).

## 2. Choose the answers

The survey drafts most of the [Copier answers](reference/questions.md); the
maintainer's details and licenses come from the person.
[`example/answers.yml`](https://github.com/monarch-initiative/mechmaker/blob/main/example/answers.yml):

```yaml
mech_name: GoatMech
record_class: GoatBreed
record_noun: goat breed
records_dir: data/goat_breeds
identity_prefix: VBO
identity_root: "VBO:0400025"
ontologies: [NCBITaxon, UO]
causal_graphs: false
workflows: [sweep, docs, comment-guard]
# ... maintainer, licenses
```

## 3. Generate

```console
$ copier copy --data-file answers.yml --defaults gh:monarch-initiative/mechmaker goatmech
...
GoatMech is laid down in goatmech.
$ cd goatmech
$ just install        # 3 s with a warm uv cache
$ just qc             # 24 s
=== lint: just lint
=== records: closed schema: just validate-all
=== history: just validate-history
=== tests: just test -q
=== site is current: just render-check
=== docs build: just docs-build
QC passed: 6 gate(s).
```

For a real Mech, run `git init -b main` in the new directory. GoatMech
lives inside the mechmaker repository, so it skipped that.

The first attempt could not reach github.com and Copier printed a long
traceback. It was a network outage; the retry worked. The fresh copy also
showed that the generated `.gitignore` hid `uv.lock`, which a Mech must
commit. That was fixed in the template during the run.

## 4. Design the schema

The agent ran [`design-mech-schema`](skills/design-mech-schema.md) in the new
Mech. It writes `docs/DOMAIN.md` first, then the schema. GoatMech's record:

| Section | Grounding |
|---|---|
| `origins` | NCIT countries, under `NCIT:C25464` Country |
| `purposes` | `DAIRY`, `MEAT`, `MOHAIR`, `CASHMERE`, ... |
| `distinguishing_features` | VT traits, under `VT:0000001` |
| `horns` | `HORNED`, `POLLED`, `VARIABLE` |
| `measurements` | a VT trait, a sex, a statistic, a value, a UO unit |
| `related_breeds` | VBO breeds |
| `population` | a count, an area, a date |
| `risk_status` | FAO categories |

Each term is checked against the ontology, and the checks earned their keep:

- **The gazetteer failed.** The survey picked GAZ for countries but had only
  checked its root's label. In GAZ as OLS serves it, a country has no is-a
  parent, so the term check rejected Switzerland. NCIT's Country class
  works. The survey skill now asks for sample terms to be checked with
  `under`, not only the root.
- **`is_direct: true` is ignored** by the term validator, so "direct
  children only" is enforced by a network check, `just check-identity`,
  which GoatMech adds to `just qc-full` ([#3](https://github.com/monarch-initiative/mechmaker/issues/3)).
- `check_terms.py` printed tracebacks when OLS was slow. It now retries and
  prints one line ([#5](https://github.com/monarch-initiative/mechmaker/issues/5)).

## 4b. Choose the workflows

Workflows are a Copier answer, so they are added with an update:

```console
$ uvx copier update --skip-answered --defaults \
    --data 'workflows=["sweep","docs","comment-guard","claude","review","triage","dedupe","literature-scan"]'
```

Copier added the workflows, their prompts and the literature scan, and kept
the hand-edited `justfile`. The literature scan was tuned in
`conf/literature_scan.yaml` until a 60-day trial returned mostly goat breed
papers:

```console
$ just literature-scan --days 60
6 paper(s) -> build/literature/packet.md
```

That trial found titles arriving with escaped markup (`&lt;i&gt;`), fixed in
the template during the run.

## 5. Curate

Curation uses the Mech's own skills. For Saanen, with
[`curate-record`](reference/mech-skills.md):

```console
$ just term-info ols:vbo VBO:0000827
VBO:0000827 ! Saanen (Goat)
$ just new-record --id VBO:0000827 --name "Saanen" --apply
data/goat_breeds/saanen.yaml
$ just fetch-reference WIKIPEDIA:Saanen_goat
$ just fetch-reference PMID:35034210
```

The agent read the fetched text, then filled each section. A feature, with
its source:

```yaml
distinguishing_features:
  - preferred_term: short white coat
    term:
      id: VT:0010463
      label: coat/hair pigmentation trait
    evidence:
      - reference: WIKIPEDIA:Saanen_goat
        reference_title: Saanen goat
        supports: SUPPORT
        evidence_source: ENCYCLOPEDIA
        snippet: It has white skin and a short white coat; some small pigmented areas may be tolerated.
```

Then the three checks:

```console
$ just validate data/goat_breeds/saanen.yaml
1 record(s) checked, 0 with errors.
✅ Validation passed
  All validations passed!
```

A changed number shows the quote check at work:

```console
[ERROR] Text part not found as substring: 'Average milk yield is 900 kg in a lactation of 264 days.'
```

Writing the first record was also the design's **paper test**. Wikipedia
gives population figures, and the schema had nowhere to put them, so a
`population` section was added. Unsourced facts became to-dos on the record,
not guesses: Saanen's FAO risk status, and four local variants with no VBO
term.

Two more records followed: Boer, citing two PubMed abstracts, and Nigerian
Dwarf, whose article gives its risk status. Every session adds a history
record:

```console
$ just new-history --kind record --slug saanen --event CREATE --outcome changed \
    --summary "Create: Saanen" --details "..." --apply
history/records/saanen/2026-09-30T184959Z-claude-code-25f3f2.yaml
```

### Review

A reviewer, human or agent, uses [`review-record`](reference/mech-skills.md).
On Boer it found that the cited article says the breed is horned, and the
record did not; that ear and horn descriptions were missing; and that a
review article was labelled a breed standard. A second `curate-record` pass
fixed them. The review and the fix each have a history record.

Curation friction, ticketed: nothing fills `reference_title` from the cache
([#9](https://github.com/monarch-initiative/mechmaker/issues/9));
evidence is written into YAML by hand, where an unquoted colon broke a
record ([#7](https://github.com/monarch-initiative/mechmaker/issues/7)); a
record's description has no evidence of its own
([#8](https://github.com/monarch-initiative/mechmaker/issues/8)).

### The full check

```console
$ just qc-full         # 31 s
=== records: identity is a breed: just check-identity
Identity check: 0 record(s) are not breeds.
=== records: ontology terms: just validate-terms-all
✅ All 3 files passed validation
=== records: verbatim quotes: just validate-references-all
  All validations passed!
QC passed: 9 gate(s).
```

## 6. Register

The draft entry in `registry/goatmech.md` passes MechRegistry's own
validator. Its homepage would be the Mech's documentation site; for the
example, that is the copy [published here](example/goatmech/index.html).

```console
$ uv run mechregistry validate mech/goatmech/goatmech.md
ok   mech/goatmech/goatmech.md
1 entries checked, 0 with errors
```

GoatMech is an example, so it was not submitted.

## Every day after

| To | Run |
|---|---|
| add or improve a breed | ask your agent, which uses `curate-record`; or `just new-record`, `just fetch-reference`, `just validate` |
| check a pull request | `review-record`, or the `review` workflow on GitHub |
| find the least complete records | `just compliance` |
| find new papers | `just literature-scan --days 30`, or the `literature-scan` workflow |
| see the site | `just docs-serve`; GoatMech's is [here](example/goatmech/index.html) |
| check everything | `just qc-full` |
