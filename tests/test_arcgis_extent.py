"""arcgis_extent.py, replayed on the responses DaTMech's records quote. No network."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "add-record-map" / "scripts" / "arcgis_extent.py"
sys.path.insert(0, str(SCRIPT.parent))

import arcgis_extent  # noqa: E402

DAT = ROOT / "example" / "datmech"


def boxes():
    """(reference, box) for every box in DaTMech's records that quotes an extent query."""
    for path in sorted((DAT / "data" / "zip_areas").glob("*.yaml")):
        data = yaml.safe_load(path.read_text())
        found = [data["zcta"]["bounding_box"]] + [w["bounding_box"] for w in data["watersheds"]]
        for box in found:
            yield box["evidence"][0]["reference"], box


def cached(reference: str) -> str:
    name = reference.replace("/", "_").replace(":", "_").replace("?", "_").replace("=", "_") + ".md"
    return (DAT / "references_cache" / name).read_text()


@pytest.mark.parametrize("reference,box", list(boxes()))
def test_replays_each_datmech_box_exactly(reference, box):
    url = reference.removeprefix("url:")
    layer, _, query = url.partition("/query?where=")
    where = arcgis_extent.urllib.parse.unquote(query.split("&")[0])
    assert arcgis_extent.query_url(layer, where) == url
    text = cached(reference)
    sides = arcgis_extent.extent(text)
    assert arcgis_extent.in_wgs84(text)
    printed = yaml.safe_load(arcgis_extent.box_yaml(url, sides, "x"))["bounding_box"]
    assert {k: printed[k] for k in ("west", "south", "east", "north")} == \
        {k: box[k] for k in ("west", "south", "east", "north")}
    assert printed["evidence"][0]["snippet"] == box["evidence"][0]["snippet"]


def test_numbers_are_copied_as_written_not_as_floats():
    text = '{"extent": {"xmin": -83.696946000250492, "ymin": 43.0, "xmax": -83.6, "ymax": 43.1}}'
    assert arcgis_extent.extent(text)[0] == "-83.696946000250492"


@pytest.mark.parametrize("text", [
    '{"extent": {"xmin": "NaN", "ymin": "NaN", "xmax": "NaN", "ymax": "NaN"}}',  # nothing selected
    '{"error": {"code": 400, "message": "Invalid query"}}',
])
def test_no_extent(text):
    assert arcgis_extent.extent(text) is None


def test_web_mercator_is_not_wgs84():
    assert not arcgis_extent.in_wgs84('{"spatialReference": {"wkid": 102100, "latestWkid": 3857}}')
    assert arcgis_extent.in_wgs84('{"spatialReference": {"wkid": 4326, "latestWkid": 4326}}')


def test_usage():
    assert arcgis_extent.main([]) == 64
    assert arcgis_extent.main(["not-a-url", "x=1"]) == 64
