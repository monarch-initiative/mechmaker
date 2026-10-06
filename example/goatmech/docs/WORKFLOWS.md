# GitHub workflows

Every workflow mechmaker knows is listed here, on or off. The set that is on
was chosen when this repository was made. To change it, run
`uvx copier update --skip-answered --defaults --data 'workflows=[...]'` with
the whole new list. Copier adds and removes the files; your edits to the
ones you keep are merged.

The `github-workflows` skill walks an agent through turning one on, setting
its secrets, and adapting its prompt.

## Always on

| Workflow | What it does |
|---|---|
| `qc.yaml` | The required check. Runs `just qc`. On a pull request, also checks terms and quotes for the records it changes, fails a curation PR that touches other files (the `scope-override` label allows it), and warns when a changed record has no new history record. |

## No agent

| Key | State | File | What it does | Needs |
|---|---|---|---|---|
| `sweep` | **on** | `sweep.yaml` | Weekly `just qc-full`: every term and quote against the live services. Finds upstream drift. | nothing |
| `docs` | **on** | `docs.yaml` | Builds the documentation site (LinkML schema pages, guides, corpus counts, and the record browser at `/records/`) and publishes it to GitHub Pages on every push to main. | Settings > Pages > Source: GitHub Actions |
| `comment-guard` | **on** | `comment-guard.yaml` | Hides comments from people without write access that carry attachments, installers or agent triggers. | nothing |
| `close-fork-prs` | off | `close-fork-prs.yaml` | Closes PRs from forks with a note pointing to CONTRIBUTING.md. Turn it on once agents act on PRs. | nothing |
| `release-records` | off | `release-records.yaml` | Attaches the exports `just export` writes, in the formats `conf/export.yaml` names, to each release. | nothing |
| `warm-reference-cache` | off | `warm-reference-cache.yaml` | Weekly: fetches open-access full text for cached references and opens one rolling PR. Worth it once the cache is large. | optional agent App, so CI runs on its PR |
| `pypi-publish` | off | `pypi-publish.yaml` | Publishes the package with trusted publishing. Most Mechs do not need this; the data is the product. | PyPI trusted publisher, `pypi-release` environment |

## Agents

All agent workflows need `ANTHROPIC_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` as
a repository secret. The API key is used when both are set; it has no weekly
cap. Models and turn budgets are in `.github/agent-config.yaml`. Prompts are
in `.github/prompts/`; edit them to fit the domain.
Scheduled agents run only when started by hand (Actions tab, Run workflow)
until `agent_schedules` is turned on.

| Key | State | File | What it does | Writes | Needs |
|---|---|---|---|---|---|
| `claude` | **on** | `claude.yaml` | Answers `@claude` from people with write access, in issues and PRs. | branches, PRs, comments | Claude GitHub App installed |
| `review` | **on** | `review.yaml` | Reviews each same-repo PR with the `review-record` skill. The agent reads the PR as data with a read-only token; a step with no model approves or requests changes. `/review` re-runs it. Refuses PRs from forks, however started. | reviews | reviewer App, or Actions allowed to approve PRs |
| `triage` | **on** | `triage.yaml` | Labels new issues. The agent only reads; a step with no model applies labels from a fixed list. `curation` goes on only when the author can write to the repository. | labels | `just labels` run once |
| `dedupe` | **on** | `dedupe.yaml`, `auto-close-duplicates.yaml` | Flags likely duplicates; closes them after three days unless a person objects. | one comment, a label, closure | nothing more |
| `pr-shepherd` | off | `pr-shepherd.yaml` | Comments on the most stuck PR, saying why and what would unstick it. The agent only reads; a step with no model posts. Never pushes or approves. | one comment | nothing more |
| `curation-scanner` | off | `curation-scanner.yaml` | Picks one unassigned `curation` issue or PR per effort tier and advances it. | branches, PRs, comments | agent App |
| `literature-scan` | **on** | `literature-scan.yaml` | Finds recent papers (PubMed or preprints) that match records and files a few `curation` issues. The agent only reads; a step with no model files them. Tune `conf/literature_scan.yaml`. | issues | nothing more |
| `compliance` | off | `compliance.yaml` | Improves the least complete records by `just compliance`, one PR each. | branches, PRs | agent App |
| `post-review` | off | `post-review.yaml` | Proposes a suggestion, reply or `Editorial:` issue for each unanswered human review comment; a step with no model posts them. | suggestions, replies, issues | nothing more |

### Identities

- **Built-in token.** Used by most workflows. GitHub does not start other
  workflows from its pushes or PRs, so nothing it writes gets CI.
- **Agent App** (`MECH_AGENT_APP_ID`, `MECH_AGENT_PRIVATE_KEY`). A GitHub
  App you create and install on this repository, with contents, issues and
  pull requests write. Workflows that push use it so their PRs run CI. The
  curation scanner and compliance workflows refuse to run without it.
- **Reviewer App** (`MECH_REVIEWER_APP_ID`, `MECH_REVIEWER_PRIVATE_KEY`).
  Optional, pull requests write only. A separate identity, so an approval
  counts toward branch protection and the writer never approves itself.
- **Claude App.** The `claude` workflow acts as the Claude GitHub App
  through OIDC. Install it from https://github.com/apps/claude.

### Deep research

On. The `claude` and `curation-scanner` workflows pass the provider keys
(`OPENAI_API_KEY`, `EDISON_API_KEY`, `PERPLEXITY_API_KEY`, `ASTA_API_KEY`,
`CONSENSUS_API_KEY`, `OPENSCIENTIST_API_KEY`) from repository secrets, so an
agent can run `just research`. Set only the ones you pay for. A run costs
money; the agents are told to research one record at a time.

### Langfuse

Off. Answer `langfuse` in Copier to add tracing to every agent workflow.

### Safety

- Agents that read text anyone can write (issues, comments, PR bodies,
  abstracts) have no write access. They return structured results, and a
  step with no model checks and posts them: `review`, `triage`, `dedupe`,
  `post-review`, `pr-shepherd`, `literature-scan`.
- Triage adds `curation` only to issues whose author can write to the
  repository. The curation scanner can push, so a stranger's issue reaches
  it only after a person has read it and added the label.
- Prompts and helper scripts load from the default branch, so a PR cannot
  change the instructions it is reviewed under.
- Tool lists are explicit. No workflow runs with permissions bypassed.
  `gh api` is left out wherever it could approve or merge.
- No agent merges. Merging is for people.
- Every agent run ends with `check_agent_run.py`, which fails the job with a
  clear cause (out of turns, out of credit, usage limit) instead of leaving
  a silent green.

## Not in the template

DisMech has more workflows. These were left out, and why:

| DisMech workflow | Why not |
|---|---|
| `dragon-ai.yml` | A second write-capable agent that duplicates `@claude`. |
| `claude-issue-summarize.yml` | Posts on every new issue from untrusted text; overlaps triage and dedupe. |
| `discussion-scanner.yml` | Needs GitHub Discussions and a large trust gate. Worth adding once a Mech has discussion traffic. |
| `generate-pages.yaml`, `deploy-docs.yaml` | Solve 30-minute site builds at DisMech's scale. Here the docs and the record browser are built fresh by `docs`, and `just qc` builds the same site. |
| `jev-recuration.yml` | Reads DisMech's own evaluation pipeline. |
| `reference-title-baseline.yaml`, `title-snippet-baseline.yaml` | Maintain lists of old failures. A new Mech starts at zero, so both checks are hard errors in `just validate-all` instead. |
| `verify-merge-integrity.yaml` | Guards against merge-queue failures at dozens of merges a day. |
| `kgx-release.yaml`, `mondo-emc-release.yaml`, `publish-ndex.yml` | Exports specific to DisMech's schema. `release-records` is the general form. |
| PR shepherd's merge controller | DisMech's shepherd merges approved PRs with no person in the loop. That is a policy a new Mech should choose deliberately, not inherit. |
