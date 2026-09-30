---
name: site-design
description: >-
  Change how the IngestMech documentation site and record browser look:
  colors, light or dark mode, title, footer, the columns of the browser's
  front page, the sections shown on record pages, and deeper changes to the
  page templates. Use when asked to restyle, rebrand, recolor or reorganize
  the site, or when the site is hard to read.
---

# Site design

Most changes are one line in `conf/site.yaml`. Start there. Edit the page
templates only for what the settings cannot do.

## Settings: `conf/site.yaml`

| Setting | What it does | Values |
|---|---|---|
| `title` | Title of the record browser's front page | text |
| `palette` | Main color: docs header, browser header band, links | red, pink, purple, deep-purple, indigo, blue, light-blue, cyan, teal, green, light-green, lime, yellow, amber, orange, deep-orange, brown, grey, blue-grey |
| `accent` | Hover and focus color | the palette names except brown, grey, blue-grey |
| `theme` | Light or dark pages, for both sites | `auto` (follows the visitor's system), `light`, `dark` |
| `index_columns` | Columns of the browser's front-page table, in order; the first links to the record | record field names, e.g. `name`, `id`, `status`, `record_term` |
| `hidden_sections` | Record sections left off browser record pages; the data keeps them | record field names |
| `footer` | Footer on every browser page | text |

The names are Material for MkDocs' own, so one name colors both sites.

After any change:

```bash
just site-check     # validates the file and reports contrast
just render         # rebuilds pages/; commit the result
just docs-serve     # look at both sites at http://127.0.0.1:8000
```

`just qc` fails if `pages/` is stale, so always run `just render` and commit
`pages/` with the settings change.

## Choosing colors

- Pick for the domain, not for decoration. A palette the maintainers
  already use (a lab or project color) is a good choice.
- Readability is handled for links: the browser darkens or lightens the
  palette color until it reaches 4.5:1 against the page, and picks black or
  white header text, whichever reads better. `just site-check` shows the
  final colors. The docs site uses Material's own pairings, which for a few
  light palettes (cyan, light-green, and similar) put white text under 3:1
  on the header; prefer a darker palette if the docs header must be
  readable.
- Ask the person before changing an established color. It is part of how
  people recognize the site.

## Beyond the settings

The browser is rendered from Jinja templates in
`src/ingestmech/templates/`:

| File | Page |
|---|---|
| `index.html` | the front page table |
| `record.html` | one record; the `show` macro draws each section |
| `style.css` | the stylesheet; colors arrive as variables from `conf/site.yaml` |

Rules:

- Keep colors in `conf/site.yaml`. In `style.css`, use the `var(--...)`
  names, never a new literal color.
- Keep every link relative. The site is hosted under a path, and the
  record browser sits inside the docs site at `/records/`.
- Keep output deterministic: no dates or random values in templates, or
  `just render-check` will always fail.
- After editing a template, `just render`, look at the result with
  `just docs-serve`, and commit `pages/` with the template.

The docs site's layout is `mkdocs.yml`; its pages are `docs/`. Never edit
`.mkdocs.site.yml`, `site/`, or `docs/records/`: they are generated.

If a request needs a setting that does not exist yet (a logo, a second
table layout), add it to `conf/site.yaml`, read it in `site.py` and the
templates, document it in this skill, and say so in the pull request.
