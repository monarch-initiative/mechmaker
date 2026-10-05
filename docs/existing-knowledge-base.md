# Already have a knowledge base?

You can turn it into a Mech. Ask your agent to run the
[`convert-knowledge-base`](skills/convert-knowledge-base.md) skill. The
[conversion walkthrough](walkthrough-conversion.md) shows one real run.

## What happens

1. **The agent surveys what you have.** It counts your entries and fields,
   checks a sample of your identifiers, and reads your license. If the
   license does not allow your content to be republished, it stops and
   asks you.
2. **It makes a Mech that can hold it.** Your fields become the starting
   point for the data model.
3. **It writes a conversion script.** The script reads your knowledge base
   and writes one record per entry through the Mech's checks. Every new
   Mech has a helper for this, `just convert`. It never overwrites a
   record, and it reports each entry it could not convert and why.
4. **It converts a few entries first.** Three to five, as a trial. Problems
   with the data model are cheap to fix with five records and costly with
   five thousand.
5. **It fills in what your knowledge base never recorded.** Each copied fact
   carries a quote of where it came from, so the checks can confirm it.
   Each gap is written into the record as work to do, and the agent curates
   what it can from other sources. What it cannot source stays marked as a
   gap.
6. **The rest goes in batches** of a few dozen records per pull request, so
   people can read them.
7. **It audits the result.** It checks the Mech against what you asked
   for and gives you a checklist of what is there, what is missing and
   why, and what to do next.

Your existing knowledge base stays where it is. The Mech lists it as the
source its records were derived from.

## A good first request

> I have a knowledge base of X at (path or URL). Use the
> convert-knowledge-base skill to make a Mech that can hold it, and convert
> five entries as a trial.
