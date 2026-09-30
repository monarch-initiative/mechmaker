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

Close and reopen your terminal, then check that everything is there:

```bash
git --version
uv --version
just --version
copier --version
```

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
