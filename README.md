# pothole-monitor

Road-health monitoring for the **Panipat - Karnal stretch (NH-44 / GT Road)**.
A YOLOv8 model finds potholes in street-level imagery; detections are geo-tagged and compared
across time to flag **new** potholes and **likely repaired** ones. Results are shown on a map.

> Status: pipeline and tests are in place. Model training on real data and the first full
> corridor run are the next steps (see Roadmap). No accuracy numbers are claimed yet.

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

### The one idea that matters: coverage-aware change detection

"Not detected last time" does **not** mean "new pothole" - maybe nobody photographed that spot.
So each status needs imagery evidence:

| Status | Meaning |
|---|---|
| `new` | detected now, *not* detected before, and we had imagery of that spot before |
| `persistent` | detected in both periods |
| `fixed` | detected before, not detected now, and we have recent imagery of that spot |
| `unconfirmed` | no imagery of that spot in the other period, so we can't tell |

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

# 2. Get imagery for the corridor (free Mapillary token)
export MAPILLARY_TOKEN="MLY|..."
pothole fetch --start 2022-01-01 --download

# 3. Detect, compare, visualise
pothole detect
pothole analyze --split 2024-06-01      # before = baseline, on/after = current
streamlit run app/dashboard.py
```

Docker (dashboard only): `docker build -t pothole-monitor . && docker run -p 8501:8501 -v $(pwd)/data:/app/data pothole-monitor`

## Repo layout

```
src/pothole/   geo, compare (change detection), db, mapillary, detect, analysis, report, cli
scripts/       rdd_to_yolo.py (dataset conversion), train.py
notebooks/     train_colab.ipynb
app/           Streamlit dashboard
tests/         geo, compare, db, converter tests (run in CI, no GPU needed)
config.yaml    corridor, detection and comparison settings
```

## Results

| Model | Data | Precision | Recall | mAP@0.5 |
|---|---|---|---|---|
| YOLOv8s | RDD2022 India (potholes only) | TBD | TBD | TBD |

Fill this in after training, together with a few failure-case images.

## Known limitations

- **Coverage:** Mapillary coverage along the corridor is uneven and changes over time. Run
  `pothole fetch` first and check how many images and which dates you actually get.
- **Domain gap:** the model trains on RDD2022 but runs on Mapillary images (different cameras,
  angles, weather). Check precision by hand on ~100 Mapillary images before trusting the map.
- **Position accuracy:** a pothole is placed a fixed distance ahead of the camera along its heading
  (`detection.offset_m`), so expect errors of several metres. GPS on crowdsourced images is noisy.
- **Severity** is a rough proxy from box size, which depends on the camera.
- **"Fixed"** means "not seen in newer imagery", which can also be a missed detection.
- `corridor.waypoints` in `config.yaml` are approximate. For a precise corridor, export the road
  as a LineString GeoJSON to `data/corridor.geojson`.

## Roadmap

- [x] Geo utilities, coverage-aware comparison, DB, Mapillary client, CLI, dashboard, CI
- [ ] Train on RDD2022 India and record metrics
- [ ] First full corridor run; manually verify a sample of detections
- [ ] Add a small hand-labelled Mapillary set from the corridor to close the domain gap
- [ ] Deploy the dashboard (Hugging Face Spaces / Render)
- [ ] Citizen reporting via Telegram bot
