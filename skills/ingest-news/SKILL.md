---
name: ingest-news
description: >-
  Curate a Mech's records from news reports: find articles about past
  events (months or years back, not just today's), keep them as leads,
  and turn what they say into quoted evidence from archived copies. Use
  when a person wants a Mech that draws on the news, when records are
  about events that local news covers and papers may never report
  (incidents, outbreaks, spills, closures, recalls), or when a record's
  known gap is something a news story would settle.
---

# Curate from news reports

Papers cover what researchers study. Many events never reach them: a
boil-water notice, a spill into a creek, a plant shut for a week. Local
news does. This skill gets those reports into a Mech without lowering its
evidence rule: every claim still quotes a source the validator can fetch.

| Step | Who | Output |
|---|---|---|
| 1. Plan the searches | you, from the record | a plan: queries, date windows, Wikipedia articles |
| 2. Find leads | script | a leads file per record |
| 3. Read and quote | you, with the Mech's `curate-record` | evidence from archived copies |
| 4. Record it | you | the leads file kept, the record's history |

DaTMech, in mechmaker's `example/datmech`, is a worked example: its
`scripts/news_plan.py` writes plans from its records, and its
`curation/news/` holds the leads each record got.

## Why not RSS

A feed gives the newest items. Curation needs the story from the week an
event happened, which may be years ago. RSS still suits watching for new
events, on a schedule; that is a different job from this one.

## 1. Plan the searches

A plan is JSON. Build it from what the record already knows, so the
searches are about this record and not the topic in general:

```json
{"label": "44413 East Palestine, Ohio",
 "searches": [{"query": "\"East Palestine\" \"Ohio\" water (spill OR \"vinyl chloride\")",
               "from": "2023-01-04", "to": "2024-02-03",
               "why": "Recorded incident: East Palestine train derailment"}],
 "wikipedia": ["East_Palestine,_Ohio,_train_derailment"],
 "keywords": ["water", "well", "bottled"],
 "place": ["East Palestine"],
 "rank": ["bottled", "drink", "well", "advisory", "spill", "vinyl chloride"],
 "known": ["url:https://...", "WIKIPEDIA:East_Palestine,_Ohio,_train_derailment"]}
```

- **One search per event the record has,** in a window from a little
  before it began to a while after it ended, with the words news uses for
  it: the place, then the kind of event and its specifics (the chemical,
  the advisory). Quote a phrase of several words, or it is searched as
  separate words.
- **One search per recent year for events the record lacks,** with the
  place and the general words for the domain's events. Yearly windows keep
  each search under the source's result limit.
- **Every Wikipedia article the record cites.** An article's own citations
  are the best-curated news there is, and many already have archived
  copies.
- **`known`:** every reference the record cites, so the leads it already
  used are marked.
- **`place` and `rank`:** the leads of each search are listed best first:
  a title that names the place, then one holding more of the `rank` words
  (the domain's event words and the record's specifics), then one with an
  archived copy. Searches return many leads (DaTMech's three records got
  139 to 762 each); ranking puts the few worth reading on top, and the rest
  are folded away.

For a Mech that will do this often, write a plan builder like DaTMech's,
in the Mech's `scripts/`: it reads a record and prints the plan.

## 2. Find leads

A script comes with this skill, in the `scripts/` folder beside this file;
`<scripts>` stands for that folder's path. It needs only Python 3, and
runs where it is.

```bash
python3 <scripts>/news_leads.py --plan plan.json --out curation/news/<record>.md
python3 <scripts>/news_leads.py --query '"Toledo" water microcystin' --from 2014-07-15 --to 2014-09-30 --out leads.md
```

| Source | Reaches | Gives | Limits |
|---|---|---|---|
| Google News search, with `after:`/`before:` | years back (2014 was checked) | title, outlet, date | no article URL: its link is a Google redirect. An unofficial use of a feed meant for news readers; it may change |
| GDELT article search | 2017 on | article URLs | asks for one request every 5 seconds, and may refuse far more (it refused every DaTMech search, HTTP 429). The script waits, retries once, and stops asking after two refusals |
| Wikipedia citations | any event with an article | title, outlet, date, URL, often an archived copy | only events with an article |

For each article with a URL, the script looks up an existing Wayback
Machine snapshot near its date (at most 40 per run; `--wayback N`). It
never asks the archive to save anything: that would publish a request to
an outside service on the person's behalf. A source that fails is named
at the top of the leads file; the rest still run.

The leads file is a table per search: date, outlet, title, archived copy,
and what found it. **A lead is not evidence.** Never cite the leads file,
and never write a claim from a headline.

## 3. Read and quote

For each lead worth reading, most promising first:

1. **Find the article.** A Wikipedia or GDELT lead has its URL. A Google
   lead has a title and an outlet: search for them. The same story is
   often republished (a public radio network's stations, a TV group's
   sites); any copy with a snapshot will do.
2. **Use an archived copy.** News sites often refuse scripted requests
   (403, 406), and stories move or vanish. Cite the snapshot, not the live
   page: `url:https://web.archive.org/web/<timestamp>/<article URL>`. Use
   that form, with the archive's toolbar; the raw `id_` form returns the
   stored bytes, which may be compressed and fail to fetch. If no snapshot
   exists, the lead waits; tell the person, who may choose to archive it.
3. **Fetch and read it** with `just fetch-reference url:<snapshot>`. Quote
   a sentence within one paragraph that runs through no link: the cache
   keeps the page's tags, so a quote across a link fails.
4. **Add the evidence** with the Mech's `just add-evidence`, with its
   evidence source set to its value for news (DaTMech's is `NEWS`).

Read news as a source with a date and a point of view:

- **Who says it.** "Officials said" quoting a named agency is a report of
  that agency's statement; prefer the agency's own notice when it can be
  found. A company handing out bottled water is not a public health
  advisory: record what was done and by whom.
- **When.** Take the date from the article, not the lead: a feed's date
  can be weeks off (DaTMech's Flint story was listed February 10 and is
  dated March 9 on its page). A story says "Saturday": work out the date
  from its own, and say so in `explanation`. Early reports carry early
  numbers; prefer the latest report that states a figure.
- **Start and end.** An advisory's start and its end are often in
  different stories. When a lead gives the start, search for the end
  ("lifted", "safe to drink") in the days after.
- **Disagreement.** When two reports differ on a date or a number, record
  both and open a `CONTROVERSY` discussion, as DaTMech's Toledo record does
  for its advisory's start.

## 4. Record it

Commit the leads file beside the records it served; it shows what was
searched and when, and what was not yet read. Each record's history event
names the searches. A gap a lead could settle but that no archived copy
supports stays a `KNOWLEDGE_GAP`, now with the lead named in its
rationale.

## Limits

- Coverage is uneven: big events have hundreds of stories, small ones a
  local paragraph or none. No lead is not evidence that nothing happened.
- The sources' terms change. Google News' search feed in particular is not
  an API; if it stops answering, the other sources still run.
- Paywalled stories may be archived only in part. Quote what the copy
  shows.
