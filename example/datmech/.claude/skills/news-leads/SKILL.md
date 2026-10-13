---
name: news-leads
description: >-
  Search the news about a ZIP code area, past and new, and turn what
  it reports into quoted evidence: run `just news-leads`, tune the searches
  in conf/news.yaml, read the ranked leads, and quote archived copies of the
  stories. Use when a record's events are the kind local news reports, when
  a record's known gap is something a news story would settle, when a `news`
  issue arrives, or when asked to search the news for a record.
---

# News leads

Papers cover what researchers study. Many events never reach them, and local
news reports them. `just news-leads <record>` searches a record's past news
and writes ranked leads to `curation/news/<stem>.md`.

**A lead is never evidence.** Never cite `curation/news/` or a `news` issue,
and never write a claim from a headline. Read the story's archived copy and
quote it, like any other source.

## 1. The searches

`conf/news.yaml` says which record fields name a ZIP code area in the
news, where its dated events are, and which words to search with. The
record supplies the values. See what a record gets:

```bash
just news-plan <stem>
```

Each search is printed with its date window and why it exists. Read it
before searching:

- **The subject.** `subject.fields` names it: the first field set is
  quoted in every search. Add `qualifier_fields` when the name alone is
  ambiguous (a town name shared by several states), with `qualifier_map`
  to turn codes into the words news uses.
- **The topic.** `topic` words go in every search, so that stories about
  the subject but not the domain stay out.
- **Events.** With `events.field` set, each event gets a search in a
  window around its dates, with its `terms`: a field's values (a
  contaminant's name), or, through a `map`, the words news uses for a coded
  value (`SPILL` becomes `spill`, `chemicals`).
- **Discovery.** One search per recent year, with `discovery.words`, for
  events the record lacks. Stories about events it already has rank lower
  here. When one famous old event crowds out the rest, put its name in
  `discovery.exclude`.
- **Wikipedia.** Each `WIKIPEDIA:` reference the record cites is read for
  the news it cites: the best-curated news there is, often already archived.

Change `conf/news.yaml`, not a record, to change the searches. For a
one-off, save the plan, edit it, and run it:
`just news-plan <stem> > /tmp/plan.json`, then
`just news-leads --plan /tmp/plan.json --out curation/news/<stem>.md`.

## 2. Find leads

```bash
just news-leads <stem>
```

It counts first: every search runs once, and its number of hits is
printed. Google News answers about 100 items at most, so a search at that
cap is split in two by date (up to `max_splits` times, never below a month); one still at the
cap is too broad, and says so. Then it keeps each search's `per_search`
most promising leads (the subject in the title, more `rank` words, an
archived copy already known, newer), counts the rest, and looks up an
existing Wayback Machine snapshot for the kept ones. It never asks the
archive to save anything.

A search with hundreds of hits and nothing useful on top needs better
words, not more reading: tighten `topic` or the event's `terms`, and run
again.

## 3. Read and quote

For each lead worth reading, best first:

1. **Find the article.** A Wikipedia lead has its URL. A Google lead has a
   title and an outlet: search for them. A story is often republished; any
   copy with a snapshot will do.
2. **Use an archived copy.** News sites refuse scripts and move stories.
   Cite the snapshot: `url:https://web.archive.org/web/<timestamp>/<article URL>`.
   If none exists, the lead waits; tell the person, who may choose to
   archive it.
3. **Fetch and read it** with `just fetch-reference url:<snapshot>`. Quote a
   sentence within one paragraph that runs through no link.
4. **Add the evidence** with `just add-evidence`.

Read news as a source with a date and a point of view. "Officials said"
reports an agency's statement: prefer the agency's own notice. Take the date
from the article, not the lead. Prefer the latest report of a figure. When
two reports differ, record both and open a `CONTROVERSY` discussion.

## Record it

Commit the leads file beside the records it served: it shows what was
searched, when, and what was not yet read. The record's history event
names the searches. A gap a lead could settle but no archived copy supports
stays a `KNOWLEDGE_GAP`, with the lead named in its rationale.

No lead is not evidence that nothing happened: coverage is uneven, and
Google News' search feed is not an API; it may change.
