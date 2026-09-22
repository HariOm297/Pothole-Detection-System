"""Reproducible demo of the whole chain: photos in, change-tracking map out.

    python scripts/demo_run.py                      # places pothole photos along NH-44, 2 passes
    python scripts/demo_run.py --photos C:/photos --csv C:/photos/meta.csv   # your own photos
    python scripts/demo_run.py --figure docs/demo_map.png

Synthetic mode uses the public RDD2022 India pothole images (real Indian road damage) and
places them along the NH-44 geometry inside the study area as two passes in time. That is a
**demo of the pipeline**, not a survey of the real road: no public street imagery exists for
Panipat (see README). With `--photos` the same chain runs on your own geotagged photos.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from pothole.analysis import run_analysis  # noqa: E402
from pothole.config import load_area, load_config  # noqa: E402
from pothole.coverage import coverage_stats  # noqa: E402
from pothole.db import (  # noqa: E402
    all_image_points,
    connect,
    images_to_process,
    insert_local_images,
    save_detections,
    set_image_path,
    upsert_images,
)
from pothole.detect import detect_image, load_model, locate  # noqa: E402
from pothole.geo import interpolate_polyline  # noqa: E402
from pothole.report import save_outputs  # noqa: E402

SCENES = 20          # groups of 3 photos showing the same stretch of road
PERSISTENT = 12      # seen in both passes
FIXED = 4            # seen in pass 1, road clean in pass 2
ROUTE_STEP_M = 8.0   # photo spacing along the road
DATASET = "vidishbijalwan/rdd2022-india-pothole-d40"

def bearing(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    dlon = lo2 - lo1
    return (
        math.degrees(
            math.atan2(
                math.sin(dlon) * math.cos(la2),
                math.cos(la1) * math.sin(la2) - math.sin(la1) * math.cos(la2) * math.cos(dlon),
            )
        )
        + 360
    ) % 360

def find_pothole_photos() -> pathlib.Path:
    """RDD2022 India pothole images: local cache first, else kagglehub download."""
    import kagglehub

    root = pathlib.Path(kagglehub.dataset_download(DATASET))
    for images in sorted(root.rglob("images")):
        if images.is_dir() and any(images.glob("*.jpg")):
            return images
    raise SystemExit(f"No images found under {root}")

def synthetic_rows(cfg: dict, images_dir: pathlib.Path, per_pass: int, date1: str, date2: str):
    """Place photos along NH-44 (inside the study area) as two passes in time."""
    area = load_area(cfg)
    highway = cfg["area"].get("highway_geojson")
    if not highway or not pathlib.Path(highway).exists():
        raise SystemExit(
            "Synthetic mode needs data/highway.geojson (the NH-44 line). "
            "Run with --photos to use your own images instead."
        )
    line = max(
        json.load(open(highway))["features"][0]["geometry"]["coordinates"], key=len
    )
    route = [
        p for p in interpolate_polyline([(la, lo) for lo, la in line], ROUTE_STEP_M)
        if area.contains(*p)
    ]
    if len(route) < per_pass + 1:
        raise SystemExit(f"Road geometry inside the study area is too short ({len(route)} points)")

    import numpy as np
    from PIL import Image

    images = sorted(images_dir.glob("*.jpg"))
    out_dir = pathlib.Path(cfg["paths"]["images"])
    out_dir.mkdir(parents=True, exist_ok=True)
    blank = out_dir / "demo_blank.jpg"          # "clean road" frames
    Image.fromarray(np.full((720, 720, 3), 110, np.uint8)).save(blank, quality=85)

    t1 = int(datetime.fromisoformat(date1).replace(tzinfo=timezone.utc).timestamp() * 1000)
    t2 = int(datetime.fromisoformat(date2).replace(tzinfo=timezone.utc).timestamp() * 1000)
    plan: list[tuple[str, int, int, pathlib.Path]] = []
    for k in range(SCENES):                       # scenes: 3 photos each -> a cluster
        scene_img = images[k % len(images)]
        in_pass1 = k >= PERSISTENT + FIXED        # "new" scenes were clean in pass 1
        in_pass2 = not (PERSISTENT <= k < PERSISTENT + FIXED)
        for p in range(3 * k, 3 * k + 3):
            plan.append(("pass1", p, t1, scene_img if in_pass1 else blank))
            plan.append(("pass2", p, t2, scene_img if in_pass2 else blank))
    # filler photos: coverage for the rest of the route
    for p in range(SCENES * 3, per_pass):
        plan.append(("pass1", p, t1, images[(300 + p) % len(images)]))
        plan.append(("pass2", p, t2, images[(700 + p) % len(images)]))

    rows = []
    for tag, p, when, src in plan:
        dst = out_dir / f"demo_{tag}_{p:03d}.jpg"
        shutil.copy2(src, dst)
        rows.append({
            "id": f"demo:{tag}:{p:03d}", "captured_at": when,
            "lat": route[p][0], "lon": route[p][1],
            "heading": bearing(route[p], route[min(p + 1, len(route) - 1)]),
            "url": None, "path": str(dst),
        })
    rows = list({r["id"]: r for r in rows}.values())
    print(f"placed {len(rows)} photos along {len(route) * ROUTE_STEP_M / 1000:.1f} km of NH-44")
    return rows

def own_photo_rows(args, cfg: dict):
    from pothole.ingest import collect_rows, read_csv

    csv_map = read_csv(args.csv) if args.csv else None
    rows, skipped = collect_rows(args.photos, csv_map)
    print(f"your photos: {len(rows)} with a location, {skipped} skipped")
    if not rows:
        raise SystemExit("None of the photos have a location (pass --csv or use EXIF GPS).")
    for r in rows:
        pathlib.Path(r["path"]).resolve()
    return rows

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--photos", help="your own photo folder (skips the synthetic placement)")
    ap.add_argument("--csv", help="CSV with file,lat,lon[,date,heading] for --photos")
    ap.add_argument("--per-pass", type=int, default=100, help="photos per pass (synthetic mode)")
    ap.add_argument("--date1", default="2025-06-15", help="first pass date")
    ap.add_argument("--date2", default="2026-09-10", help="second pass date")
    ap.add_argument("--split", default=None, help="split date (default: 1 Jan between the passes)")
    ap.add_argument("--figure", default=None, help="write a summary PNG here")
    args = ap.parse_args()

    cfg = load_config(args.config)
    cfg["paths"]["db"] = str(pathlib.Path(cfg["paths"]["db"]))
    conn = connect(cfg["paths"]["db"])
    with conn:  # fresh demo: drop earlier demo rows, keep anything you ingested yourself
        conn.execute("DELETE FROM detections WHERE image_id LIKE 'demo:%'")
        conn.execute("DELETE FROM images WHERE id LIKE 'demo:%'")

    if args.photos:
        rows = own_photo_rows(args, cfg)
        insert_local_images(conn, rows)
    else:
        rows = synthetic_rows(cfg, find_pothole_photos(), args.per_pass, args.date1, args.date2)
        upsert_images(conn, rows)
        for r in rows:
            set_image_path(conn, r["id"], r["path"])

    d = cfg["detection"]
    model = load_model(d["weights"])
    todo = images_to_process(conn)
    print(f"detect: running YOLO on {len(todo)} photos")
    found = 0
    for n, row in enumerate(todo, 1):
        dets = detect_image(model, row["path"], d["conf"], d["imgsz"], d["min_y_frac"])
        for det in dets:
            det["lat"], det["lon"] = locate(row["lat"], row["lon"], row["heading"], d["offset_m"])
        save_detections(conn, row["id"], dets)
        found += len(dets)
        if n % 100 == 0:
            print(f"  {n}/{len(todo)} photos, {found} detections")
    print(f"detect: {found} detections")

    area = load_area(cfg)
    points = all_image_points(conn)
    by_year: dict[int, list] = {}
    for r in points:
        year = datetime.fromtimestamp(r["captured_at"] / 1000, tz=timezone.utc).year
        by_year.setdefault(year, []).append((r["lat"], r["lon"]))
    print("coverage (100 m cells):")
    for year in sorted(by_year):
        s = coverage_stats(by_year[year], area, 100.0)
        print(
            f"  {year}: {s['images_in_area']} images, "
            f"{s['cells_covered']}/{s['cells_total']} cells"
        )

    split = args.split or f"{min(by_year) + 1}-01-01"
    split_ms = int(datetime.fromisoformat(split).replace(tzinfo=timezone.utc).timestamp() * 1000)
    statuses = run_analysis(conn, split_ms, cfg)
    counts = Counter(s.status.value for s in statuses)
    print(f"analyze (baseline < {split}): {dict(counts)}")
    save_outputs(statuses, area, cfg["paths"]["outputs"])
    print(f"wrote {cfg['paths']['outputs']}/map.html and potholes.geojson")

    if args.figure:
        make_figure(cfg, statuses, args.figure)

def make_figure(cfg: dict, statuses, path: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    style = {
        "new": "#d62728", "persistent": "#ff9500",
        "fixed": "#2ca02c", "unconfirmed": "#8c8c8c",
    }
    fig, ax = plt.subplots(figsize=(9.5, 8.5), dpi=110)
    highway = cfg["area"].get("highway_geojson")
    if highway and pathlib.Path(highway).exists():
        lines = json.load(open(highway))["features"][0]["geometry"]["coordinates"]
        for n, line in enumerate(lines):
            ax.plot([c[0] for c in line], [c[1] for c in line], "-", color="#3b6fb6",
                    lw=2.5, alpha=0.55, label="NH-44 (OSM)" if n == 0 else None, zorder=1)
    counts = Counter(s.status.value for s in statuses)
    for status, color in style.items():
        sel = [s for s in statuses if s.status.value == status]
        if sel:
            ax.scatter([s.lon for s in sel], [s.lat for s in sel], s=95, c=color,
                       edgecolors="black", linewidths=0.7, alpha=0.9,
                       label=f"{status} ({len(sel)})", zorder=3)
    xs = [s.lon for s in statuses]
    ys = [s.lat for s in statuses]
    ax.set_xlim(min(xs) - 0.004, max(xs) + 0.004)
    ax.set_ylim(min(ys) - 0.004, max(ys) + 0.004)
    ax.set_xlabel("longitude")
    ax.set_ylabel("latitude")
    summary = ", ".join(f"{k} {v}" for k, v in counts.items())
    ax.set_title(
        "Pothole change tracking - demo run\n"
        f"{sum(counts.values())} potholes classified: {summary}",
        fontsize=11,
    )
    ax.legend(loc="lower left", fontsize=9, framealpha=0.95)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    print(f"wrote {path}")

if __name__ == "__main__":
    main()
