Research the following {record_noun} for a curated knowledge base.

Name: {name}
Identifier: {id} {label}
Other names: {synonyms}

The knowledge base is DaTMech: DaTMech records US ZIP code areas by their water: the watersheds they drain to, the plants that treat their drinking water and wastewater, and the incidents that have harmed its safety or quality, with every claim quoted from its source.

Report what the published evidence says about this ZIP code area, section
by section. For every statement:

- cite the primary source that states it: a paper by its PMID or DOI, a
  government, utility or news page by its URL;
- quote the sentence from that source that supports it, word for word;
- say plainly where sources disagree, or where nothing was found.

Where an ontology term fits a statement, give its CURIE and its exact label.
Do not invent identifiers. An uncertain statement is more useful marked
uncertain than left out, and more useful left out than stated as fact.
Sections, in the order a DaTMech record is filled (docs/DOMAIN.md):

1. The area: the place the Postal Service names for the ZIP code, its
   state, and its 2020 Census ZIP Code Tabulation Area.
2. Watersheds: the USGS hydrologic units (HUC8 and HUC12 codes and names)
   the area drains to, and their main rivers and lakes.
3. Drinking water: the public water systems that serve the area, with
   EPA PWSID, the treatment plants, whether each serves now, as a backup
   or did once, the source type (surface water, groundwater, purchased)
   and the water bodies or aquifers drawn from.
4. Wastewater: the plants that treat the area's wastewater, with NPDES
   permit, and the water bodies they discharge to.
5. Incidents: every event that harmed or threatened the safety or
   quality of the area's water (contamination, treatment failure, spill,
   toxic bloom, outbreak, infrastructure failure). For each: dates as
   precise as the sources allow, cause, contaminants (chemical names),
   organisms (species names), the water bodies and plants involved, and
   each advisory to the public (boil water, do not drink, bottled water,
   declared emergency) with who issued it, when it began and ended, and
   how many people it covered. Say which incidents the area was spared.
6. Open questions and disagreements: dates, numbers or causes the
   sources give differently.
7. The most useful primary sources, with one line on what each contains.
