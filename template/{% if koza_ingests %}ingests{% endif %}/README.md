# Ingests

The Mech's own structured data ingests, one folder each, for sources no
Monarch Initiative ingest covers. A folder holds:

| File | What it is |
|---|---|
| `download.yaml` | what kghub-downloader fetches, into `build/ingest/<name>/` |
| `<transform>.yaml` | a Koza transform config: one reader, the columns, the writer |
| `<transform>.py` | the Koza transform: one row in, nodes and edges out |

`just new-ingest <name>` scaffolds one, `just ingest <name>` runs it, and
`conf/ingests.yaml` lists it. The `structured-ingests` skill covers the
rest: writing the transform, testing it, and seeding records from its rows.
