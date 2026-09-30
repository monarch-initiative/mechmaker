---
reference_id: url:https://raw.githubusercontent.com/monarch-initiative/omim-ingest/de31fd083c8fd894eda3767085fa0452f581298c/README.md
title: "https://raw.githubusercontent.com/monarch-initiative/omim-ingest/de31fd083c8fd894eda3767085fa0452f581298c/README.md"
content_type: url
---

# https://raw.githubusercontent.com/monarch-initiative/omim-ingest/de31fd083c8fd894eda3767085fa0452f581298c/README.md

## Content

# OMIM

[OMIM](https://omim.org/) (Online Mendelian Inheritance in Man) is a comprehensive database of human genes and genetic phenotypes, with a particular focus on the molecular relationship between genetic variation and phenotypic expression.

Data is downloaded from OMIM's data portal (requires access key): the `morbidmap.txt` file which maps diseases to their associated genes.

## Gene to Disease

Each row in morbidmap represents a disease-gene association with a confidence level (1-4) and an optional susceptibility marker `{}`. These are used to determine the association type and predicate:

| Confidence Level | Susceptibility | Association Type | Predicate |
|---|---|---|---|
| 3 (molecular basis known) | No | `CausalGeneToDiseaseAssociation` | `biolink:causes` |
| 1 or 2 (mapped gene/phenotype) | No | `CorrelatedGeneToDiseaseAssociation` | `biolink:contributes_to` |
| Any | Yes `{}` | `CorrelatedGeneToDiseaseAssociation` | `biolink:contributes_to` |
| 4 (chromosomal abnormality) | — | Skipped | — |

**Biolink Captured:**

- `biolink:CausalGeneToDiseaseAssociation`
    - id (UUID)
    - subject (`OMIM:{gene_mim}`)
    - predicate (`biolink:causes`)
    - object (`OMIM:{disease_mim}`)
    - primary_knowledge_source (`infores:omim`)
    - aggregator_knowledge_source (`infores:monarchinitiative`)
    - knowledge_level (`not_provided`)
    - agent_type (`not_provided`)

- `biolink:CorrelatedGeneToDiseaseAssociation`
    - id (UUID)
    - subject (`OMIM:{gene_mim}`)
    - predicate (`biolink:contributes_to`)
    - object (`OMIM:{disease_mim}`)
    - primary_knowledge_source (`infores:omim`)
    - aggregator_knowledge_source (`infores:monarchinitiative`)
    - knowledge_level (`not_provided`)
    - agent_type (`not_provided`)

## Citation

Amberger JS, Bocchini CA, Scott AF, Hamosh A. OMIM.org: leveraging knowledge across phenotype-gene relationships. Nucleic Acids Research. 2019;47(D1):D1038-D1043. doi: 10.1093/nar/gky1151. PMID: 30445645

## License

BSD-3-Clause
