# Starting from an existing schema

If the knowledge a Mech will hold already has a schema, start from it. A new
Mech's `just import-schema` takes the schema's classes, slots and enums into
the Mech, and adds what every Mech needs around them: status, evidence and
quotes, discussions, and history.

```bash
just import-schema SOURCE --record-class CLASS                    # copy mode, dry run
just import-schema SOURCE --record-class CLASS --mode reference   # reference mode
just import-schema SOURCE --record-class CLASS --apply            # write it
```

`SOURCE` is a path or a URL. `CLASS` is the source's class for one record.
It becomes the Mech's record class: the Mech's own name for that class stays,
and it gains the source class's slots. Nothing is written without `--apply`,
and every decision is printed.

## Two modes

| | Copy (default) | Reference |
|---|---|---|
| The source's elements | copied into the Mech's schema, which owns them | kept in their own file, unchanged, and imported |
| The record class | gains the source class's slots | extends the source class (`is_a`) |
| Upstream changes | not followed; compare by hand | replace the file to take them |
| Reshaping | the agent may change anything | the source's classes cannot change |
| Names in both schemas | the Mech's core slots win; other clashes need `--rename` | the Mech uses the source's slot; a clash on what the Mech's checks need stops the import |
| RDF | each copied element keeps its source URI | the source's own URIs |

Use **copy** to start from someone's schema and make it the Mech's own. Use
**reference** when the Mech must stay conformant with an upstream standard.

Both record the source, its version and a SHA-256 of the file in the
schema's `annotations`, as `imported_schema`. Both check that the result
loads, merges with the Mech's other modules, and gives a JSON Schema for the
record class before writing anything.

## What happens to names in both schemas

Most schemas define `id`, `name` and `description`, and so does every Mech.

- **Copy mode** keeps the Mech's definitions of its core slots (`id`, `name`,
  `description`, `notes`, `synonyms`). Any other shared name stops the
  import, naming each one, until `--rename OLD=NEW` gives the source's
  element a new name. A source slot called `status`, for example, clashes
  with the Mech's review status: `--rename status=sample_status`.
- **Reference mode** cannot rename inside a file it keeps unchanged, and
  LinkML cannot merge a name defined in two schemas. So the Mech drops its
  own copy of a shared core slot and uses the source's. A source that
  defines anything the Mech's checks depend on (`evidence`, `reference`,
  `snippet`, `status`, `term`, `curation_history` and the like) cannot be
  referenced: the quote and term checks would quietly stop. Use copy mode.

Records are keyed by `id`. If the source's class has another identifier, it
becomes a plain slot: in copy mode by editing the copied slot, in reference
mode by `slot_usage` on the record class.

## Other formats

`--from` converts a schema in another format to LinkML first, with
[schema-automator](https://github.com/linkml/schema-automator), run through
`uvx` in its own environment, so the Mech never installs it:

| `--from` | Source |
|---|---|
| `json-schema` | JSON Schema |
| `owl` | OWL ontology |
| `rdfs` | RDFS schema |
| `xsd` | XML Schema |
| `frictionless` | Frictionless data package |
| `tsv`, `json` | data, from which a schema is inferred |

A converted schema is a snapshot, so copy mode usually suits it. Its
elements take the Mech's namespace, since a converter's invented namespace
means nothing in RDF. Check the result against the original: in the tests
here, schema-automator 0.5.7 dropped a JSON Schema `pattern`.

## An example: LinkML's personinfo

[personinfo](https://github.com/linkml/linkml/blob/main/examples/PersonSchema/personinfo.yaml)
is LinkML's example schema of people, places and organizations. Imported
into a Mech whose record class is `Researcher`:

```console
$ just import-schema personinfo.yaml --record-class Person
  slot id: the Mech's definition is kept, the source's set aside
  slot name: the Mech's definition is kept, the source's set aside
  slot description: the Mech's definition is kept, the source's set aside
  22 classes copied
  36 slots copied
  5 enums copied
  3 types copied
  Person is folded into Researcher: 24 slots
  source personinfo unversioned, sha256 091de8a6c8b7

# dry run; the result loads and validates. Pass --apply to write peoplemech.yaml.
```

```console
$ just import-schema personinfo.yaml --record-class Person --mode reference --apply
  slot description: the Mech's definition is dropped; the source's is used
  slot id: the Mech's definition is dropped; the source's is used
  slot name: the Mech's definition is dropped; the source's is used
  the source marks Container as tree_root; Researcher stays the Mech's record
  Researcher is_a Person; schema personinfo imported unchanged
  source personinfo unversioned, sha256 091de8a6c8b7
```

In both, a researcher record with a `primary_email` validates, and a bad
address fails on personinfo's own pattern. In copy mode the Turtle export
types the record `personinfo:Person` and writes address fields as
`personinfo:city`, the source's URIs.

One LinkML limit showed up: personinfo's `age_in_years` slot has the alias
`age`, and LinkML 1.11.1's RDF writer fails on a record that uses an alias,
with or without a Mech.

## Afterwards

Update `tests/data/example_record.yaml` so it exercises the new fields, and
`docs/DOMAIN.md` so it says where they came from. Then `just qc`. The
[`design-mech-schema`](skills/design-mech-schema.md) skill goes on from
there.
