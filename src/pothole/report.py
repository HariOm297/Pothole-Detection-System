"""Map / GeoJSON output."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import folium

from .compare import PotholeStatus, Status
from .config import Area

COLORS = {
    Status.NEW: "#d62728",
    Status.PERSISTENT: "#ff7f0e",
    Status.FIXED: "#2ca02c",
    Status.UNCONFIRMED: "#7f7f7f",
}

LEGEND = """
<div style="position: fixed; bottom: 24px; left: 24px; z-index: 9999; background: white;
     padding: 8px 12px; border: 1px solid #999; border-radius: 6px; font-size: 13px;">
  <b>Pothole status</b><br>
  <span style="color:#d62728">&#9679;</span> new<br>
  <span style="color:#ff7f0e">&#9679;</span> persistent<br>
  <span style="color:#2ca02c">&#9679;</span> fixed (not seen in newer imagery)<br>
  <span style="color:#7f7f7f">&#9679;</span> unconfirmed (no imagery in other period)
</div>
"""


def to_geojson(statuses: Sequence[PotholeStatus]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s.lon, s.lat]},
                "properties": {"status": s.status.value, "conf": round(s.conf, 3), "hits": s.hits},
            }
            for s in statuses
        ],
    }


def make_map(statuses: Sequence[PotholeStatus], area: Area) -> folium.Map:
    m = folium.Map(location=area.centre(), zoom_start=13, tiles="OpenStreetMap")
    for poly in area.polygons:
        folium.Polygon(
            poly, color="#1f77b4", weight=2, fill=True, fill_opacity=0.04
        ).add_to(m)
    for line in area.highway or []:
        folium.PolyLine(line, color="#1f77b4", weight=3, opacity=0.5).add_to(m)
    for s in statuses:
        folium.CircleMarker(
            (s.lat, s.lon),
            radius=6,
            color=COLORS[s.status],
            fill=True,
            fill_opacity=0.8,
            popup=f"{s.status.value} | conf {s.conf:.2f} | seen {s.hits}x",
        ).add_to(m)
    m.get_root().html.add_child(folium.Element(LEGEND))
    return m


def save_outputs(statuses: Sequence[PotholeStatus], area: Area, out_dir: str) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "potholes.geojson").write_text(json.dumps(to_geojson(statuses)))
    make_map(statuses, area).save(str(out / "map.html"))
