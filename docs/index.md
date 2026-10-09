# mechmaker

mechmaker helps you start a new **Mech**: a knowledge base where AI agents
do most of the curation and people review their work.

You say what your knowledge base is about. mechmaker sets up a repository
with a data model, checks that catch bad citations and made-up identifiers,
a documentation site, and instructions that teach an AI agent how to curate
in your field.

## Start here

Paste this into your AI agent, in the folder where the Mech should live.
Change the first line to your topic. The copy button is at the top right
of the box.

```text
I want a Mech about: bacterial biofilm matrix components.

1. Install the mechmaker skills: npx skills add monarch-initiative/mechmaker -y
   (No npx? Read them from https://github.com/monarch-initiative/mechmaker/tree/main/skills instead.)
2. Read the make-mech skill and follow it, from its step 0.
3. Ask me before you install a tool, and before you create anything on GitHub.
```

[Getting started](getting-started.md) says what happens next, how to
install the skills yourself, and what your machine needs. An agent reading
this site can start from [llms.txt](llms.txt).

<div class="grid cards" markdown>

- **[Getting started](getting-started.md)**

    What to install, then make a Mech with an agent or by hand.

- **[Already have a knowledge base?](existing-knowledge-base.md)**

    How to bring an existing one into the Mech pattern.

- **[What a Mech contains](what-you-get.md)**

    The files, the checks, the commands.

- **[Walkthrough](walkthrough.md)**

    One real run, from the tools to curated goat breeds. See its
    [site](example/goatmech/index.html) and
    [record browser](example/goatmech/records/index.html).

- **[Conversion walkthrough](walkthrough-conversion.md)**

    An existing knowledge base, Monarch's data ingests, turned into a Mech.
    See its [site](example/ingestmech/index.html) and
    [record browser](example/ingestmech/records/index.html).

- **[No ontology, no list](walkthrough-datmech.md)**

    US ZIP code areas, their watersheds, treatment plants and water
    incidents: records keyed by no ontology, chosen by their incidents.
    See its [site](example/datmech/index.html) and
    [record browser](example/datmech/records/index.html).

- **[Fleets](fleets.md)**

    Several Mechs whose records link to each other's, coordinated by one
    more repository.

- **[Updating a Mech](updating.md)**

    Bring a Mech made with an older mechmaker up to date.

- **[Workflows](workflows.md)**

    GitHub automation, from checks to curation agents. You choose.

</div>

## What is a Mech?

A Mech is a knowledge base built on a pattern first used by
[DisMech](https://dismech.monarchinitiative.org/), a knowledge base of how
diseases work. Every Mech follows the same rules.

- **One file per thing.** Each disease, habitat, chemical, or whatever the
  Mech is about, gets its own record in its own file.
- **Standard vocabulary.** Records use terms from established ontologies,
  like the Gene Ontology, so they mean the same thing everywhere.
- **Every claim has a source.** Each claim cites a paper and quotes it word
  for word. A program fetches the paper and checks that the quote is there.
- **A full history.** Every change records who made it, human or AI, and why.
- **People review.** AI agents propose changes. People accept them or not.

Other Mechs are listed in
[MechRegistry](https://monarch-initiative.github.io/mechregistry/).

## How mechmaker works

Making a Mech has two kinds of work.

- **The part that is the same for every Mech** is done by a
  [Copier](https://copier.readthedocs.io/) template. It answers a few
  questions and writes the repository, the same way every time.
- **The part that depends on the field** is done by an AI agent following
  mechmaker's [skills](skills/index.md): what one record is, how records are
  keyed, which ontologies and sources fit, and what shape the data model
  takes.

## Source

mechmaker is open source, at
[monarch-initiative/mechmaker](https://github.com/monarch-initiative/mechmaker).
Code is released under the BSD 3-Clause license.
