---
name: add-record-map
description: >-
  Give a Mech's record pages a map: add bounding boxes to the schema for
  the places records describe (areas, regions, watersheds, sites), fill
  them from a source with each box quoted, and let the record browser draw
  them on OpenStreetMap through Leaflet. Use when a person asks for a map
  in their record browser, or while designing a Mech whose records have a
  geography, where the map belongs by default. Not for maps outside the
  record browser.
---

# Add a map to record pages

The record browser draws a map on any record page whose record holds a
bounding box. It needs no setting and no schema name. A box is any object,
at any depth in a record, with four numbers in decimal degrees (WGS84):

```yaml
bounding_box:
  west: -83.696946
  south: 43.006408
  east: -83.679611
  north: 43.02246
  evidence: [...]
```

So the work is in the data. The browser and the checks come with the
template:

| What | Where | Does |
|---|---|---|
| finding boxes | `boxes()` in `src/<slug>/validate.py` | walks a record for objects with `west`, `south`, `east`, `north` |
| checking them | `box_errors()`, run by `just validate` | all four sides, numbers, in range, west no east of east, south no north of north |
| drawing them | `record.html`, from `render.py` | one rectangle per box, named by what holds it, colored by section, toggled in a list; a dot on a box too small to see |
| turning it off | `map: false` in `conf/site.yaml` | no maps anywhere |

A Mech made before this feature takes it with `sync-mech`.

DaTMech, in mechmaker's `example/datmech`, is a worked example: every ZIP
code area and watershed has a box quoted from a Census or USGS query.

## 1. Decide what has a box

A box belongs to a thing with an extent that a source states: an
administrative area, a postal or census area, a watershed, a protected
area, a sampling region, a range. One box per thing, on the object that
describes it, not one per record.

| Thing | Box? |
|---|---|
| An area a source draws (a county, a ZCTA, a watershed) | Yes: its extent |
| A point (a plant, a sample site, a city's center) | Not a box. If the person wants it on the map, a box with `west` = `east` and `south` = `north` draws as a dot; say so in the schema's description |
| A place known only by name, such as "northwest Ohio" | No. A box drawn by eye is a guess |
| Something across the antimeridian (west of 180° and east of it) | Not supported: west must not be east of east |

Ask the person when a record's geography is unclear. Do not add a box
because the domain is spatial in general.

## 2. Add the class to the schema

In the Mech, with its `extend-schema` skill: one class, and a
`bounding_box` slot on each class that describes a place. The four names
are fixed; the browser and the checks look for them.

```yaml
classes:
  BoundingBox:
    description: >-
      The smallest box, in decimal degrees (WGS84), that holds an area: the
      extent its source reports, rounded to six decimals. The record browser
      draws every one on a map.
    slots: [west, south, east, north, evidence]
    slot_usage:
      west: {required: true}
      south: {required: true}
      east: {required: true}
      north: {required: true}

slots:
  bounding_box:
    range: BoundingBox
    inlined: true
    recommended: true
    description: The area's extent, from the source that defines the area; drawn on the record's map.
  west: {range: float, minimum_value: -180, maximum_value: 180, description: Westernmost longitude, decimal degrees.}
  south: {range: float, minimum_value: -90, maximum_value: 90, description: Southernmost latitude, decimal degrees.}
  east: {range: float, minimum_value: -180, maximum_value: 180, description: Easternmost longitude, decimal degrees.}
  north: {range: float, minimum_value: -90, maximum_value: 90, description: Northernmost latitude, decimal degrees.}
```

Write it in `docs/DOMAIN.md` too: which objects carry a box, and from what
source.

## 3. Fill each box from a source, quoted

A box is a claim like any other. It comes from a source that states the
extent, and its evidence quotes the numbers. Never compute one from
memory, from a map, or from a list of coordinates you made up.

**An ArcGIS layer** (Census TIGERweb, the USGS Watershed Boundary Dataset,
many state and federal GIS services) reports the extent of any query. A
script comes with this skill, in the `scripts/` folder beside this file;
`<scripts>` stands for that folder's path. It needs only Python 3:

```bash
python3 <scripts>/arcgis_extent.py <layer URL> "<where clause>"
python3 <scripts>/arcgis_extent.py https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/4 "huc8='04080204'"
```

It prints a `bounding_box` with its sides rounded to six decimals and one
evidence item: the query URL as a `url:` reference, and the extent exactly
as the service wrote it as the snippet. Set `evidence_source` to the Mech's
own value, paste it into the record, and run `just validate`, which fetches
the URL and checks the quote. Exit 1 means the clause selects nothing.
Find the layer's field names at `<layer URL>?f=pjson`.

**Other sources.** A dataset's own metadata, a gazetteer, or a paper that
states coordinates. Quote the numbers as the source writes them, and say
in `explanation` how they map to the four sides. Watch the order:
OpenStreetMap's Nominatim gives `boundingbox` as south, north, west, east,
and its data is under the ODbL, which asks for attribution. GeoJSON and
most GIS tools give west, south, east, north.

Keep the numbers as text when copying them. A float loses digits
(-83.696946000250492 prints as -83.69694600025049), and the quote then
fails.

## 4. Look at it

```bash
just validate data/<records>/<record>.yaml   # the box, its sides, its quote
just docs-serve                              # the record page, with its map
```

Look at a record page at desktop and phone widths. A small box inside a
large one (a postal area inside its watershed) gets a dot; the layer list
folds into a button on a narrow map.

## Settings and limits

- Maps are on by default. `map: false` in `conf/site.yaml` turns them off;
  the boxes stay in the data and on the page as text.
- The page loads Leaflet 1.9.4 from unpkg, pinned with an integrity hash,
  and tiles from OpenStreetMap. A visitor without JavaScript, or offline,
  sees the boxes as text in their sections.
- OpenStreetMap's tile policy
  (https://operations.osmfoundation.org/policies/tiles/) asks for the
  attribution the map shows and for light use. A Mech whose site will get
  heavy traffic should point the tile layer in `record.html` at its own or
  a paid tile service.
- Boxes are in WGS84 (EPSG:4326). A source in another reference system
  must be asked for WGS84 (`outSR=4326` on ArcGIS) or not used.
