---
reference_id: url:https://raw.githubusercontent.com/monarch-initiative/go-ingest/fe6ed785b3484ee879c5ca0b4ed0a2b6bea5d3ca/download.yaml
title: "https://raw.githubusercontent.com/monarch-initiative/go-ingest/fe6ed785b3484ee879c5ca0b4ed0a2b6bea5d3ca/download.yaml"
content_type: url
---

# https://raw.githubusercontent.com/monarch-initiative/go-ingest/fe6ed785b3484ee879c5ca0b4ed0a2b6bea5d3ca/download.yaml

## Content

### This file is a YAML configuration that specifies
### the data to be downloaded and ingested for this project.
### The configuration is used by `kghub-downloader`.
### For more information, see https://github.com/monarch-initiative/kghub-downloader
---

# GO evidence mapping codes
- url: https://raw.githubusercontent.com/evidenceontology/evidenceontology/master/gaf-eco-mapping.txt
  local_name: data/gaf-eco-mapping.txt

# NOTE: As of the June 2026 GO pipeline migration (geneontology/go-announcements#1153)
# annotation files live under /annotations/gaf/ and are named with UniProt mnemonic
# organism codes. MOD-submitted species use the `-mod` (MOD ID-centric) variant to
# preserve MOD-namespace gene identifiers; UniProt-mediated species use `-uniprot`.

# Homo sapiens (human)
- url: http://current.geneontology.org/annotations/gaf/HUMAN-uniprot.gaf.gz
  local_name: data/9606.go_annotations.gaf.gz
  tag: go_annotation

# Mus musculus (house mouse)
- url: http://current.geneontology.org/annotations/gaf/MOUSE-mod.gaf.gz
  local_name: data/10090.go_annotations.gaf.gz
  tag: go_annotation

# Rattus norvegicus (Norway rat)
- url: http://current.geneontology.org/annotations/gaf/RAT-mod.gaf.gz
  local_name: data/10116.go_annotations.gaf.gz
  tag: go_annotation

# Canis lupus familiaris (dog)
- url: http://current.geneontology.org/annotations/gaf/CANLF-uniprot.gaf.gz
  local_name: data/9615.go_annotations.gaf.gz
  tag: go_annotation

# Bos taurus (cow)
- url: http://current.geneontology.org/annotations/gaf/BOVIN-uniprot.gaf.gz
  local_name: data/9913.go_annotations.gaf.gz
  tag: go_annotation

# Sus scrofa (pig)
- url: http://current.geneontology.org/annotations/gaf/PIG-uniprot.gaf.gz
  local_name: data/9823.go_annotations.gaf.gz
  tag: go_annotation

# Gallus gallus (chicken)
- url: http://current.geneontology.org/annotations/gaf/CHICK-uniprot.gaf.gz
  local_name: data/9031.go_annotations.gaf.gz
  tag: go_annotation

# Danio rerio (Zebrafish)
- url: http://current.geneontology.org/annotations/gaf/DANRE-mod.gaf.gz
  local_name: data/7955.go_annotations.gaf.gz
  tag: go_annotation

# Drosophila melanogaster (fruit fly)
- url: http://current.geneontology.org/annotations/gaf/DROME-mod.gaf.gz
  local_name: data/7227.go_annotations.gaf.gz
  tag: go_annotation

# Caenorhabditis elegans (nematodes)
- url: http://current.geneontology.org/annotations/gaf/CAEEL-mod.gaf.gz
  local_name: data/6239.go_annotations.gaf.gz
  tag: go_annotation

# Dictyostelium discoideum
- url: http://current.geneontology.org/annotations/gaf/DICDI-mod.gaf.gz
  local_name: data/44689.go_annotations.gaf.gz
  tag: go_annotation

# Saccharomyces cerevisiae (baker's yeast)
- url: http://current.geneontology.org/annotations/gaf/YEAST-mod.gaf.gz
  local_name: data/4932.go_annotations.gaf.gz
  tag: go_annotation

# Schizosaccharomyces pombe (fission yeast)
- url: http://current.geneontology.org/annotations/gaf/SCHPO-mod.gaf.gz
  local_name: data/4896.go_annotations.gaf.gz
  tag: go_annotation
