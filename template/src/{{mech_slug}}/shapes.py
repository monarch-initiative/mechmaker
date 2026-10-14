"""The places a record holds, as shapes on a map: points, boxes, lines and areas.

The schema says which objects are shapes, not their keys. A class is one when
its slots say so, whatever the class is called:

- a point: numeric `latitude` and `longitude` slots (or slots with slot_uri
  schema:latitude and schema:longitude), in decimal degrees (WGS84);
- a box: numeric `west`, `south`, `east` and `north` slots, in decimal degrees.
  West greater than east is a box across the antimeridian, as in GeoJSON;
- a geometry: a slot with slot_uri geo:asWKT (GeoSPARQL), holding Well-Known
  Text in longitude, latitude order: a POINT, LINESTRING or POLYGON, or a
  MULTIPOINT, MULTILINESTRING or MULTIPOLYGON.

find() walks a record along each slot's range from the record class, so a slot
named `north` that holds a county's name is never taken for a box. `just
validate` checks every shape (errors); the record browser draws every one
(render.py), as GeoJSON (geometry).
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path
from typing import NamedTuple

from .paths import RECORD_CLASS, SCHEMA_PATH

BOX = ("west", "south", "east", "north")
POINT = ("latitude", "longitude")
# Slots that hold a latitude or a longitude under another name.
POINT_URIS = {
    "latitude": {"http://schema.org/latitude", "https://schema.org/latitude",
                 "http://www.w3.org/2003/01/geo/wgs84_pos#lat"},
    "longitude": {"http://schema.org/longitude", "https://schema.org/longitude",
                  "http://www.w3.org/2003/01/geo/wgs84_pos#long"},
}
WKT_URI = "http://www.opengis.net/ont/geosparql#asWKT"
# The one reference system WKT may name: GeoSPARQL's default, longitude first.
CRS84 = "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
NUMERIC = {"float", "double", "decimal", "integer"}
# WKT's types, as GeoJSON names them, and how deep their coordinates nest.
WKT_TYPES = {"POINT": ("Point", 0), "LINESTRING": ("LineString", 1), "POLYGON": ("Polygon", 2),
             "MULTIPOINT": ("MultiPoint", 1), "MULTILINESTRING": ("MultiLineString", 2),
             "MULTIPOLYGON": ("MultiPolygon", 3)}


class Shape(NamedTuple):
    where: str  # its path in the record, such as watersheds[0].bounding_box
    parents: tuple  # ((key, the object holding key), ...) from the record down to it
    obj: dict  # the object that holds it
    kind: str  # point, box or wkt
    values: dict  # its slots' values: {west: .., ...}, {latitude: .., longitude: ..} or {wkt: ..}


@cache
def _view(schema: str):
    from linkml_runtime.utils.schemaview import SchemaView

    return SchemaView(schema)


def _numeric(sv, rng: str | None) -> bool:
    return rng in sv.all_types() and bool(NUMERIC & set(sv.type_ancestors(rng)))


@cache
def _class(schema: str, cls: str) -> tuple[dict[str, list[dict[str, str]]], dict[str, tuple[str, bool]]]:
    """({kind: [{role: key}, ...]}, {key: (the class it ranges over, multivalued)}) for one class."""
    sv = _view(schema)
    slots = {s.alias or s.name: s for s in sv.class_induced_slots(cls)}
    uris = {k: sv.expand_curie(s.slot_uri) if s.slot_uri else None for k, s in slots.items()}
    numeric = {k for k, s in slots.items() if _numeric(sv, s.range)}
    kinds: dict[str, list[dict[str, str]]] = {}
    point = {}
    for role in POINT:
        found = [k for k in numeric if k == role or uris[k] in POINT_URIS[role]]
        if found:
            point[role] = sorted(found, key=lambda k: k != role)[0]
    if len(point) == len(POINT):
        kinds["point"] = [point]
    if set(BOX) <= numeric:
        kinds["box"] = [{side: side for side in BOX}]
    wkt = [{"wkt": k} for k, uri in uris.items() if uri == WKT_URI]
    if wkt:
        kinds["wkt"] = wkt
    ranges = {k: (s.range, bool(s.multivalued)) for k, s in slots.items() if s.range in sv.all_classes()}
    return kinds, ranges


def find(data, schema: Path | str | None = None, cls: str | None = None,
         where: str = "", parents: tuple = ()):
    """Every Shape in DATA, an object of class CLS (the record class). Nothing when the schema
    does not load: the schema check reports that."""
    if not isinstance(data, dict):
        return
    schema, cls = str(schema or SCHEMA_PATH), cls or RECORD_CLASS
    try:
        kinds, ranges = _class(schema, cls)
    except Exception:
        return
    for kind, groups in kinds.items():
        for roles in groups:
            values = {role: data.get(key) for role, key in roles.items()}
            if any(v is not None for v in values.values()):
                yield Shape(where or "record", parents, data, kind, values)
    for key, value in data.items():
        if key not in ranges:
            continue
        rng, multivalued = ranges[key]
        here, up = f"{where}.{key}" if where else key, (*parents, (key, data))
        if isinstance(value, list):
            for i, item in enumerate(value):
                yield from find(item, schema, rng, f"{here}[{i}]", up)
        elif isinstance(value, dict) and multivalued:  # inlined as a dict, keyed by identifier
            for name, item in value.items():
                yield from find(item, schema, rng, f"{here}.{name}", up)
        else:
            yield from find(value, schema, rng, here, up)


def errors(data, schema: Path | str | None = None, cls: str | None = None) -> list[str]:
    """What is wrong with each shape in a record, one line each."""
    out = []
    for shape in find(data, schema, cls):
        try:
            geometry(shape)
        except ValueError as exc:
            out.append(f"{shape.where}: {exc}")
    return out


def _number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _lon_lat(lon, lat) -> list:
    if not -180 <= lon <= 180:
        raise ValueError(f"longitude {lon} must lie in -180..180")
    if not -90 <= lat <= 90:
        raise ValueError(f"latitude {lat} must lie in -90..90")
    return [lon, lat]


def geometry(shape: Shape) -> dict:
    """The shape as a GeoJSON geometry, or ValueError saying what is wrong with it."""
    v = shape.values
    if shape.kind == "point":
        if not all(_number(v[k]) for k in POINT):
            raise ValueError("a point needs latitude and longitude, in decimal degrees")
        return {"type": "Point", "coordinates": _lon_lat(v["longitude"], v["latitude"])}
    if shape.kind == "box":
        if not all(_number(v[k]) for k in BOX):
            raise ValueError("a bounding box needs west, south, east and north, in decimal degrees")
        west, south, east, north = (v[k] for k in BOX)
        if not (-180 <= west <= 180 and -180 <= east <= 180):
            raise ValueError(f"west {west} and east {east} must lie in -180..180")
        if not -90 <= south <= north <= 90:
            raise ValueError(f"south {south} and north {north} must lie in -90..90, south first")
        if west > east:  # across the antimeridian: the map continues east past 180
            east += 360
        if (west, south) == (east, north):
            return {"type": "Point", "coordinates": [west, south]}
        return {"type": "Polygon",
                "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}
    return wkt_geometry(v["wkt"])


_HEAD = re.compile(r"\s*(?:<([^>]*)>\s*)?([A-Za-z]+)(?:\s+(?:ZM|Z|M)(?=[\s(]))?\s*(.*?)\s*$", re.S | re.I)
_NUMBER = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_POSITION = re.compile(rf"{_NUMBER}(?:\s+{_NUMBER})*")


def _groups(text: str) -> list:
    """Parenthesized WKT as nested lists, each position a tuple of numbers."""
    pos = 0

    def skip():
        nonlocal pos
        while pos < len(text) and text[pos].isspace():
            pos += 1

    def group() -> list:
        nonlocal pos
        skip()
        if text[pos:pos + 1] != "(":
            raise ValueError(f"WKT: expected ( at character {pos}")
        pos += 1
        items: list = []
        while True:
            skip()
            if text[pos:pos + 1] == "(":
                items.append(group())
            else:
                m = _POSITION.match(text, pos)
                if not m:
                    raise ValueError(f"WKT: expected a coordinate at character {pos}")
                items.append(tuple(float(x) for x in m.group().split()))
                pos = m.end()
            skip()
            if text[pos:pos + 1] == ",":
                pos += 1
            elif text[pos:pos + 1] == ")":
                pos += 1
                return items
            else:
                raise ValueError(f"WKT: expected , or ) at character {pos}")

    found = group()
    skip()
    if pos != len(text):
        raise ValueError(f"WKT: unexpected text at character {pos}")
    return found


def _coordinates(items, depth: int):
    if depth == 0:
        if not isinstance(items, tuple) or not 2 <= len(items) <= 4:
            raise ValueError("WKT: a position is two to four numbers, longitude first")
        return _lon_lat(items[0], items[1])
    if not isinstance(items, list):
        raise ValueError("WKT: the parentheses do not match the type")
    return [_coordinates(i, depth - 1) for i in items]


def wkt_geometry(text) -> dict:
    """Well-Known Text as a GeoJSON geometry, or ValueError saying what is wrong with it."""
    m = _HEAD.match(text) if isinstance(text, str) else None
    if not m:
        raise ValueError("a geometry needs Well-Known Text, such as POINT (-83.69 43.01)")
    crs, kind, body = m.groups()
    if crs and crs != CRS84:
        raise ValueError(f"WKT in {crs}: give it in {CRS84}, longitude first")
    if kind.upper() not in WKT_TYPES:
        raise ValueError(f"WKT type {kind} is not drawn; use one of {', '.join(WKT_TYPES)}")
    if body.upper() == "EMPTY":
        raise ValueError(f"an empty {kind.upper()} has nothing to draw")
    name, depth = WKT_TYPES[kind.upper()]
    items = _groups(body)
    if name == "Point":
        if len(items) != 1:
            raise ValueError("WKT: a POINT has one position")
        items = items[0]
    elif name == "MultiPoint":  # MULTIPOINT ((1 2), (3 4)) or MULTIPOINT (1 2, 3 4)
        items = [i[0] if isinstance(i, list) and len(i) == 1 else i for i in items]
    coordinates = _coordinates(items, depth)
    lines = [coordinates] if name == "LineString" else coordinates if name == "MultiLineString" else []
    if any(len(line) < 2 for line in lines):
        raise ValueError("WKT: a line needs two positions or more")
    polygons = [coordinates] if name == "Polygon" else coordinates if name == "MultiPolygon" else []
    rings = [ring for polygon in polygons for ring in polygon]
    if any(len(ring) < 4 or ring[0] != ring[-1] for ring in rings):
        raise ValueError("WKT: a polygon's ring needs four positions or more, the last the same as the first")
    return {"type": name, "coordinates": coordinates}
