"""Config loading and the study area (city polygon + optional highway stretch)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from .geo import (
    BBox,
    LatLon,
    area_tiles,
    corridor_tiles,
    distance_to_polyline_m,
    point_in_polygon,
)


def load_config(path: str | Path = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _all_geometries(obj: dict, kinds: tuple[str, ...]) -> list[dict]:
    """Every geometry of the given kinds found in a GeoJSON object, in file order."""
    found: list[dict] = []
    kind = obj.get("type")
    if kind == "FeatureCollection":
        for feat in obj["features"]:
            found += _all_geometries(feat, kinds)
    elif kind == "Feature":
        found += _all_geometries(obj["geometry"], kinds)
    elif kind in kinds:
        found.append(obj)
    return found


def _polygons_from_geojson(obj: dict) -> list[list[LatLon]]:
    """All polygon outer rings in a GeoJSON file, as (lat, lon) lists."""
    rings: list[list[LatLon]] = []

    def walk(o: dict) -> None:
        kind = o.get("type")
        if kind == "FeatureCollection":
            for feat in o["features"]:
                walk(feat)
        elif kind == "Feature":
            walk(o["geometry"])
        elif kind == "Polygon":
            rings.append([(lat, lon) for lon, lat in o["coordinates"][0]])
        elif kind == "MultiPolygon":
            for poly in o["coordinates"]:
                rings.append([(lat, lon) for lon, lat in poly[0]])

    walk(obj)
    if not rings:
        raise ValueError("No Polygon found in GeoJSON")
    return rings


def _lines_from_geojson(obj: dict) -> list[list[LatLon]]:
    """All line strings in a GeoJSON file, each kept as its own (lat, lon) list.

    A MultiLineString (or several LineStrings) describes *separate* stretches of road:
    joining them into one polyline would invent road segments between the line ends and
    those phantom segments would then be counted as covered area.
    """
    lines: list[list[LatLon]] = []
    for geom in _all_geometries(obj, ("LineString", "MultiLineString")):
        parts = geom["coordinates"]
        if geom["type"] == "LineString":
            parts = [parts]
        for part in parts:
            pts = [(lat, lon) for lon, lat in part]
            if len(pts) >= 2:
                lines.append(pts)
    if not lines:
        raise ValueError("No LineString found in GeoJSON")
    return lines


@dataclass(frozen=True)
class Area:
    """Study area: one or more polygons, plus optional highway lines with a buffer."""

    name: str
    polygons: list[list[LatLon]]
    highway: list[list[LatLon]] | None = None
    highway_buffer_m: float = 100.0
    tile_deg: float = 0.01

    def contains(self, lat: float, lon: float) -> bool:
        if any(point_in_polygon(lat, lon, poly) for poly in self.polygons):
            return True
        if self.highway:
            return any(
                distance_to_polyline_m(lat, lon, line) <= self.highway_buffer_m
                for line in self.highway
            )
        return False

    def tiles(self) -> list[BBox]:
        tiles: set[BBox] = set()
        for poly in self.polygons:
            tiles.update(area_tiles(poly, self.tile_deg))
        for line in self.highway or []:
            tiles.update(corridor_tiles(line, self.tile_deg))
        return sorted(tiles)

    def centre(self) -> LatLon:
        pts = [p for poly in self.polygons for p in poly]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def load_area(cfg: dict) -> Area:
    a = cfg["area"]
    poly_file = a.get("polygon_geojson")
    if poly_file and Path(poly_file).exists():
        with open(poly_file, encoding="utf-8") as f:
            polygons = _polygons_from_geojson(json.load(f))
    else:
        min_lat, min_lon, max_lat, max_lon = a["bbox"]
        polygons = [
            [(min_lat, min_lon), (min_lat, max_lon), (max_lat, max_lon), (max_lat, min_lon)]
        ]

    highway = None
    hw_file = a.get("highway_geojson")
    if hw_file and Path(hw_file).exists():
        with open(hw_file, encoding="utf-8") as f:
            highway = _lines_from_geojson(json.load(f))

    return Area(
        name=a.get("name", "study area"),
        polygons=polygons,
        highway=highway,
        highway_buffer_m=float(a.get("highway_buffer_m", 100)),
        tile_deg=float(a.get("tile_deg", 0.01)),
    )
