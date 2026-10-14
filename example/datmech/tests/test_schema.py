"""The schema, the vendored modules and the record rules."""

import copy
import hashlib
from pathlib import Path

import pytest
from linkml_runtime import SchemaView

from datmech import shapes
from datmech.paths import (
    HISTORY_SCHEMA_PATH,
    RECORD_CLASS,
    SCHEMA_DIR,
    SCHEMA_PATH,
)
from datmech.validate import load, rule_errors, schema_errors

EXAMPLE = Path(__file__).parent / "data" / "example_record.yaml"

# Fleet canon. These files are vendored byte-identical; a changed hash means
# a local edit. Change them upstream and re-vendor, never here.
VENDORED_MD5 = {
    "mech_shared.yaml": "afbf1a48493e88e086294aa5df03b556",
    "history.yaml": "3742bc2068b637868c48aba406f6569d",
}


@pytest.fixture
def example() -> dict:
    return load(EXAMPLE)


def test_schema_loads():
    sv = SchemaView(str(SCHEMA_PATH))
    assert RECORD_CLASS in sv.all_classes()
    assert sv.get_class(RECORD_CLASS).tree_root


@pytest.mark.parametrize("kind", ["all_classes", "all_slots", "all_enums", "all_types"])
def test_names_of_one_kind_differ_by_more_than_case(kind):
    """The schema pages are one file per element, in a folder per kind. Two
    names of one kind that differ only by case are one file on macOS and
    Windows, and the documentation build loses a page."""
    names = [str(n) for n in getattr(SchemaView(str(SCHEMA_PATH)), kind)()]
    seen: dict[str, str] = {}
    clashes = []
    for name in names:
        if name.casefold() in seen:
            clashes.append((seen[name.casefold()], name))
        seen[name.casefold()] = name
    assert clashes == []


@pytest.mark.parametrize("name,md5", VENDORED_MD5.items())
def test_vendored_modules_are_unmodified(name, md5):
    assert hashlib.md5((SCHEMA_DIR / name).read_bytes()).hexdigest() == md5


def test_example_is_valid(example):
    assert schema_errors(example) == []
    assert rule_errors(example) == []


def test_unknown_field_is_rejected(example):
    bad = copy.deepcopy(example)
    bad["not_a_field"] = 1
    assert schema_errors(bad)


def test_name_is_required(example):
    bad = copy.deepcopy(example)
    del bad["name"]
    assert schema_errors(bad)


def test_reviewed_needs_a_human_review_event(example):
    bad = copy.deepcopy(example)
    bad["status"] = "REVIEWED"
    assert any("REVIEWED" in e for e in rule_errors(bad))

def test_two_records_with_one_stem_are_refused(tmp_path, example):
    # Pages, history and research name a record by its filename stem alone.
    import yaml

    from datmech.validate import validate_paths

    paths = []
    for sub in ("a", "b"):
        (tmp_path / sub).mkdir()
        path = tmp_path / sub / "same.yaml"
        path.write_text(yaml.safe_dump({**example, "id": f"{example['id']}-{sub}"}), encoding="utf-8")
        paths.append(path)
    failures = validate_paths(paths)
    assert not any("also used by" in e for e in failures.get(paths[0], []))
    assert any(f"also used by {paths[0]}" in e for e in failures[paths[1]])




def test_malformed_items_are_reported_not_crashed_on(example):
    bad = copy.deepcopy(example)
    bad["status"] = "REVIEWED"
    bad["mechanisms"] = ["a string, not a node", {"name": "n", "downstream": ["not an edge"]}]
    bad["curation_history"] = ["not an event"]
    assert any("REVIEWED" in e for e in rule_errors(bad))  # and no AttributeError


def test_a_broken_history_file_is_reported(tmp_path):
    from datmech.history import validate_history

    (tmp_path / "dup.yaml").write_text("session: {}\nsession: {}\n", encoding="utf-8")
    (tmp_path / "null.yaml").write_text("session:\n", encoding="utf-8")
    failures = validate_history(tmp_path)
    assert "YAML parse error" in failures[tmp_path / "dup.yaml"][0]
    assert tmp_path / "null.yaml" in failures  # schema errors, not a crash


def test_history_schema_loads():
    sv = SchemaView(str(HISTORY_SCHEMA_PATH))
    assert "HistoryRecord" in sv.all_classes()


SHAPES = Path(__file__).parent / "data" / "shapes_schema.yaml"


def place_errors(data: dict) -> list[str]:
    return shapes.errors(data, SHAPES, "Place")


def test_shapes_are_found_from_the_schema_not_from_key_names():
    data = {"name": "X", "sites": [{"name": "s", "lat": 43.0, "longitude": -83.7}],
            "area": {"west": -83.7, "south": 43.0, "east": -83.6, "north": 43.1, "outline": "POINT (1 2)"},
            "neighbours": {"north": "Lake County", "south": "Porter County"}}
    found = [(s.where, s.kind) for s in shapes.find(data, SHAPES, "Place")]
    assert found == [("sites[0]", "point"), ("area", "box"), ("area", "wkt")]
    assert place_errors(data) == []


@pytest.mark.parametrize("box,ok", [
    ({"west": -83.7, "south": 43.0, "east": -83.6, "north": 43.1}, True),
    ({"west": 179.0, "south": 50.0, "east": -179.0, "north": 52.0}, True),  # across the antimeridian
    ({"west": -83.7, "south": 43.1, "east": -83.6, "north": 43.0}, False),  # south north of north
    ({"west": -200, "south": 0, "east": 0, "north": 1}, False),
    ({"west": -83.7, "south": 43.0, "east": -83.6}, False),  # a side missing
    ({"west": "far", "south": 43.0, "east": -83.6, "north": 43.1}, False),
])
def test_bounding_boxes_are_checked(box, ok):
    assert (place_errors({"area": box}) == []) == ok


@pytest.mark.parametrize("site,ok", [
    ({"lat": 43.0, "longitude": -83.7}, True),
    ({"lat": -83.7, "longitude": 43.0}, True),  # in range, so not caught: quote the order the source gives
    ({"lat": 95.0, "longitude": 0.0}, False),
    ({"lat": 43.0}, False),
    ({"name": "known only by name"}, True),  # no coordinates, no point
])
def test_points_are_checked(site, ok):
    assert (place_errors({"sites": [site]}) == []) == ok


@pytest.mark.parametrize("wkt,kind", [
    ("POINT (-83.69 43.01)", "Point"),
    ("Point(-83.69 43.01)", "Point"),
    ("POINT Z (-83.69 43.01 180)", "Point"),
    ("<http://www.opengis.net/def/crs/OGC/1.3/CRS84> POINT (-83.69 43.01)", "Point"),
    ("LINESTRING (-83.7 43.0, -83.6 43.1, -83.5 43.1)", "LineString"),
    ("POLYGON ((0 0, 1 0, 1 1, 0 0), (0.1 0.1, 0.2 0.1, 0.2 0.2, 0.1 0.1))", "Polygon"),
    ("MULTIPOINT ((0 0), (1 1))", "MultiPoint"),
    ("MULTIPOINT (0 0, 1 1)", "MultiPoint"),
    ("MULTILINESTRING ((0 0, 1 1), (2 2, 3 3))", "MultiLineString"),
    ("MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)), ((2 2, 3 2, 3 3, 2 2)))", "MultiPolygon"),
])
def test_wkt_becomes_geojson(wkt, kind):
    assert shapes.wkt_geometry(wkt)["type"] == kind
    assert place_errors({"area": {"outline": wkt}}) == []


def test_wkt_keeps_longitude_first():
    line = shapes.wkt_geometry("LINESTRING (-83.7 43.0, -83.6 43.1)")
    assert line["coordinates"] == [[-83.7, 43.0], [-83.6, 43.1]]


@pytest.mark.parametrize("wkt", [
    "POINT (43.01 -95)",  # latitude out of range
    "POINT EMPTY",
    "POINT (1 2, 3 4)",
    "LINESTRING (0 0)",
    "POLYGON ((0 0, 1 0, 1 1, 0 1))",  # ring not closed
    "POLYGON (0 0, 1 0, 1 1, 0 0)",  # one pair of parentheses short
    "GEOMETRYCOLLECTION (POINT (0 0))",
    "<http://www.opengis.net/def/crs/EPSG/0/4326> POINT (43.01 -83.69)",  # latitude first
    "POINT (1 2",
    "a field in Ohio",
])
def test_bad_wkt_is_reported(wkt):
    assert place_errors({"area": {"outline": wkt}})


def test_a_record_with_no_shapes_has_no_shape_errors(example):
    assert shapes.errors(example) == []
