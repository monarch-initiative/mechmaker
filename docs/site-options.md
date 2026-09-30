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
| `footer` | Footer on every browser page | text |

The color names are Material for MkDocs' own, so one name colors both the
documentation site and the browser.

Then, in the Mech:

```bash
just site-check     # validates the file and reports contrast
just render         # rebuilds the browser in pages/; commit it
just docs-serve     # look at both at http://127.0.0.1:8000
```

`just qc` runs `site-check`, and fails if `pages/` is stale.

## Readability

Some palette colors are unreadable as text on a white page: yellow, amber,
lime. The browser handles that. Links use the palette color darkened (on
light pages) or lightened (on dark pages) just enough to reach a 4.5:1
contrast ratio, the WCAG AA level for text, and the header uses black or
white text, whichever reads better on the palette color. `just site-check`
shows the result:

```console
$ just site-check
palette yellow, accent amber, theme dark
  header: #1f1f1f on #ffec3d, contrast 13.6
  links on light pages: #82781f (adjusted from #ffec3d), contrast 4.5
  links on dark pages: #ffec3d, contrast 15.0
```

The documentation site uses Material for MkDocs' own color pairings. For a
few light palettes, such as cyan and light-green, Material puts white text
under 3:1 on the header. Prefer a darker palette if that matters.

## With an agent

Each Mech carries a `site-design` skill. Ask for what you want ("make the
site brown, and show the ontology term on the front page") and the agent
edits `conf/site.yaml`, checks it, renders, and shows you. For changes the
settings cannot make, the skill explains the page templates in
`src/<slug>/templates/` and the rules they must keep: colors only through
the settings, relative links, deterministic output.
