# AGENTS.md

For an AI agent working in this repository, or pointed at it.

## If a person wants a Mech

They want a new knowledge base, not a change to mechmaker. Do not build it
inside this repository.

1. Install the skills in the folder where the Mech will live:

   ```bash
   npx skills add monarch-initiative/mechmaker -y
   ```

   No npx? The skills are in `skills/` here. Read them in place.
2. Follow `make-mech` from its step 0, which checks the machine. For a
   knowledge base that already exists, follow `convert-knowledge-base`.
3. Ask the person before you install a tool, and before you create
   anything on GitHub.

The documentation, indexed for agents:
https://monarch-initiative.github.io/mechmaker/llms.txt

## If a person wants several linked Mechs

They want a Fleet: Mechs whose records link to each other's, each in its
own repository, with a Coordinator repository for what they share. Install
the skills as above, and follow `make-fleet` from its step 0.

## If a person wants to update a Mech

They have a Mech made from mechmaker and want its newer features. Work in
the Mech's folder, not here. Install the skills there as above, and follow
`sync-mech`. The person chooses which updates to take.

## If you are changing mechmaker

Read `CLAUDE.md`. It has the layout and the rules: what is vendored and
must not be edited, how the template is tested, and how generated pages
are made. Branch first; changes reach `main` by pull request.

`example/goatmech` and `example/ingestmech` are generated Mechs, each with
its own `CLAUDE.md`. Inside one, that file governs.
