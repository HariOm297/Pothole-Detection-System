# Pothole-Detection-System

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/HariOm297/Pothole-Detection-System/blob/main/notebooks/train_colab.ipynb)

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
2. `data/highway.geojson` is already included: 11 continuous stretches of NH-44 (55 km, OSM
   ODbL) that carry the study area north and south of the city bbox - images within
   `highway_buffer_m` of a line are kept. If you draw your own (geojson.io), several separate
   lines are fine: each LineString is treated as its own stretch of road.

## Quick start

```bash
git clone https://github.com/HariOm297/Pothole-Detection-System && cd Pothole-Detection-System
python -m venv .venv && source .venv/bin/activate
pip install -e ".[ml,app,dev]"
pytest -q

# 1. Train (Colab GPU): open notebooks/train_colab.ipynb   ->  models/best.pt
#    or locally (downloads the RDD2022 India subset, ~500 MB, from a Kaggle mirror):
pip install kagglehub
python -c "import kagglehub; print(kagglehub.dataset_download('musfequa/india-road-damage'))"
python scripts/rdd_to_yolo.py --src <printed path>/India --out data/yolo   # -> 1530 pothole images
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

Docker (dashboard only): `docker build -t pothole-detection . && docker run -p 8501:8501 -v $(pwd)/data:/app/data pothole-detection`

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

## Training data

[RDD2022](https://doi.org/10.6084/m9.figshare.21431547) (Arya et al., 2022), **India subset only**:
7,706 annotated images, of which 1,530 contain potholes (class `D40`, 3,187 boxes). The
converter keeps those 1,530 plus 10% background images and splits 85/15 into train/val.
The official `RDD2022_India.zip` link now returns 403, so the notebook pulls the identical
Kaggle mirror `musfequa/india-road-damage` (no Kaggle account needed via `kagglehub`).

## Results

| Model | Data | Precision | Recall | mAP@0.5 | mAP@0.5:0.95 |
|---|---|---|---|---|---|
| YOLOv8s, 60 epochs, 640px | RDD2022 India, potholes only (1431 train / 252 val) | TBD | TBD | TBD | TBD |

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
