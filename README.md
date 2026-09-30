# mechmaker

mechmaker helps you start a new **Mech**: a knowledge base where AI agents
do most of the curation and people review their work.

You tell it what your knowledge base is about. It sets up a ready-to-use
repository with a data model, checks that catch bad citations and made-up
identifiers, and instructions that teach an AI agent how to curate in your
field.

## What is a Mech?

A Mech is a knowledge base built on a pattern first used by
[DisMech](https://dismech.monarchinitiative.org/), a knowledge base of how
diseases work. Every Mech follows the same few rules:

- **One file per thing.** Each disease, habitat, chemical or whatever your
  Mech is about gets its own record, in its own file.
- **Standard vocabulary.** Records use terms from established ontologies,
  like the Gene Ontology, so they mean the same thing everywhere.
- **Every claim has a source.** Each claim cites a paper and quotes it word
  for word. A program fetches the paper and checks that the quote is really
  there.
- **A full history.** Every change records who made it, human or AI, and why.
- **People review.** AI agents propose changes. People accept them or not.

Other Mechs are listed in
[MechRegistry](https://monarch-initiative.github.io/mechregistry/).

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

**Install just and Copier** (the tool that copies this template), using uv:

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

## Start a new Mech with an AI agent (recommended)

This is the easiest way. The agent asks you a few questions, looks up the
ontologies and sources for your field, and builds the Mech with you.

1. Open Claude Code in the folder where you want your Mech to live.
2. Add the mechmaker skills:

   ```
   /plugin marketplace add monarch-initiative/mechmaker
   /plugin install mechmaker@mechmaker
   ```

3. Describe what you want, in plain words. For example:

   > Make a Mech for bacterial biofilm matrix components.

The agent works in steps and checks with you along the way:

1. **Survey.** It works out what one record should be, which ontologies fit,
   and which sources can feed the knowledge base. It also checks whether an
   existing Mech already covers your topic.
2. **Set up.** It fills in the template's questions and creates the
   repository. It asks you for the things only you know, like your name,
   your GitHub organization, and the license you want.
3. **Design.** It shapes the data model to your field.
4. **Seed.** It writes the first three to five records, with real sources.
5. **Register.** It drafts your entry for MechRegistry.

It asks before it creates anything on GitHub.

## Start a new Mech by hand

If you prefer to work without an agent:

```bash
copier copy gh:monarch-initiative/mechmaker my-new-mech
```

Copier asks you questions: the Mech's name, what one record is, which
ontologies to use, and so on. Each question has a short explanation. Then:

```bash
cd my-new-mech
git init -b main
just install     # installs everything the Mech needs
just qc          # runs all the checks; a fresh Mech should pass
```

Next, open `docs/DOMAIN.md` in your new Mech. It lists what is left to
decide about your data model. `docs/CURATION.md` explains how records are
written.

## What if I already have a knowledge base?

You can turn it into a Mech. mechmaker does not convert existing data on its
own, so plan on some work, most of which an agent can do for you.

The usual path:

1. **Start a new Mech** for the same topic, as above. Keep your existing
   knowledge base where it is. It becomes a source for the new one.
2. **Shape the data model to fit what you have.** Ask the agent to run the
   `design-mech-schema` skill, and point it at your existing data. Your
   current fields tell it which sections a record needs.
3. **Write a conversion script** that reads your existing data and writes one
   Mech record per entry. The new Mech includes a helper,
   `write_validated_record`, that refuses to save a record that fails the
   checks. Converted records start as `DRAFT`.
4. **Bring the evidence up to standard.** This is usually the biggest job.
   A Mech needs each claim to quote its source word for word. If your
   knowledge base already cites papers, the agent can fetch each one and find
   the supporting sentence. Claims with no source become open questions
   in the record, and are kept, not thrown away.
5. **Review in batches.** Send converted records through pull requests a few
   dozen at a time, so people can actually read them.

A good first request to the agent:

> I have a knowledge base of X at <location>. Survey it, then make a Mech
> that can hold it, and convert five entries as a trial.

Try a handful of entries before converting everything. Problems with the
data model are cheap to fix when there are five records and costly when
there are five thousand.

## What you get

A new Mech comes with:

| Part | What it does |
|---|---|
| A data model | Describes what a record holds, written in [LinkML](https://linkml.io/) |
| Checks | Catch malformed records, made-up or mislabeled ontology terms, and quotes that do not match their source |
| Curation tools | Commands to create records, look up ontology terms, fetch papers and log history |
| Agent instructions | Skills that teach an AI agent how to curate, review records and change the data model |
| A website | A simple browsable page for every record (optional) |
| Automatic checks on GitHub | Every proposed change is checked before anyone reviews it |
| A registry entry | A draft listing for MechRegistry |

The commands you will use most, from inside your Mech:

```bash
just              # list every command
just qc           # run all the checks
just report       # count what is in the knowledge base
just validate data/<records>/<name>.yaml   # check one record fully
```

## Words you will see

| Word | Meaning |
|---|---|
| **Record** | One entry in the knowledge base, stored as one YAML file |
| **YAML** | A plain text format for structured data, readable by people |
| **Schema** or **data model** | The rules for what a record may contain |
| **Ontology** | A curated, standard vocabulary for a field, like the Gene Ontology |
| **CURIE** | A short identifier for a term, like `GO:0008150` |
| **Evidence** or **snippet** | A citation and the exact sentence quoted from it |
| **Curation history** | The log of who changed a record, when and why |
| **Pull request** | A proposed change on GitHub that people review before it is accepted |

## For developers

The rest of this README is about working on mechmaker itself.

### How it is organized

| Path | What it is |
|---|---|
| `copier.yml` | The questions Copier asks, and a table of supported ontologies with their root terms |
| `template/` | The files that become a new Mech. Files ending `.jinja` are filled in from the answers; the rest are copied as they are |
| `skills/` | Skills for the agent that makes a Mech: `make-mech`, `survey-domain`, `design-mech-schema`, `register-mech` |
| `.claude-plugin/` | Makes this repository installable as a Claude Code plugin |
| `tests/` | Tests that generate sample Mechs and check them |

`skills/make-mech/scripts/check_terms.py` looks up ontology terms, labels and
root terms before a Mech exists. It needs only Python.

### Checks in a generated Mech

1. **Schema.** Each record must match the data model. Unknown fields are
   errors.
2. **Terms.** [linkml-term-validator](https://github.com/linkml/linkml-term-validator)
   checks that each ontology term exists, carries its real label, and falls
   under the right part of the ontology.
3. **Quotes.** [linkml-reference-validator](https://github.com/linkml/linkml-reference-validator)
   fetches each cited source and checks the quote appears in it.

### Shared files

Two schema files, `mech_shared.yaml` and `history.yaml`, are shared by all
Mechs. They come unchanged from
[culturebotai-claw](https://github.com/CultureBotAI/culturebotai-claw), so
every Mech records discussions, datasets and history the same way. Do not
edit them in this repository. A test checks they are unchanged.

### Updating an existing Mech from the template

In the Mech's repository:

```bash
just update-template
```

### Working on mechmaker

```bash
just install
just test              # generate four sample Mechs and check the output
just test-generated    # generate three Mechs, install them, run their checks
just sample /tmp/x     # generate one sample to look at
```

## License

Code: BSD-3-Clause. See [LICENSE](LICENSE).
