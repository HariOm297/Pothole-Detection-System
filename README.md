# pothole-monitor

Pothole detection and tracking for **Panipat city** - inner streets and the NH-44 highway stretch.
A YOLOv8 model finds potholes in street-level imagery; detections are geo-tagged and compared
across time to flag **new** potholes and **likely repaired** ones. Results are shown on a map.

> Status: pipeline and tests are in place. Model training on real data and the first full city
> run are the next steps (see Roadmap). No accuracy numbers are claimed yet.

## How it works

```
Mapillary API (images + GPS + date)      RDD2022 India (labelled potholes)
        |                                         |
        v                                         v
  data/images  ------------------->  YOLOv8 fine-tuning (Colab GPU)  -> models/best.pt
        |                                         |
        +--------------> detect (per image) <-----+
                               |
                     geo-tag (camera pos + heading offset)
                               |
                          SQLite (images, detections)
                               |
        cluster frames -> compare baseline vs current period
                               |
              new / persistent / fixed / unconfirmed
                               |
                    map.html + GeoJSON + Streamlit dashboard
```

### Coverage-aware change detection

"Not detected last time" does **not** mean "new pothole" - maybe nobody photographed that spot.
So each status needs imagery evidence:

| Status | Meaning |
|---|---|
| `new` | detected now, *not* detected before, and we had imagery of that spot before |
| `persistent` | detected in both periods |
| `fixed` | detected before, not detected now, and we have recent imagery of that spot |
| `unconfirmed` | no imagery of that spot in the other period, so we can't tell |

This matters even more in a city: inner lanes are photographed far less often than main roads.

## Study area

`config.yaml` starts with a generous bounding box around Panipat that includes the NH-44 stretch
through the city. To tighten it:

1. Draw the city boundary at [geojson.io](https://geojson.io) and save it as `data/area.geojson`
   (one or more polygons).
2. If you also want NH-44 beyond that boundary, draw it as a line and save `data/highway.geojson`
   (images within `highway_buffer_m` of the line are kept).

## Quick start

```bash
git clone https://github.com/<you>/pothole-monitor && cd pothole-monitor
python -m venv .venv && source .venv/bin/activate
pip install -e ".[ml,app,dev]"
pytest -q

# 1. Train (Colab GPU): open notebooks/train_colab.ipynb   ->  models/best.pt
#    or locally:
python scripts/rdd_to_yolo.py --src data/raw/India --out data/yolo
python scripts/train.py

# 2. Get imagery for the city (free Mapillary token) and check what you actually have
export MAPILLARY_TOKEN="MLY|..."
pothole fetch --start 2022-01-01 --download
pothole coverage                        # share of the city with imagery, per year

# 3. Detect, compare, visualise
pothole detect
pothole analyze --split 2024-06-01      # before = baseline, on/after = current
streamlit run app/dashboard.py
```

Docker (dashboard only): `docker build -t pothole-monitor . && docker run -p 8501:8501 -v $(pwd)/data:/app/data pothole-monitor`

## Repo layout

```
src/pothole/   geo, config (study area), compare (change detection), coverage, db,
               mapillary, detect, analysis, report, cli
scripts/       rdd_to_yolo.py (dataset conversion), train.py
notebooks/     train_colab.ipynb
app/           Streamlit dashboard
tests/         geo, area, compare, db, converter tests (run in CI, no GPU needed)
config.yaml    study area, detection and comparison settings
```

## Results

| Model | Data | Precision | Recall | mAP@0.5 |
|---|---|---|---|---|
| YOLOv8s | RDD2022 India (potholes only) | TBD | TBD | TBD |

Fill this in after training, together with a few failure-case images.

## Known limitations

- **Inner-lane coverage is the big unknown.** Crowdsourced imagery is dense on main roads and
  thin in narrow lanes. Run `pothole coverage` first: if a year has very low coverage, change
  tracking for that year is not meaningful, and lane potholes will stay `unconfirmed`.
  Lower `compare.min_hits` to 1 if lanes only have single passes (expect more false positives).
- **Domain gap:** the model trains on RDD2022 but runs on Mapillary images (different cameras,
  angles, weather). Check precision by hand on ~100 Mapillary images before trusting the map.
- **Position accuracy:** a pothole is placed a fixed distance ahead of the camera along its
  heading (`detection.offset_m`). GPS between tall buildings is noisy, so expect errors of
  several metres; in narrow lanes two potholes can end up merged into one.
- **Severity** is a rough proxy from box size, which depends on the camera.
- **"Fixed"** means "not seen in newer imagery", which can also be a missed detection.
- The default bounding box is approximate and includes some outskirts and farmland.

## Roadmap

- [x] Geo utilities, coverage-aware comparison, coverage report, DB, Mapillary client, CLI,
      dashboard, CI
- [ ] Train on RDD2022 India and record metrics
- [ ] First full city run; manually verify a sample of detections
- [ ] Web app for citizens and drivers (near-me, route check) and deploy it
- [ ] Fill lane coverage gaps with citizen reports
