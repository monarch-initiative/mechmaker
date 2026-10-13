---
name: ingest-news
description: >-
  Set a Mech up to curate from news reports: turn on mechmaker's news
  feature (`news_leads`, and the weekly `news-watch` workflow), write the
  Mech's conf/news.yaml so its records' own fields drive the searches, and
  prove it on a few records. Use when a person wants a Mech that draws on
  the news, when records are about events local news covers and papers may
  never report (incidents, outbreaks, spills, closures, recalls), or when
  a record's known gap is something a news story would settle. Day-to-day
  curation from the leads is the Mech's own `news-leads` skill.
---

# Curate from news reports

Papers cover what researchers study. Many events never reach them: a
boil-water notice, a spill into a creek, a plant shut for a week. Local
news does. mechmaker's news feature gets those reports into a Mech without
lowering its evidence rule: every claim still quotes a source the
validator can fetch, and a lead is never evidence.

| Step | Who | Output |
|---|---|---|
| 1. Decide | you and the person | whether the Mech's records are news events |
| 2. Turn it on | Copier | `news.py`, `conf/news.yaml`, recipes, the `news-leads` skill |
| 3. Configure | you | `conf/news.yaml`, written for the record type |
| 4. Prove it | you | leads for three records, in `curation/news/` |

DaTMech, in mechmaker's `example/datmech`, is the worked example: its
`conf/news.yaml` searches a ZIP code area's place, state and incidents, and
its `curation/news/` holds the leads three records got.

## 1. Decide

News is worth it when a record's facts are events with dates that local
news reports: incidents, outbreaks, recalls, closures, disasters. It adds
little when records are things papers describe (genes, compounds, cell
types). Try one dated search for a known event before turning it on; the
survey (`survey-domain`) says whether news is a source.

## 2. Turn it on

For a new Mech, answer `news_leads: true` in `answers.yml`, and add
`news-watch` to `workflows` for the weekly watch. For an existing one:

```bash
uvx copier update --vcs-ref=:current: --skip-answered --defaults --data news_leads=true
```

That turns on the leads, not the weekly watch. For the watch too, pass the
Mech's whole `workflows` list from `.copier-answers.yml` with `news-watch`
added, as one more `--data`, such as
`--data 'workflows=[sweep, docs, comment-guard, news-watch]'`.

A Mech made before the feature existed takes it with `sync-mech` first.

**Coming from the old script.** A Mech that ran this skill's former
`news_leads.py` kept its searches in a plan builder under `scripts/`. Turn
the feature on as above, then move what the builder computed into
`conf/news.yaml` (step 3): the record fields it read for names and places
become `subject.fields` and `subject.qualifier_fields`, its topic words
`topic`, its event words `events.terms`, and its rank words `rank`. Compare its plans with `just news-plan <record>` on
a few records, then remove the builder and its tests. Leads already in
`curation/news/` stay where they are.
The Mech gets `src/<slug>/news.py`, `conf/news.yaml`, `curation/news/`,
`just news-leads`, `just news-plan` and `just news-watch`, its own
`news-leads` skill, and tests that run on canned feeds.

## 3. Configure

`conf/news.yaml` names record fields; each record supplies the values. Its
comments describe every setting. Decide, for this Mech's records:

- **What names a record in the news** (`subject.fields`): a place name, an
  outbreak's pathogen and place, a product's brand, a facility's name. Add
  `qualifier_fields` when the name alone is ambiguous (a town name in
  several states, a common brand word), with `qualifier_map` to turn codes
  into the words news uses.
- **What every story must be about** (`topic`): water, recall, outbreak.
- **Where the dated events are** (`events`): the list field, its name and
  date fields, and the words news uses for each (`terms`): a field's values
  as they are (a contaminant), or a `map` from a coded value to words
  (`SPILL` to `spill`, `chemicals`).
- **What a new event sounds like** (`discovery.words`): the domain's
  general event words, searched one recent year at a time.
- **Which cited news to keep** (`wikipedia.keywords`) and **what ranks a
  lead higher** (`rank`).

Records that are not places need only different fields. An outbreak:
`subject.fields: [pathogen.preferred_term]`, `qualifier_fields:
[location.name]`, `topic: [outbreak]`. A recall: `subject.fields: [brand]`,
`topic: [recall]`. A facility: `subject.fields: [name]`,
`qualifier_fields: [state]`.

Read `just news-plan <record>` after every change: it prints each search,
its window, and why it exists.

## 4. Prove it

Run `just news-leads <record>` on three records that span the corpus. It
counts each search's hits first (a search at Google's cap of about 100 is
split by date), keeps the 15 most promising leads of each, and looks up
archived copies for those only. Read the files in `curation/news/`:

- **A search at the cap, still split,** is too broad: tighten `topic` or
  the event's terms.
- **A search with hits and nothing useful on top** needs better words, not
  more reading.
- **A discovery search full of one famous old event:** stories about the
  record's own events already rank lower; if one still crowds the rest
  out, add its name to `discovery.exclude`.

Then hand over to the Mech's `news-leads` skill, which says how to read a
lead, find its archived copy, and quote it with `just add-evidence`.

## The weekly watch

The `news-watch` workflow reads a Google News search feed of each record's
words for the last week, in turns of `watch.max_records` records, and any
agency or utility feeds listed under `watch.feeds`, matching their items to
records by name. It files what is new as one `news` issue; stories already
in an earlier `news` issue are skipped. No model reads the news: matching
is by name, and the issue is filed by a step with no model.

## Limits

- Coverage is uneven. No lead is not evidence that nothing happened.
- Google News' search feed is not an API; it may change. Wikipedia's
  citations still run without it.
- GDELT gives article URLs but often refuses; it is off unless
  `sources` lists it.
