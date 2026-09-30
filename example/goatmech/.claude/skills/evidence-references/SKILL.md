---
name: evidence-references
description: >-
  Find, fetch, quote and validate the evidence behind a GoatMech claim.
  Use when adding or fixing an `evidence` item, when a snippet fails
  reference validation, when choosing between sources, or when asked whether
  a claim is supported.
---

# Evidence and references

Every evidence item is checked by `linkml-reference-validator`. It fetches
the cited source, caches it under `references_cache/`, and requires the
snippet to appear in it verbatim.

## Writing an item

1. Find a primary source that states the claim. Prefer the paper that
   showed it over a review that repeats it.
2. Fetch it and read it:

   ```bash
   just fetch-reference PMID:<n>
   ```

3. Copy the snippet from the fetched text. `...` joins two exact spans.
   `[...]` marks an editorial note. Nothing else may differ.
4. Fill the item:

   ```yaml
   - reference: PMID:<n>
     reference_title: <as fetched>
     supports: SUPPORT
     evidence_source: <EvidenceSourceEnum value>
     snippet: <verbatim>
     explanation: <how it bears on the claim>
   ```

5. Validate:

   ```bash
   just validate-references data/goat_breeds/<stem>.yaml
   ```

## `supports`

| Value | When |
|---|---|
| `SUPPORT` | The quote states or directly shows the claim. |
| `PARTIAL` | It supports part of the claim, or with a caveat that matters. |
| `REFUTE` | It contradicts the claim. Keep it. Open a `CONTROVERSY` discussion. |
| `NO_EVIDENCE` | Relevant context that does not bear on the claim. |
| `WRONG_STATEMENT` | The claim was found wrong. Kept for provenance. |

## When validation fails

- **Snippet not found.** Your quote differs from the source. Fetch again and
  copy. If the text is in the full paper but only the abstract is cached,
  quote the abstract or find an open-access copy. Do not paraphrase.
- **Reference not found.** The identifier is wrong. Search PubMed for the
  title. Never adjust digits until something resolves.
- **Unknown prefix.** The reference type is not supported by the validator.
  Use a PMID or DOI for the same work.

## When no source exists

Do not reach. Write the claim as a `KNOWLEDGE_GAP` discussion with
`rationale` saying what evidence would settle it. Sketch a
`proposed_experiments` entry if one is obvious.
