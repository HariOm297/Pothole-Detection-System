# Data

Raw dumps (`raw/`, `yolo/`, `images/`) and the database are git-ignored. The study-area
files **are** committed so that a clone reproduces the same query area.

- `highway.geojson` - 11 continuous stretches of NH-44 around Panipat (55 km), from
  OpenStreetMap (ODbL, downloaded 2026-09-20) with the Overpass query below. Each stretch is
  its own LineString: OSM maps the highway in pieces, and separate lines must stay separate.
- `area.geojson`   - optional city polygon. If missing, the bbox in `config.yaml` is used;
  draw one at geojson.io to trade a rectangular area for the real city outline.
- `raw/`     - RDD2022 India subset. Easiest: `kagglehub.dataset_download('musfequa/india-road-damage')`
               (same layout as the official zip: `India/train/images`, `India/train/annotations/xmls`).
               Official source: https://doi.org/10.6084/m9.figshare.21431547 (13 GB, all countries).
- `yolo/`    - converted dataset (`python scripts/rdd_to_yolo.py --src .../India --out data/yolo`)
- `images/`  - Mapillary thumbnails fetched for the study area
- `pothole.db` - SQLite: images, detections

```overpassql
[out:json][timeout:90];
way["highway"]["ref"~"^(NH ?44|NH-44)"](29.28,76.80,29.55,77.15);
out geom;
```
