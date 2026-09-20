"""How much of the study area do we actually have imagery for?

Cells are squares of `cell_m` metres whose centre lies inside the area. A cell is "covered"
if at least one image was taken inside it. Cells include buildings and empty land, so 100%
is unreachable - use the number to compare periods and to judge whether change tracking is
feasible, not as a literal share of road length.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from .config import Area
from .geo import EARTH_R


def coverage_stats(
    points: Iterable[tuple[float, float]], area: Area, cell_m: float = 100.0
) -> dict:
    ring_pts = [p for poly in area.polygons for p in poly]
    min_lat, max_lat = min(p[0] for p in ring_pts), max(p[0] for p in ring_pts)
    min_lon, max_lon = min(p[1] for p in ring_pts), max(p[1] for p in ring_pts)
    dlat = math.degrees(cell_m / EARTH_R)
    dlon = math.degrees(cell_m / (EARTH_R * math.cos(math.radians((min_lat + max_lat) / 2))))

    cells = set()
    for i in range(math.ceil((max_lat - min_lat) / dlat)):
        for j in range(math.ceil((max_lon - min_lon) / dlon)):
            if area.contains(min_lat + (i + 0.5) * dlat, min_lon + (j + 0.5) * dlon):
                cells.add((i, j))

    covered = set()
    n_images = 0
    for lat, lon in points:
        key = (math.floor((lat - min_lat) / dlat), math.floor((lon - min_lon) / dlon))
        if key in cells:
            covered.add(key)
            n_images += 1
    total = len(cells)
    return {
        "cells_total": total,
        "cells_covered": len(covered),
        "coverage_pct": round(100 * len(covered) / total, 1) if total else 0.0,
        "images_in_area": n_images,
    }
