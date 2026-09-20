"""Command line: fetch imagery, run detection, analyse changes, build the map."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .analysis import run_analysis
from .config import load_area, load_config
from .coverage import coverage_stats
from .db import (
    all_image_points,
    connect,
    images_to_download,
    images_to_process,
    save_detections,
    set_image_path,
    upsert_images,
)


def _iso(day: str | None) -> str | None:
    return f"{day}T00:00:00Z" if day and len(day) == 10 else day


def cmd_fetch(args, cfg) -> None:
    from .mapillary import download_image, fetch_area

    area = load_area(cfg)
    tiles = area.tiles()
    print(f"{area.name}: {len(tiles)} tiles to query")
    conn = connect(cfg["paths"]["db"])
    rows = fetch_area(tiles, area.contains, _iso(args.start), _iso(args.end))
    upsert_images(conn, rows)
    print(f"{len(rows)} images stored in {cfg['paths']['db']}")
    if not args.download:
        return

    img_dir = Path(cfg["paths"]["images"])
    todo = images_to_download(conn)
    print(f"Downloading {len(todo)} images...")

    def job(row):
        dest = img_dir / f"{row['id']}.jpg"
        return row["id"], str(dest), download_image(row["url"], dest)

    with ThreadPoolExecutor(max_workers=8) as pool:
        for n, (image_id, dest, ok) in enumerate(pool.map(job, todo), 1):
            if ok:
                set_image_path(conn, image_id, dest)
            if n % 100 == 0:
                print(f"  {n}/{len(todo)}")


def cmd_detect(args, cfg) -> None:
    from .detect import detect_image, load_model, locate

    d = cfg["detection"]
    model = load_model(d["weights"])
    conn = connect(cfg["paths"]["db"])
    todo = images_to_process(conn, args.limit)
    print(f"Running detector on {len(todo)} images")
    found = 0
    for n, row in enumerate(todo, 1):
        dets = detect_image(model, row["path"], d["conf"], d["imgsz"], d["min_y_frac"])
        for det in dets:
            det["lat"], det["lon"] = locate(row["lat"], row["lon"], row["heading"], d["offset_m"])
        save_detections(conn, row["id"], dets)
        found += len(dets)
        if n % 100 == 0:
            print(f"  {n}/{len(todo)} images, {found} detections")
    print(f"Done: {found} detections")


def cmd_analyze(args, cfg) -> None:
    from .report import save_outputs

    split = datetime.fromisoformat(args.split).replace(tzinfo=timezone.utc)
    conn = connect(cfg["paths"]["db"])
    statuses = run_analysis(conn, int(split.timestamp() * 1000), cfg)
    counts = Counter(s.status.value for s in statuses)
    print(f"Baseline = before {args.split}, current = on/after. Results: {dict(counts)}")
    save_outputs(statuses, load_area(cfg), cfg["paths"]["outputs"])
    print(f"Wrote {cfg['paths']['outputs']}/map.html and potholes.geojson")


def cmd_coverage(args, cfg) -> None:
    area = load_area(cfg)
    conn = connect(cfg["paths"]["db"])
    rows = all_image_points(conn)
    conn.close()
    if not rows:
        print("No images in the database yet. Run `pothole fetch` first.")
        return
    by_year: dict[int, list[tuple[float, float]]] = {}
    for r in rows:
        year = datetime.fromtimestamp(r["captured_at"] / 1000, tz=timezone.utc).year
        by_year.setdefault(year, []).append((r["lat"], r["lon"]))
    everything = coverage_stats([(r["lat"], r["lon"]) for r in rows], area, args.cell)
    print(f"{area.name}, {args.cell:.0f} m cells - all years: {everything}")
    for year in sorted(by_year):
        print(f"  {year}: {coverage_stats(by_year[year], area, args.cell)}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="pothole")
    ap.add_argument("--config", default="config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="get Mapillary image metadata for the study area")
    f.add_argument("--start", help="YYYY-MM-DD, only images captured after")
    f.add_argument("--end", help="YYYY-MM-DD, only images captured before")
    f.add_argument("--download", action="store_true", help="also download thumbnails")
    f.set_defaults(func=cmd_fetch)

    d = sub.add_parser("detect", help="run YOLO on downloaded images")
    d.add_argument("--limit", type=int)
    d.set_defaults(func=cmd_detect)

    c = sub.add_parser("coverage", help="how much of the city has imagery, per year")
    c.add_argument("--cell", type=float, default=100.0, help="cell size in metres")
    c.set_defaults(func=cmd_coverage)

    a = sub.add_parser("analyze", help="classify potholes as new/persistent/fixed and build map")
    a.add_argument("--split", required=True, help="YYYY-MM-DD: before = baseline, after = current")
    a.set_defaults(func=cmd_analyze)

    args = ap.parse_args(argv)
    args.func(args, load_config(args.config))


if __name__ == "__main__":
    main()
