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
    """Local equirectangular projection to metres (fine at city scale)."""
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


def corridor_tiles(
    polyline: Sequence[LatLon], tile_deg: float = 0.01, step_m: float = 250
) -> list[BBox]:
    """Grid-aligned bounding boxes along a road line (Mapillary limits bbox size)."""
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


def point_in_polygon(lat: float, lon: float, polygon: Sequence[LatLon]) -> bool:
    """Ray-casting point-in-polygon test (polygon given as (lat, lon) vertices)."""
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        yi, xi = polygon[i]
        yj, xj = polygon[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def polygon_bbox(polygon: Sequence[LatLon]) -> BBox:
    lats = [p[0] for p in polygon]
    lons = [p[1] for p in polygon]
    return min(lons), min(lats), max(lons), max(lats)


def _tile_touches_polygon(tile: BBox, polygon: Sequence[LatLon], samples: int) -> bool:
    min_lon, min_lat, max_lon, max_lat = tile
    if any(min_lat <= la <= max_lat and min_lon <= lo <= max_lon for la, lo in polygon):
        return True
    for a in range(samples):
        for b in range(samples):
            la = min_lat + (max_lat - min_lat) * a / (samples - 1)
            lo = min_lon + (max_lon - min_lon) * b / (samples - 1)
            if point_in_polygon(la, lo, polygon):
                return True
    return False


def area_tiles(
    polygon: Sequence[LatLon], tile_deg: float = 0.01, samples: int = 5
) -> list[BBox]:
    """Grid-aligned tiles that overlap the polygon (approximate: thin slivers may be missed)."""
    min_lon, min_lat, max_lon, max_lat = polygon_bbox(polygon)
    i0, j0 = math.floor(min_lat / tile_deg + 1e-9), math.floor(min_lon / tile_deg + 1e-9)
    i1 = max(i0, math.ceil(max_lat / tile_deg - 1e-9) - 1)
    j1 = max(j0, math.ceil(max_lon / tile_deg - 1e-9) - 1)
    tiles = []
    for i in range(i0, i1 + 1):
        for j in range(j0, j1 + 1):
            tile = (j * tile_deg, i * tile_deg, (j + 1) * tile_deg, (i + 1) * tile_deg)
            if _tile_touches_polygon(tile, polygon, samples):
                tiles.append(tuple(round(v, 6) for v in tile))
    return tiles


def split_bbox(b: BBox) -> list[BBox]:
    min_lon, min_lat, max_lon, max_lat = b
    mid_lon, mid_lat = (min_lon + max_lon) / 2, (min_lat + max_lat) / 2
    return [
        (min_lon, min_lat, mid_lon, mid_lat),
        (mid_lon, min_lat, max_lon, mid_lat),
        (min_lon, mid_lat, mid_lon, max_lat),
        (mid_lon, mid_lat, max_lon, max_lat),
    ]
