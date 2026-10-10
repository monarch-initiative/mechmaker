# Deep research

Reports written by `just research PROVIDER TARGET`, through
[deep-research-client](https://pypi.org/project/deep-research-client/).

```
research/<stem>-deep-research-<provider>.md              the report
research/<stem>-deep-research-<provider>.md.citations.md its citations
research/templates/record.md                             the question every report answers
```

## What a report is for

A report is a lead, never a source. It suggests what a
ZIP code area record could say and where the evidence might be. It does not
go into a record, and a record never cites it.

To use a report:

1. Read it, and its `## Reference Validation` and `## Term Validation`
   sections at the end. A citation marked not found, or a term whose label
   does not match, is a sign the report is wrong there.
2. For each claim worth keeping, fetch the primary source it cites:
   `just fetch-reference PMID:NNN`. Read that source.
3. Write the claim into the record with a verbatim quote from the source,
   as for any other claim. If the source does not say it, the claim is not
   written.
4. Record the report as a source in the history record's `--details`: the
   file, the provider and the model (both in its frontmatter).

## Rules

- Reports are committed: they are provenance, and a provider run can cost
  real money.
- Never edit a report by hand. Its frontmatter records what produced it.
- `just research` refuses to overwrite a report. Pass `--force` only when a
  new run is really wanted.
- Exit code 3 means the report was saved and its checks found problems. Do
  not rerun the provider; read the report, or rerun only the checks with
  `just research-validate <report>`.
