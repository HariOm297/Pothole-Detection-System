"""Change detection between two time periods.

Key idea: "not detected before" only means *new* if we actually had imagery of that
spot in the earlier period. Likewise "not detected now" only means *fixed* if we have
recent imagery there. Otherwise the status is `unconfirmed`.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

from .geo import haversine_m, to_xy


class Status(str, Enum):
    NEW = "new"
    PERSISTENT = "persistent"
    FIXED = "fixed"
    UNCONFIRMED = "unconfirmed"


@dataclass(frozen=True)
class Detection:
    lat: float
    lon: float
    conf: float


@dataclass
class Cluster:
    lat: float
    lon: float
    conf: float
    hits: int = 1


@dataclass(frozen=True)
class PotholeStatus:
    lat: float
    lon: float
    status: Status
    conf: float
    hits: int


class _Grid:
    """Spatial hash over points in local metres."""

    def __init__(self, cell_m: float, lat0: float):
        self.cell = cell_m
        self.lat0 = lat0
        self.cells: dict[tuple[int, int], list] = {}

    def _key(self, x: float, y: float) -> tuple[int, int]:
        return math.floor(x / self.cell), math.floor(y / self.cell)

    def add(self, lat: float, lon: float, item=None) -> None:
        x, y = to_xy(lat, lon, self.lat0)
        self.cells.setdefault(self._key(x, y), []).append((x, y, item))

    def near(self, lat: float, lon: float, radius_m: float) -> list:
        x, y = to_xy(lat, lon, self.lat0)
        cx, cy = self._key(x, y)
        reach = max(1, math.ceil(radius_m / self.cell))
        found = []
        for i in range(cx - reach, cx + reach + 1):
            for j in range(cy - reach, cy + reach + 1):
                for px, py, item in self.cells.get((i, j), ()):
                    if math.hypot(px - x, py - y) <= radius_m:
                        found.append(item)
        return found


def cluster_detections(
    dets: Sequence[Detection], radius_m: float = 8.0, min_hits: int = 1
) -> list[Cluster]:
    """Merge detections of the same pothole (seen in several frames) into one cluster.

    The highest-confidence detection seeds each cluster and gives its position.
    """
    if not dets:
        return []
    grid = _Grid(radius_m, dets[0].lat)
    clusters: list[Cluster] = []
    for d in sorted(dets, key=lambda d: -d.conf):
        nearby = grid.near(d.lat, d.lon, radius_m)
        if nearby:
            best = min(nearby, key=lambda c: haversine_m(c.lat, c.lon, d.lat, d.lon))
            best.hits += 1
        else:
            c = Cluster(d.lat, d.lon, d.conf)
            clusters.append(c)
            grid.add(c.lat, c.lon, c)
    return [c for c in clusters if c.hits >= min_hits]


def _coverage_grid(points: Iterable[tuple[float, float]], cell_m: float, lat0: float) -> _Grid:
    g = _Grid(cell_m, lat0)
    for lat, lon in points:
        g.add(lat, lon)
    return g


def compare_periods(
    baseline: Sequence[Detection],
    current: Sequence[Detection],
    baseline_coverage: Sequence[tuple[float, float]],
    current_coverage: Sequence[tuple[float, float]],
    cluster_radius_m: float = 8.0,
    match_radius_m: float = 12.0,
    coverage_radius_m: float = 15.0,
    min_hits: int = 2,
) -> list[PotholeStatus]:
    base = cluster_detections(baseline, cluster_radius_m, min_hits)
    cur = cluster_detections(current, cluster_radius_m, min_hits)

    first = next(
        (p for seq in (baseline, current) for p in seq),
        None,
    )
    if first is not None:
        lat0 = first.lat
    else:
        lat0 = next((p[0] for seq in (baseline_coverage, current_coverage) for p in seq), 0.0)

    base_grid, cur_grid = _Grid(match_radius_m, lat0), _Grid(match_radius_m, lat0)
    for c in base:
        base_grid.add(c.lat, c.lon, c)
    for c in cur:
        cur_grid.add(c.lat, c.lon, c)
    base_cov = _coverage_grid(baseline_coverage, coverage_radius_m, lat0)
    cur_cov = _coverage_grid(current_coverage, coverage_radius_m, lat0)

    out: list[PotholeStatus] = []
    for c in cur:
        if base_grid.near(c.lat, c.lon, match_radius_m):
            status = Status.PERSISTENT
        elif base_cov.near(c.lat, c.lon, coverage_radius_m):
            status = Status.NEW
        else:
            status = Status.UNCONFIRMED
        out.append(PotholeStatus(c.lat, c.lon, status, c.conf, c.hits))

    for c in base:
        if cur_grid.near(c.lat, c.lon, match_radius_m):
            continue  # already reported as persistent
        status = Status.FIXED if cur_cov.near(c.lat, c.lon, coverage_radius_m) else Status.UNCONFIRMED
        out.append(PotholeStatus(c.lat, c.lon, status, c.conf, c.hits))
    return out
