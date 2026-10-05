# Deep research

A Mech can use [deep-research-client](https://pypi.org/project/deep-research-client/),
as DisMech does, to ask an AI research service for a report on one record:
what the literature says, with citations. The report is a list of leads for
a curator. It is never cited in a record; every claim that makes it into a
record still quotes its primary source.

It helps most for Mechs built on scholarly literature, where a record's
subject may have hundreds of papers. It helps least where the facts come
from one database, or the literature is thin.

## Turning it on

Answer `deep_research: true` when making the Mech (see
[Copier questions](reference/questions.md)), or add it later:

```bash
uvx copier update --skip-answered --data deep_research=true
```

The Mech then gets:

| Part | What it is |
|---|---|
| `just research PROVIDER TARGET` | a report on one record (its filename stem) or a new name |
| `just research-providers` | which providers this machine can use |
| `just research-status` | which records have research, from which providers |
| `just research-validate REPORT` | rerun a report's citation and term checks |
| `research/templates/record.md` | the question every report answers; adapt it to the domain |
| `research/README.md` | what a report is for, and how to use one |
| the `deep-research` skill | when to run it, which provider, and how to turn a report into evidence |

The `claude` and `curation-scanner` workflows, if on, receive the provider
keys from repository secrets so an agent can run it too.

## Dependencies

- **uv.** deep-research-client runs through `uvx` in its own environment,
  pinned to a tested version. It needs Python 3.12 or newer and brings
  dependencies a Mech does not otherwise need, so it is kept out of the
  Mech's own packages. uv downloads the Python it needs.
- **At least one provider.** Check with:

    ```bash
    curl -fsSLO https://raw.githubusercontent.com/monarch-initiative/mechmaker/main/skills/make-mech/scripts/check_env.py
    python3 check_env.py --research
    ```

| Provider | Needs |
|---|---|
| `claude_code` | Claude Code, installed and signed in. No extra key |
| `openai` | `OPENAI_API_KEY` |
| `falcon` (Edison Scientific) | `EDISON_API_KEY` |
| `perplexity` | `PERPLEXITY_API_KEY` |
| `asta` | `ASTA_API_KEY` |
| `consensus` | `CONSENSUS_API_KEY` |
| `openscientist` | `OPENSCIENTIST_API_KEY` |
| `cyberian` | an agent command line tool and agentapi |
| `mock` | `ENABLE_MOCK_PROVIDER=true`; free and fake, for trying the setup |

Keys belong in your environment or in repository secrets, never in a file
in the repository. Most providers charge per run; a run takes minutes.

## A run

```console
$ just research claude_code saanen
Researching saanen with claude_code -> research/saanen-deep-research-claude_code.md
```

The report's frontmatter records the provider, model, timing and results.
When the run ends, the client checks every cited PMID and DOI, every quote
attributed to one, and every ontology CURIE against its label, using the
Mech's own caches and ontology settings. It writes the results into the
report.

- `just research` will not overwrite a report; `--force` does, at the cost
  of a new run.
- Exit code 3 means the report was saved and a check found problems. Do not
  pay for a rerun: read the report, or rerun only the checks with
  `just research-validate`.
- Arguments after `--` go to deep-research-client, for example
  `just research falcon saanen -- --fallback` to let another ready provider
  take the run.

## From report to record

1. Read the report and its validation sections.
2. For each lead worth keeping, fetch the primary source with
   `just fetch-reference`, and read it.
3. Write the claim with a verbatim quote from that source.
4. Name the report, provider and model in the history record.
