"""Small geo helpers (pure Python, no heavy dependencies)."""

from __future__ import annotations

import math
from collections.abc import Sequence

EARTH_R = 6_371_000.0

LatLon = tuple[float, float]
BBox = tuple[float, float, float, float]  # min_lon, min_lat, max_lon, max_lat


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_R * math.asin(math.sqrt(a))


def offset_point(lat: float, lon: float, bearing_deg: float, dist_m: float) -> LatLon:
    """Point `dist_m` away from (lat, lon) along `bearing_deg` (0 = north, 90 = east)."""
    br = math.radians(bearing_deg)
    d = dist_m / EARTH_R
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(br))
    l2 = l1 + math.atan2(
        math.sin(br) * math.sin(d) * math.cos(p1),
        math.cos(d) - math.sin(p1) * math.sin(p2),
    )
    return math.degrees(p2), math.degrees(l2)


def to_xy(lat: float, lon: float, lat0: float) -> tuple[float, float]:
    """Local equirectangular projection to metres (fine for a ~50 km corridor)."""
    x = math.radians(lon) * EARTH_R * math.cos(math.radians(lat0))
    y = math.radians(lat) * EARTH_R
    return x, y


def _dist_point_segment(p, a, b) -> float:
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def distance_to_polyline_m(lat: float, lon: float, polyline: Sequence[LatLon]) -> float:
    lat0 = sum(p[0] for p in polyline) / len(polyline)
    p = to_xy(lat, lon, lat0)
    pts = [to_xy(la, lo, lat0) for la, lo in polyline]
    if len(pts) == 1:
        return math.hypot(p[0] - pts[0][0], p[1] - pts[0][1])
    return min(_dist_point_segment(p, a, b) for a, b in zip(pts, pts[1:], strict=False))


def interpolate_polyline(polyline: Sequence[LatLon], step_m: float) -> list[LatLon]:
    """Densify a polyline so consecutive points are at most `step_m` apart."""
    out: list[LatLon] = [tuple(polyline[0])]
    for (la1, lo1), (la2, lo2) in zip(polyline, polyline[1:], strict=False):
        n = max(1, math.ceil(haversine_m(la1, lo1, la2, lo2) / step_m))
        for i in range(1, n + 1):
            t = i / n
            out.append((la1 + (la2 - la1) * t, lo1 + (lo2 - lo1) * t))
    return out


def corridor_tiles(polyline: Sequence[LatLon], tile_deg: float = 0.01, step_m: float = 250) -> list[BBox]:
    """Grid-aligned bounding boxes covering the corridor (Mapillary limits bbox size)."""
    cells = {
        (math.floor(lat / tile_deg), math.floor(lon / tile_deg))
        for lat, lon in interpolate_polyline(polyline, step_m)
    }
    return [
        (
            round(j * tile_deg, 6),
            round(i * tile_deg, 6),
            round((j + 1) * tile_deg, 6),
            round((i + 1) * tile_deg, 6),
        )
        for i, j in sorted(cells)
    ]


def split_bbox(b: BBox) -> list[BBox]:
    min_lon, min_lat, max_lon, max_lat = b
    mid_lon, mid_lat = (min_lon + max_lon) / 2, (min_lat + max_lat) / 2
    return [
        (min_lon, min_lat, mid_lon, mid_lat),
        (mid_lon, min_lat, max_lon, mid_lat),
        (min_lon, mid_lat, mid_lon, max_lat),
        (mid_lon, mid_lat, max_lon, max_lat),
    ]
