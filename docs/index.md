# mechmaker

mechmaker helps you start a new **Mech**: a knowledge base where AI agents
do most of the curation and people review their work.

You say what your knowledge base is about. mechmaker sets up a repository
with a data model, checks that catch bad citations and made-up identifiers,
a documentation site, and instructions that teach an AI agent how to curate
in your field.

<div class="grid cards" markdown>

- **[Getting started](getting-started.md)**

    What to install, then make a Mech with an agent or by hand.

- **[Already have a knowledge base?](existing-knowledge-base.md)**

    How to bring an existing one into the Mech pattern.

- **[What a Mech contains](what-you-get.md)**

    The files, the checks, the commands.

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
