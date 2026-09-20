# Data

Nothing in this folder is committed except this file.

- `raw/`     - RDD2022 download (use only the `India/` folder). See github.com/sekilab/RoadDamageDetector for download links.
- `yolo/`    - converted dataset (`python scripts/rdd_to_yolo.py`)
- `images/`  - Mapillary thumbnails fetched for the corridor
- `pothole.db` - SQLite: images, detections
- `corridor.geojson` - optional precise road line (LineString)
