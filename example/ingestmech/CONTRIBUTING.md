# Contributing to IngestMech

Thank you for helping. IngestMech is curated mostly by AI agents and
reviewed by people. Contributions from people are the review, and more.

## Ways to help

- **Open an issue.** Report an error in a record, ask for an ingest
  to be added, or suggest a source. Say what is wrong and cite a source if
  you have one.
- **Review a pull request.** Check that quotes support their claims and that
  terms are right. This is the part machines cannot do.
- **Curate.** Add or improve records. See `docs/CURATION.md` and `CLAUDE.md`.

## Pull requests

Push a branch to this repository and open the pull request from it. Pull
requests from forks are not accepted: automated review cannot run on them,
and they are a way to inject instructions into the agent workflows. Ask in
an issue to be given access to push branches.

Before opening a pull request:

```bash
just qc
just validate data/ingests/<record>.yaml   # for each record you changed
```

Keep a pull request to one purpose. A pull request that changes records
should change only records and their history and caches.

## Agents

Mention `@claude` in an issue or pull request to ask the agent for help, if
that workflow is on. Only people with write access can summon it.
