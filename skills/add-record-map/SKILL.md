---
name: add-record-map
description: >-
  Give a Mech's record pages a map: add places to the schema for what
  records describe (points for sites, bounding boxes for areas, lines and
  outlines in Well-Known Text), fill them from a source with each quoted,
  and let the record browser draw them on OpenStreetMap through Leaflet.
  Use when a person asks for a map in their record browser, or while
  designing a Mech whose records have a geography, where the map belongs
  by default. Not for maps outside the record browser.
---

# Add a map to record pages

The record browser draws a map on any record page whose record holds a
place. It needs no setting. The schema says what a place is, not the
names of keys: a class is a shape when its slots say so, whatever the
class is called (`src/<slug>/shapes.py`).

| Shape | A class is one when it has | Drawn as | Standard |
|---|---|---|---|
| point | numeric `latitude` and `longitude` slots, or numeric slots with `slot_uri` `schema:latitude` and `schema:longitude` | a dot | schema.org `GeoCoordinates` |
| bounding box | numeric `west`, `south`, `east` and `north` slots | a rectangle | GeoJSON's `bbox` order (RFC 7946) |
| geometry | a slot with `slot_uri: geo:asWKT` | a line, polygon or dots | GeoSPARQL `geo:asWKT`, Well-Known Text |

Numeric means a range of `float`, `double`, `decimal` or `integer`, or a
type built on one. All coordinates are decimal degrees, WGS84. A slot
named `north` that holds a county's name is not a box side, because its
range is not a number.

```yaml
treatment_facilities:
  - name: Flint Water Plant
    location:
      latitude: 43.05512
      longitude: -83.65728
      evidence: [...]
bounding_box:
  west: -83.696946
  south: 43.006408
  east: -83.679611
  north: 43.02246
  evidence: [...]
reach:
  wkt: LINESTRING (-83.741 43.012, -83.702 43.018, -83.687 43.025)
  evidence: [...]
```

So the work is in the schema and the data. The browser and the checks
come with the template:

| What | Where | Does |
|---|---|---|
| finding shapes | `find()` in `src/<slug>/shapes.py` | walks a record along each slot's range from the record class |
| checking them | `errors()`, run by `just validate` | every part present and a number, in range; south no north of north; WKT that parses, rings closed |
| drawing them | `record.html`, from `render.py` | each shape as GeoJSON, named by what holds it, colored by section, toggled in a list; a dot on a line or area too small to see |
| turning it off | `map: false` in `conf/site.yaml` | no maps anywhere |

A Mech made before this feature takes it with `sync-mech`.

DaTMech, in mechmaker's `example/datmech`, is a worked example: every ZIP
code area and watershed has a box quoted from a Census or USGS query.

## 1. Decide what has a place, and which shape

A place belongs to a thing a source locates: a site, a facility, a sample,
an administrative area, a postal or census area, a watershed, a river
reach, a range. One place per thing, on the object that describes it.

| Thing | Shape |
|---|---|
| A site a source gives coordinates for (a plant, a well, a sample, a station) | point |
| An area a source gives the extent of (a county, a ZCTA, a watershed) | bounding box |
| A line a source traces (a river reach, a pipeline, a transect, a road) | geometry, `LINESTRING` |
| An outline a source publishes (a protected area, a plume, a study region) | geometry, `POLYGON` or `MULTIPOLYGON` |
| A place known only by name, such as "northwest Ohio" | none. Coordinates drawn by eye are a guess |

Prefer the simplest shape the source states. An outline with thousands of
vertices makes a record hard to read and its quote hard to check; a box
or a point often says enough. Ask the person when a record's geography is
unclear. Do not add places because the domain is spatial in general.

## 2. Add the classes to the schema

In the Mech, with its `extend-schema` skill: the classes the records need,
and a slot for each on the classes that describe a place. Use these names;
the checks find them by their slots, so a Mech may rename the classes, but
keep the slots' names, numeric ranges and, for WKT, the `slot_uri`.

```yaml
prefixes:
  schema: http://schema.org/
  geo: http://www.opengis.net/ont/geosparql#

classes:
  GeoPoint:
    class_uri: schema:GeoCoordinates
    description: >-
      A point, in decimal degrees (WGS84), as its source reports it. The
      record browser draws every one on a map.
    slots: [latitude, longitude, evidence]
    slot_usage:
      latitude: {required: true}
      longitude: {required: true}
  BoundingBox:
    description: >-
      The smallest box, in decimal degrees (WGS84), that holds an area: the
      extent its source reports, rounded to six decimals. West greater than
      east is a box across the antimeridian. The record browser draws every
      one on a map.
    slots: [west, south, east, north, evidence]
    slot_usage:
      west: {required: true}
      south: {required: true}
      east: {required: true}
      north: {required: true}
  Geometry:
    class_uri: geo:Geometry
    description: >-
      A line or an outline, as Well-Known Text in longitude, latitude order
      (WGS84). The record browser draws every one on a map.
    slots: [wkt, evidence]
    slot_usage:
      wkt: {required: true}

slots:
  location:
    range: GeoPoint
    inlined: true
    description: Where it is, from the source that locates it; drawn on the record's map.
  bounding_box:
    range: BoundingBox
    inlined: true
    slot_uri: geo:hasBoundingBox
    description: The area's extent, from the source that defines the area; drawn on the record's map.
  geometry:
    range: Geometry
    inlined: true
    slot_uri: geo:hasGeometry
    description: Its line or outline, from the source that draws it; drawn on the record's map.
  latitude:
    range: float
    slot_uri: schema:latitude
    minimum_value: -90
    maximum_value: 90
    description: Latitude, in decimal degrees.
  longitude:
    range: float
    slot_uri: schema:longitude
    minimum_value: -180
    maximum_value: 180
    description: Longitude, in decimal degrees.
  west:
    range: float
    minimum_value: -180
    maximum_value: 180
    description: Westernmost longitude, in decimal degrees.
  south:
    range: float
    minimum_value: -90
    maximum_value: 90
    description: Southernmost latitude, in decimal degrees.
  east:
    range: float
    minimum_value: -180
    maximum_value: 180
    description: Easternmost longitude, in decimal degrees.
  north:
    range: float
    minimum_value: -90
    maximum_value: 90
    description: Northernmost latitude, in decimal degrees.
  wkt:
    slot_uri: geo:asWKT
    description: >-
      Well-Known Text: POINT, LINESTRING, POLYGON or their MULTI forms,
      longitude first, as GeoSPARQL's default (CRS84).
```

Take only the classes the records use. Write it in `docs/DOMAIN.md` too:
which objects carry which shape, and from what source.

Then check that the checks see them: `just validate` on a record with a
place out of range (a latitude of 95) must fail. If it passes, a slot's
range is not numeric, or the WKT slot lacks its `slot_uri`.

## 3. Fill each place from a source, quoted

A place is a claim like any other. It comes from a source that states the
coordinates, and its evidence quotes the numbers. Never compute one from
memory, from a map, or from a list of coordinates you made up.

**An ArcGIS layer** (Census TIGERweb, the USGS Watershed Boundary Dataset,
many state and federal GIS services) reports the extent of any query, for
a bounding box. A script comes with this skill, in the `scripts/` folder
beside this file; `<scripts>` stands for that folder's path. It needs only
Python 3:

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

**Points.** A facility registry (EPA's FRS, a state's permit database), a
gazetteer (GeoNames gives `lat` and `lng`), a paper's methods, or Wikidata's
coordinate location (P625), which it writes as WKT, `Point(-83.65 43.05)`:
longitude first. Quote the numbers as the source writes them.

**Lines and outlines.** A source that publishes the geometry: an open-data
portal's WKT column, a dataset's GeoJSON, an ArcGIS query with
`returnGeometry=true`. Write it as WKT, simplified if the source allows
(`maxAllowableOffset` on ArcGIS), and quote a part of it the reader can
find in the source. Say in `explanation` how the source's form maps to WKT
when it is not WKT already.

**Watch the order.** WKT, GeoJSON and most GIS tools give longitude first.
schema.org, GeoNames and most papers give latitude first. OpenStreetMap's
Nominatim gives `boundingbox` as south, north, west, east, and its data is
under the ODbL, which asks for attribution. A WKT literal that names a
reference system other than CRS84 (`<http://www.opengis.net/def/crs/EPSG/0/4326>`
puts latitude first) is rejected; give it without one. A latitude and
longitude that are swapped but both in range pass the checks, so look at
the map.

Keep the numbers as text when copying them. A float loses digits
(-83.696946000250492 prints as -83.69694600025049), and the quote then
fails.

## 4. Look at it

```bash
just validate data/<records>/<record>.yaml   # each place, its parts, its quote
just docs-serve                              # the record page, with its map
```

Look at a record page at desktop and phone widths: each place should sit
where the source says. A small shape inside a large one (a postal area
inside its watershed) gets a dot; a lone point is shown at a neighbourhood's
width, not street level; the layer list folds into a button on a narrow
map.

## Settings and limits

- Maps are on by default. `map: false` in `conf/site.yaml` turns them off;
  the places stay in the data and on the page as text.
- The page loads Leaflet 1.9.4 from unpkg, pinned with an integrity hash,
  and tiles from OpenStreetMap. A visitor without JavaScript, or offline,
  sees the places as text in their sections.
- OpenStreetMap's tile policy
  (https://operations.osmfoundation.org/policies/tiles/) asks for the
  attribution the map shows and for light use. A Mech whose site will get
  heavy traffic should point the tile layer in `record.html` at its own or
  a paid tile service.
- Coordinates are in WGS84 (EPSG:4326, longitude first as CRS84 in WKT). A
  source in another reference system must be asked for WGS84 (`outSR=4326`
  on ArcGIS) or not used.
- A bounding box may cross the antimeridian (west greater than east). A
  line or outline in WKT may not: split it at 180°.
- `GEOMETRYCOLLECTION` and curved WKT types are not drawn.
