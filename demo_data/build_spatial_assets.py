"""Derive local cartography assets from the checked-in IGN geometry."""
import json
import math
from hashlib import sha256
from pathlib import Path

from shapely import STRtree, get_parts, union_all
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent


def build():
    raw = (ROOT / "municipios.geojson").read_bytes()
    features = json.loads(raw)["features"]
    codes = [feature["id"] for feature in features]
    polygons = [shape(feature["geometry"]) for feature in features]
    tree = STRtree(polygons)
    edges = sorted([codes[i], codes[j]] for i, polygon in enumerate(polygons)
                   for j in tree.query(polygon, predicate="intersects") if i < j)
    adjacency = {"sha256": sha256(raw).hexdigest(), "edges": edges}
    (ROOT / "vecindad.json").write_text(json.dumps(adjacency, separators=(",", ":")) + "\n")

    region = union_all(polygons).simplify(0.002, preserve_topology=True)
    west, south, east, north = region.bounds
    lon_scale = math.cos(math.radians((north + south) / 2))
    scale = 52 / max((east - west) * lon_scale, north - south)
    center_x, center_y = (west + east) / 2, (north + south) / 2
    paths = []
    for polygon in get_parts(region):
        if polygon.area < region.area * 0.0001:
            continue
        coordinates = [f"{32 + scale * (lon - center_x) * lon_scale:.1f},{32 - scale * (lat - center_y):.1f}"
                       for lon, lat in polygon.exterior.coords]
        paths.append("M" + "L".join(coordinates) + "Z")
    svg = '<svg viewBox="0 0 64 64" aria-hidden="true" xmlns="http://www.w3.org/2000/svg">' + (
        f'<path fill="currentColor" d="{" ".join(paths)}"/></svg>\n')
    (ROOT / "madrid_silueta.svg").write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    build()
