# Curation history

One YAML record per curation session per target, written once and never
edited. The schema is `src/ingestmech/schema/history.yaml`, vendored
byte-identical from the Mech fleet canon.

```
history/<kind-dir>/<slug>/<TIMESTAMP>-<actor>-<shortid>.yaml
```

Every session gets its own file, so parallel agents never conflict.

Scaffold, never hand-write:

```bash
just new-history --kind record --slug <record-stem> --event EDIT --outcome changed \
  --summary "One scannable line" \
  --details "What was done, which sources, how it was validated, what was left undone." \
  --actor claude-code --agent-tool claude-code --model <model-id> --issue 12 --apply
```

`--details` is required in substance. The schema rejects the scaffold's
placeholder text. Corrections go in a new record that names the old one.

Kinds: `record`, `schema`, `mapping`, `report`, `infrastructure`, `other`.
Outcomes: `changed`, `no_change`, `needs_followup`, `blocked`. A review that
changed nothing is `no_change`, and it is still worth a record.
