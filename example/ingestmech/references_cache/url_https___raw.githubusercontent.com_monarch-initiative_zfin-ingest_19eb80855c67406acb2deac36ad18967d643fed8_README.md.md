---
reference_id: url:https://raw.githubusercontent.com/monarch-initiative/zfin-ingest/19eb80855c67406acb2deac36ad18967d643fed8/README.md
title: "https://raw.githubusercontent.com/monarch-initiative/zfin-ingest/19eb80855c67406acb2deac36ad18967d643fed8/README.md"
content_type: url
---

# https://raw.githubusercontent.com/monarch-initiative/zfin-ingest/19eb80855c67406acb2deac36ad18967d643fed8/README.md

## Content

# ZFIN

ZFIN is the Zebrafish Model Organism Database.

- [ZFIN bulk downloads](https://zfin.org/downloads)

## Gene to Phenotype

This ingest uses ZFIN's clean gene phenotype download file, which only contains phenotypes which can safely be associated to a single affected gene. This ingest is distinct from the Alliance phenotype index because ZFIN builds Entity-Quality-Entity phenotype statements that can be built from post-composed terms (E1a+E1b+Q+E2a+E2b).

**Biolink captured:**

* biolink:Gene
    * id

* biolink:PhenotypicFeature
    * id

* biolink:GeneToPhenotypicFeatureAssociation
    * id (random uuid)
    * subject (gene.id)
    * predicate (has_phenotype)
    * object (phenotypicFeature.id)
    * publications
    * aggregating_knowledge_source (["infores:monarchinitiative"])
    * primary_knowledge_source (infores:zfin)

## Genotype to Phenotype

Phenotype associations at the genotype level, including complex genotypes with multiple affected genes.

**Biolink captured:**

* biolink:Genotype
    * id

* biolink:PhenotypicFeature
    * id

* biolink:GenotypeToPhenotypicFeatureAssociation
    * id (random uuid)
    * subject (genotype.id)
    * predicate (has_phenotype)
    * object (phenotypicFeature.id)
    * publications
    * aggregating_knowledge_source (["infores:monarchinitiative"])
    * primary_knowledge_source (infores:zfin)

## Orthology

Ortholog associations between ZFIN zebrafish genes and genes from other organisms.

**Biolink captured:**

* biolink:Gene
    * id

* biolink:GeneToGeneHomologyAssociation
    * id (random uuid)
    * subject (gene.id)
    * predicate (orthologous_to)
    * object (gene.id)
    * aggregating_knowledge_source (["infores:monarchinitiative"])
    * primary_knowledge_source (infores:zfin)

## Citation

Bradford, Y.M., Van Slyke, C.E., Ruzicka, L., Singer, A., Eagle, A., Fashena, D., Howe, D.G., Frazer, K., Martin, R., Paddock, H., Pich, C., Ramachandran, S., Westerfield, M. (2022) Zebrafish Information Network, the knowledgebase for Danio rerio research. Genetics. 220(4).

## License

BSD-3-Clause
