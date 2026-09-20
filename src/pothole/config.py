"""Config loading."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

LatLon = tuple[float, float]


def load_config(path: str | Path = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _extract_line(obj: dict) -> list[list[float]]:
    kind = obj.get("type")
    if kind == "FeatureCollection":
        for feat in obj["features"]:
            try:
                return _extract_line(feat)
            except ValueError:
                continue
    elif kind == "Feature":
        return _extract_line(obj["geometry"])
    elif kind == "LineString":
        return obj["coordinates"]
    elif kind == "MultiLineString":
        return [pt for line in obj["coordinates"] for pt in line]
    raise ValueError("No LineString found in GeoJSON")


def load_corridor(cfg: dict) -> list[LatLon]:
    """Return the corridor centre line as [(lat, lon), ...]."""
    c = cfg["corridor"]
    gj = c.get("geojson")
    if gj and Path(gj).exists():
        with open(gj, encoding="utf-8") as f:
            coords = _extract_line(json.load(f))
        return [(lat, lon) for lon, lat in coords]
    return [(float(lat), float(lon)) for lat, lon in c["waypoints"]]
