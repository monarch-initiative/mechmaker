# Already have a knowledge base?

You can turn it into a Mech. mechmaker does not convert data on its own
yet, so plan on some work, most of which an agent can do for you. A
dedicated conversion skill is planned
([issue #1](https://github.com/monarch-initiative/mechmaker/issues/1)).

## The usual path

1. **Start a new Mech** for the same topic, as in
   [Getting started](getting-started.md). Keep the existing knowledge base
   where it is. It becomes a source for the new one.
2. **Shape the data model to fit what you have.** Ask the agent to run the
   [`design-mech-schema`](skills/design-mech-schema.md) skill and point it
   at your data. Your current fields tell it which sections a record needs.
3. **Write a conversion script** that reads your data and writes one Mech
   record per entry. The new Mech includes a helper,
   `write_validated_record`, that refuses to save a record that fails the
   checks. Converted records start as `DRAFT`.
4. **Bring the evidence up to standard.** This is usually the biggest job.
   A Mech needs each claim to quote its source word for word. If your
   knowledge base already cites papers, the agent can fetch each one and
   find the supporting sentence. Claims with no source become open questions
   in the record, and are kept, not thrown away.
5. **Review in batches.** Send converted records through pull requests a
   few dozen at a time, so people can actually read them.

## A good first request

> I have a knowledge base of X at (path or URL). Survey it, then make a Mech
> that can hold it, and convert five entries as a trial.

Try a handful of entries before converting everything. Problems with the
data model are cheap to fix with five records and costly with five
thousand.
