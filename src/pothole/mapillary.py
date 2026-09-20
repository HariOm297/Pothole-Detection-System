"""Minimal Mapillary Graph API v4 client (images by bounding box).

Set the token in the environment:  export MAPILLARY_TOKEN="MLY|..."
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import requests

from .geo import BBox, split_bbox

API = "https://graph.mapillary.com/images"
FIELDS = "id,captured_at,compass_angle,geometry,is_pano,thumb_1024_url"


class MapillaryError(RuntimeError):
    pass


def _token() -> str:
    tok = os.environ.get("MAPILLARY_TOKEN")
    if not tok:
        raise MapillaryError(
            "Set MAPILLARY_TOKEN (create an app at mapillary.com/dashboard/developers)."
        )
    return tok


def _request(params: dict, retries: int = 4) -> list[dict]:
    for attempt in range(retries):
        r = requests.get(API, params=params, timeout=60)
        if r.status_code == 200:
            return r.json().get("data", [])
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(2**attempt)
            continue
        raise MapillaryError(f"HTTP {r.status_code}: {r.text[:200]}")
    raise MapillaryError("Mapillary API kept failing after retries")


def fetch_bbox(
    bbox: BBox,
    start: str | None = None,
    end: str | None = None,
    limit: int = 2000,
    depth: int = 0,
    max_depth: int = 3,
) -> list[dict]:
    """Fetch images in a bbox. If the result hits `limit`, split the box and retry."""
    params = {
        "access_token": _token(),
        "fields": FIELDS,
        "bbox": ",".join(str(v) for v in bbox),
        "limit": limit,
    }
    if start:
        params["start_captured_at"] = start
    if end:
        params["end_captured_at"] = end
    data = _request(params)
    if len(data) >= limit and depth < max_depth:
        out: list[dict] = []
        for sub in split_bbox(bbox):
            out.extend(fetch_bbox(sub, start, end, limit, depth + 1, max_depth))
        return out
    return data


def to_row(item: dict) -> dict | None:
    if item.get("is_pano") or not item.get("thumb_1024_url"):
        return None  # 360 images are distorted; skip them
    lon, lat = item["geometry"]["coordinates"]
    return {
        "id": str(item["id"]),
        "captured_at": int(item["captured_at"]),
        "lat": lat,
        "lon": lon,
        "heading": item.get("compass_angle"),
        "url": item["thumb_1024_url"],
    }


def fetch_area(
    tiles: Sequence[BBox],
    keep: Callable[[float, float], bool],
    start: str | None = None,
    end: str | None = None,
    progress=print,
) -> list[dict]:
    rows: dict[str, dict] = {}
    for n, tile in enumerate(tiles, 1):
        for item in fetch_bbox(tile, start, end):
            row = to_row(item)
            if row is None:
                continue
            if keep(row["lat"], row["lon"]):
                rows[row["id"]] = row
        progress(f"tile {n}/{len(tiles)}: {len(rows)} images kept so far")
    return list(rows.values())


def download_image(url: str, dest: Path) -> bool:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return True
    r = requests.get(url, timeout=60)
    if r.status_code != 200:
        return False
    dest.write_bytes(r.content)
    return True
