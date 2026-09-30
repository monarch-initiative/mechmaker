# Getting started

## What you need first

| Tool | What it is for | How to get it |
|---|---|---|
| **git** | Keeps the history of your files | Usually installed already. Otherwise see [git-scm.com](https://git-scm.com/downloads) |
| **A GitHub account** | Hosts your Mech so others can see and review it | [github.com](https://github.com) |
| **uv** | Installs Python and the Python tools a Mech uses | See below |
| **just** | Runs the Mech's commands, like `just qc` | See below |
| **Claude Code** (recommended) | The AI agent that does the setup and curation | [Claude Code setup](https://docs.claude.com/en/docs/claude-code/setup) |

You do not need to install Python yourself. uv does that.

**Install uv.** On macOS or Linux, in a terminal:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows, in PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Install just and Copier** with uv:

```bash
uv tool install rust-just
uv tool install copier
```

Close and reopen your terminal, then check that everything is there. One
command checks every tool, and with `--network`, the services a Mech uses:

```bash
curl -fsSLO https://raw.githubusercontent.com/monarch-initiative/mechmaker/main/skills/make-mech/scripts/check_env.py
python3 check_env.py --network
```

```console
Tools
  git     2.43.0   keeps the Mech's history
  uv      0.11.29  installs Python and the Mech's packages
  just    1.42.4   runs the Mech's commands
  copier  9.10.1   copies the template
  claude  2.1.286  the AI agent that curates
  gh      2.74.0   publishes to GitHub and opens pull requests

Services
  GitHub                  ok (200)  the template, and publishing
  PyPI                    ok (200)  installing packages
  OLS (ontology lookups)  ok (200)  term checks for ontologies served by OLS (optional)
  PubMed                  ok (200)  reference checks for PMID citations (optional)

Ready.
```

Anything missing is listed with the command that installs it on your
system. GitHub and PyPI must answer. OLS and PubMed are optional: a Mech may
use ontologies OLS does not serve, and sources other than PubMed, so if one
does not answer the check warns and still passes. If `just` or `copier` is installed but your terminal cannot find it,
the check says so and tells you to run `uv tool update-shell`.

Planning to use deep research? Add `--research` to see which providers
are ready. See [Deep research](deep-research.md).

No Python on your machine? uv brings its own: run
`uv run --no-project check_env.py --network` instead. (On Windows, the
command may be `python` rather than `python3`.)

## With an AI agent (recommended)

The agent asks you a few questions, looks up the ontologies and sources for
your field, and builds the Mech with you.

1. Open Claude Code in the folder where you want your Mech to live.
2. Add the mechmaker skills:

    ```
    /plugin marketplace add monarch-initiative/mechmaker
    /plugin install mechmaker@mechmaker
    ```

3. Describe what you want, in plain words:

    > Make a Mech for bacterial biofilm matrix components.

The [`make-mech`](skills/make-mech.md) skill works in steps and checks with
you along the way:

1. **Survey.** It works out what one record should be, which ontologies fit,
   which sources can feed the knowledge base, and whether an existing Mech
   already covers your topic.
2. **Set up.** It fills in the template's questions and creates the
   repository. It asks you for what only you know: your name, your GitHub
   organization, the licenses.
3. **Design.** It shapes the data model to your field.
4. **Choose workflows.** It asks which GitHub automation to turn on.
5. **Seed.** It writes the first three to five records, with real sources.
6. **Register.** It drafts your entry for MechRegistry.

It asks before it creates anything on GitHub.

## By hand

```bash
copier copy gh:monarch-initiative/mechmaker my-new-mech
```

Copier asks the [questions](reference/questions.md). Each has a short
explanation. To answer from a file instead, pass
`--data-file answers.yml --defaults`. Then:

```bash
cd my-new-mech
git init -b main
just install     # installs everything the Mech needs
just qc          # runs all the checks; a fresh Mech passes
```

Next, open `docs/DOMAIN.md` in the new Mech. It lists what is left to decide
about the data model. `docs/CURATION.md` explains how records are written.

## Publish it

1. Create a repository on GitHub and push the Mech to it.
2. In the repository's **Settings > Pages**, set **Source** to
   **GitHub Actions**. The `docs` workflow then publishes the documentation
   site on every push to `main`.
3. Turn on more [workflows](workflows.md) when you want them.
