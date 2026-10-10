---
reference_id: url:https://raw.githubusercontent.com/monarch-initiative/go-ingest/fe6ed785b3484ee879c5ca0b4ed0a2b6bea5d3ca/README.md
extractor_version: 1
url_source_version: 1
title: "https://raw.githubusercontent.com/monarch-initiative/go-ingest/fe6ed785b3484ee879c5ca0b4ed0a2b6bea5d3ca/README.md"
content_type: url
---

# https://raw.githubusercontent.com/monarch-initiative/go-ingest/fe6ed785b3484ee879c5ca0b4ed0a2b6bea5d3ca/README.md

## Content

# Gene Ontology Annotations

[Gene Ontology](http://geneontology.org/) provides annotations linking genes to GO terms describing molecular functions, biological processes, and cellular components.

Data is downloaded from: `http://current.geneontology.org/annotations/gaf/`

### Species Included

- Human (NCBITaxon:9606)
- Mouse (NCBITaxon:10090)
- Rat (NCBITaxon:10116)
- Dog (NCBITaxon:9615)
- Pig (NCBITaxon:9823)
- Cow (NCBITaxon:9913)
- Chicken (NCBITaxon:9031)
- Zebrafish (NCBITaxon:7955)
- Fruit fly (NCBITaxon:7227)
- Baker's yeast (NCBITaxon:4932)
- Fission yeast (NCBITaxon:4896)
- C. elegans (NCBITaxon:6239)
- Dictyostelium (NCBITaxon:44689)

## Gene to GO Term Associations

This ingest uses GAF (Gene Association Format) files, one per species, to produce gene-to-GO term associations. The GO aspect determines the association type:

- **Molecular Activity** (Aspect F) — `MacromolecularMachineToMolecularActivityAssociation`
- **Biological Process** (Aspect P) — `MacromolecularMachineToBiologicalProcessAssociation`
- **Cellular Component** (Aspect C) — `MacromolecularMachineToCellularComponentAssociation`

### Predicate Mapping

The predicate is determined by the GO qualifier column. Default predicates by aspect:

| Aspect | Default Predicate |
|--------|-------------------|
| F (Molecular Function) | `biolink:enables` |
| P (Biological Process) | `biolink:actively_involved_in` |
| C (Cellular Component) | `biolink:is_active_in` |

Qualifiers in the GAF file override these defaults (e.g. `contributes_to`, `acts_upstream_of`, `part_of`, `located_in`, `colocalizes_with`, `acts_upstream_of_or_within`, etc.). Annotations with "NOT" qualifiers are captured with `negated: true`.

### Biolink Captured

- `biolink:MacromolecularMachineToMolecularActivityAssociation` / `...ToBiologicalProcessAssociation` / `...ToCellularComponentAssociation`
    - id (UUID)
    - subject (gene ID)
    - predicate (mapped from qualifier, see above)
    - negated (true when qualifier starts with "NOT")
    - object (GO term ID)
    - has_evidence (ECO term)
    - publications (from GAF reference column)
    - species_context_qualifier (NCBITaxon ID)
    - primary_knowledge_source (derived from GAF Assigned_By column)
    - aggregator_knowledge_source (`["infores:monarchinitiative"]`)
    - knowledge_level (`knowledge_assertion`)
    - agent_type (`manual_agent`)

## Citation

Ashburner et al. Gene ontology: tool for the unification of biology. Nat Genet. 2000 May;25(1):25-9. The Gene Ontology Consortium. The Gene Ontology knowledgebase in 2023. Genetics. 2023 May 4;224(1):iyad031

## License

MIT
