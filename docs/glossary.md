# Glossary

| Word | Meaning |
|---|---|
| **Mech** | A knowledge base in the DisMech pattern: one record per thing, standard vocabulary, quoted evidence, full history, human review |
| **Record** | One entry in the knowledge base, stored as one YAML file |
| **YAML** | A plain text format for structured data, readable by people |
| **Schema**, **data model** | The rules for what a record may contain, written in LinkML |
| **LinkML** | A language for describing data models, with tools that validate data and generate documentation |
| **Ontology** | A curated, standard vocabulary for a field, like the Gene Ontology |
| **CURIE** | A short identifier for a term, like `GO:0008150` |
| **Descriptor** | A mention of something in a record: a preferred name, an optional ontology term, and evidence |
| **Dynamic enum** | A rule that a term must come from one part of an ontology, below a root term |
| **Evidence**, **snippet** | A citation, and the exact sentence quoted from it |
| **Curation history** | The log of who changed a record, when and why |
| **Skill** | Written instructions an AI agent follows for one kind of task |
| **Copier** | The tool that turns this template into a new repository |
| **Workflow** | An automated job that GitHub runs, such as checks on every pull request |
| **Pull request** | A proposed change on GitHub that people review before it is accepted |
| **MechRegistry** | The public list of Mechs |
| **Fleet** | A set of Mechs, each in its own repository, whose records link to each other's through declared relationships |
| **Coordinator** | A Fleet's own repository: the members and relationships (`fleet.yaml`), the files every member shares, and the checks that read the members together. It holds no records |
| **Relationship** | In a Fleet, a declared way for one member's records to link to another's: a slot, its relations and its bases |
| **CrossCorpusLink** | A link from a record in one Mech to a record in another: the target Mech, the target record, a relation, a basis, and the target's commit that was checked |
| **Canon** | The files every member of a Fleet carries byte for byte, kept in the Coordinator |
| **Pin** | A Fleet member's `fleet/pin.yaml`: the Coordinator commit its canon came from |
