# Site and record browser options

Every Mech publishes a documentation site, and most also carry a record
browser: a page for every record, inside the documentation site at
`/records/`. How both look is set in one file, `conf/site.yaml`.

## When the Mech is made

Copier asks three questions (see [Copier questions](reference/questions.md)):

| Question | Sets | Default |
|---|---|---|
| `site_palette` | the main color | `indigo` |
| `site_accent` | the hover and focus color | the palette color, or `amber` for brown, grey and blue-grey |
| `site_theme` | light or dark pages | `auto`, which follows each visitor's system |

The answers are written to `conf/site.yaml` in the new Mech.

## Any time after: `conf/site.yaml`

```yaml
title: "GoatMech records"
palette: brown
accent: amber
theme: auto
index_columns: [name, record_term, status]
hidden_sections: [curation_history]
map: true
footer: >-
  AI-curated. Validation checks that citations exist, quotes are exact and
  ontology terms are real. It does not check that the science is right.
```

| Setting | What it does | Values |
|---|---|---|
| `title` | Title of the browser's front page | text |
| `palette` | Main color: the docs header, the browser's header band, links | red, pink, purple, deep-purple, indigo, blue, light-blue, cyan, teal, green, light-green, lime, yellow, amber, orange, deep-orange, brown, grey, blue-grey |
| `accent` | Hover and focus color | the palette names except brown, grey, blue-grey |
| `theme` | Light or dark pages, for both sites | `auto`, `light`, `dark` |
| `index_columns` | Columns of the browser's front-page table, in order; the first links to the record. A field holding an ontology term shows its label | record field names |
| `hidden_sections` | Record sections left off browser record pages; the data keeps them | record field names |
| `map` | A map on each record page that holds a bounding box | `true` (the default), `false` |
| `footer` | Footer on every browser page | text |

The color names are Material for MkDocs' own, so one name colors both the
documentation site and the browser.

Then, in the Mech:

```bash
just site-check     # validates the file and reports contrast
just docs-serve     # look at both at http://127.0.0.1:8000
```

`just qc` runs `site-check` and builds the site. The browser is rendered
fresh on every docs build; `pages/`, from `just render`, is a local copy and
is not committed.

A Mech made with `include_site: false` has no browser. Its
`conf/site.yaml` holds only `palette`, `accent` and `theme`. Run
`just site-check`, then `just docs-serve`.

## How a record page is laid out

The browser reads the shape of each record and the Mech's schema, so a new
Mech gets a readable browser with no work:

- Field names come from the schema: a slot's `title` if it has one, or its
  name with underscores as spaces (`horn_status` shows as "Horn status").
  The slot's description appears under each section heading. To change a
  label, give the slot a `title` in the schema.
- Simple values, such as a repository URL or a date, go in an overview
  table at the top.
- A list of small, uniform objects, such as measurements, is a table, with
  each row's quotes folded into its last column.
- Curated mentions (anything with a `preferred_term`) and richer objects
  are cards, with their ontology term and their quotes in view.
- Evidence shows its source, the source's title, how it supports the
  claim, and the quote.
- Discussions are cards with their kind and status. Curation history is a
  table, folded away.
- URLs and identifiers are links. Values from the schema's enums are
  small labels in plain words, with the enum's description on hover.
- On a phone, tables become one block per row.
- A record that holds a bounding box (an object with `west`, `south`,
  `east` and `north` in decimal degrees) gets a map above its sections:
  each box a rectangle on OpenStreetMap, named by what holds it, with a
  list to turn each off. A record with no box has no map. The
  [`add-record-map`](skills/add-record-map.md) skill adds boxes to a Mech;
  [DaTMech](example/datmech/records/index.html) shows the result.

The front page table sorts by any column and filters as you type.

## Readability

Some palette colors are unreadable as text on a white page: yellow, amber,
lime. The browser handles that. Links use the palette color darkened (on
light pages) or lightened (on dark pages) just enough to reach a 4.5:1
contrast ratio on the darkest (or lightest) surface a link can sit on, the WCAG AA level for text, and the header uses black or
white text, whichever reads better on the palette color. `just site-check`
shows the result:

```console
$ just site-check
palette yellow, accent amber, theme dark
  docs header: #1f1f1f on #ffec3d, contrast 13.6
  browser header: #1f1f1f on #ffec3d, contrast 13.6
  links on light pages: #756d1c (adjusted from #ffec3d), contrast 4.5
  links on dark pages: #ffec3d, contrast 11.8
```

The documentation site uses Material for MkDocs' own color pairings. For a
few light palettes, such as cyan and light-green, Material puts white text
under 3:1 on the header, and `just site-check` marks the docs header line
with a warning. Prefer a darker palette if that matters.

## With an agent

Each Mech carries a `site-design` skill. Ask for what you want ("make the
site brown, and show the ontology term on the front page") and the agent
edits `conf/site.yaml`, checks it, renders, and shows you. For changes the
settings cannot make, the skill explains the page templates in
`src/<slug>/templates/` and the rules they must keep: colors only through
the settings, relative links, deterministic output.
