# Curating GoatMech

## The loop

1. Pick a target. From the source queue, an issue, or a gap in `just report`.
2. Scaffold or open the record. `just new-record --id ... --name ... --apply`.
3. Research. Fetch every source you cite: `just fetch-reference PMID:NNN`.
   Read what came back. For a thin record in a large literature,
   `just research PROVIDER <stem>` writes a deep-research report to
   `research/`: a list of leads to check, never a source to cite.
4. Write. Terms through `just search-term` and `just term-info`. Quotes
   copied from the fetched text and added with `just add-evidence`, which
   checks each quote against its source before writing it.
5. Validate. `just fill-titles data/goat_breeds/<stem>.yaml --apply` fills
   any missing `reference_title` from the cache. Then
   `just validate data/goat_breeds/<stem>.yaml` until clean.
6. Record. Append a `curation_history` event to the record. Add a history
   record with `just new-history ... --apply`.
7. Open a pull request. A person reviews it.

## Evidence

Every claim that could be wrong carries evidence:

```yaml
evidence:
  - reference: PMID:<number>
    reference_title: <title, as fetched>
    supports: SUPPORT        # SUPPORT, REFUTE, PARTIAL, NO_EVIDENCE, WRONG_STATEMENT
    evidence_source: IN_VITRO
    snippet: <exact text from the abstract or full text>
    explanation: <how the quote bears on the claim, in your words>
```

- The snippet is checked verbatim against the cached source. `...` marks
  omitted text between two exact spans. `[...]` marks an editorial note.
  Nothing else may differ from the source.
- Cite the source that states the claim, not a review that cites a review.
- `REFUTE` evidence is kept. A record that shows disagreement is better
  than one that hides it. Open a `CONTROVERSY` discussion.
- No source found? Say so. Open a `KNOWLEDGE_GAP` discussion. Do not reach.

## Terms

- Search, then inspect. Read the definition and the parents before you bind.
- The label is copied from the ontology. `preferred_term` says it your way.
- A term that is not under the enum root fails validation. That usually
  means the wrong term, not the wrong root.
- A missing term is a finding. Record it as a `CURATION_TODO` and consider
  a new-term request to the ontology.

## Status

`DRAFT`, then `PROPOSED` when complete and valid, then `REVIEWED` when a
person accepts it. Agents never set `REVIEWED`. `DEPRECATED` keeps a record
for provenance.
