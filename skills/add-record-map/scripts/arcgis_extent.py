#!/usr/bin/env python3
"""Print a record's bounding box, with its quote, from an ArcGIS feature layer. Standard library only.

    arcgis_extent.py <layer URL> "<where clause>"
    arcgis_extent.py https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/4 "huc8='04080204'"
    arcgis_extent.py \\
        https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/1 \\
        "ZCTA5='48502'"

It asks the layer for the extent of the features the where clause selects,
in WGS84 (returnExtentOnly=true&outSR=4326), and prints a `bounding_box`
in YAML: the four sides rounded to six decimals, and one evidence item
whose reference is the query URL and whose snippet is the extent exactly as
the service wrote it. Paste it into the record, set evidence_source to the
Mech's own value, and run `just validate`, which fetches the URL and
checks the quote.

The numbers are copied from the response as text, never read back from a
float: -83.696946000250492 becomes -83.69694600025049 as a float, and the
quote would not match.

Exit status: 0 printed, 1 the clause selects nothing or the extent is not in
WGS84, 2 the service did not answer, 64 a usage error.
"""

from __future__ import annotations

import re
import sys
import urllib.error
import urllib.parse
import urllib.request

SIDES = ("xmin", "ymin", "xmax", "ymax")
NUMBER = r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"
# "xmin": <number>, "ymin": <number>, ... in that order, whitespace as the service writes it.
EXTENT = re.compile(r"\s*,\s*".join(rf'"{side}"\s*:\s*({NUMBER})' for side in SIDES))


def query_url(layer: str, where: str) -> str:
    """The extent query, spelled as DaTMech's references spell it."""
    return (f"{layer.rstrip('/')}/query?where={urllib.parse.quote(where, safe='')}"
            "&returnExtentOnly=true&outSR=4326&f=pjson")


def extent(text: str) -> tuple[str, str, str, str] | None:
    """(xmin, ymin, xmax, ymax) as written in the response, or None if it has no numeric extent."""
    m = EXTENT.search(text)
    return m.groups() if m else None


def in_wgs84(text: str) -> bool:
    return re.search(r'"(?:latestWkid|wkid)"\s*:\s*4326\b', text) is not None


def box_yaml(url: str, sides: tuple[str, str, str, str], what: str) -> str:
    xmin, ymin, xmax, ymax = sides
    snippet = ", ".join(f'"{k}": {v}' for k, v in zip(SIDES, sides, strict=True))
    west, south, east, north = (round(float(v), 6) for v in (xmin, ymin, xmax, ymax))
    return (f"bounding_box:\n"
            f"  west: {west}\n  south: {south}\n  east: {east}\n  north: {north}\n"
            f"  evidence:\n"
            f"    - reference: url:{url}\n"
            f"      supports: SUPPORT\n"
            f"      evidence_source: TODO  # the Mech's own value for a geographic dataset\n"
            f"      snippet: '{snippet}'\n"
            f"      explanation: The extent of {what} in WGS84, rounded to six decimals.\n")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or not args[0].startswith(("http://", "https://")):
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 64
    layer, where = args
    url = query_url(layer, where)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mechmaker-arcgis-extent"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8")
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"The service did not answer: {e}", file=sys.stderr)
        return 2
    if '"error"' in text and extent(text) is None:
        print(f"The service refused the query: {text.strip()[:300]}", file=sys.stderr)
        return 1
    sides = extent(text)
    if sides is None:
        print(f"No extent: the clause {where!r} selects no features in {layer}.", file=sys.stderr)
        return 1
    if not in_wgs84(text):
        print("The extent is not in WGS84 (wkid 4326); the layer ignored outSR.", file=sys.stderr)
        return 1
    print(box_yaml(url, sides, f"the features where {where}"), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
