"""Convert RDD2022 (Pascal VOC XML) to YOLO format, keeping only potholes (class D40).

Point --src at the country folder you want (e.g. data/raw/India), not the whole dataset:
    python scripts/rdd_to_yolo.py --src data/raw/India --out data/yolo
"""

from __future__ import annotations

import argparse
import random
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

POTHOLE = "D40"
IMG_EXT = {".jpg", ".jpeg", ".png"}


def parse_xml(path: Path) -> list[str] | None:
    """Return YOLO label lines for potholes, or None if the file has no usable size."""
    root = ET.parse(path).getroot()
    size = root.find("size")
    try:
        w, h = int(size.findtext("width")), int(size.findtext("height"))
    except (AttributeError, TypeError, ValueError):
        return None
    if w <= 0 or h <= 0:
        return None
    lines = []
    for obj in root.iter("object"):
        if obj.findtext("name") != POTHOLE:
            continue
        bb = obj.find("bndbox")
        x1, y1, x2, y2 = (float(bb.findtext(k)) for k in ("xmin", "ymin", "xmax", "ymax"))
        x1, x2 = max(0.0, min(x1, x2)), min(float(w), max(x1, x2))
        y1, y2 = max(0.0, min(y1, y2)), min(float(h), max(y1, y2))
        if x2 - x1 < 2 or y2 - y1 < 2:
            continue
        cx, cy = (x1 + x2) / 2 / w, (y1 + y2) / 2 / h
        lines.append(f"0 {cx:.6f} {cy:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("data/yolo"))
    ap.add_argument("--val-frac", type=float, default=0.15)
    ap.add_argument("--max-bg-ratio", type=float, default=0.1,
                    help="images without potholes, as a fraction of images with potholes")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    images = {p.stem: p for p in args.src.rglob("*") if p.suffix.lower() in IMG_EXT}
    positives, negatives = [], []
    for xml in sorted(args.src.rglob("*.xml")):
        img = images.get(xml.stem)
        lines = parse_xml(xml)
        if img is None or lines is None:
            continue
        (positives if lines else negatives).append((img, lines))

    rng = random.Random(args.seed)
    rng.shuffle(negatives)
    negatives = negatives[: int(len(positives) * args.max_bg_ratio)]
    samples = positives + negatives
    rng.shuffle(samples)
    n_val = int(len(samples) * args.val_frac)
    splits = {"val": samples[:n_val], "train": samples[n_val:]}

    for split, items in splits.items():
        (args.out / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.out / "labels" / split).mkdir(parents=True, exist_ok=True)
        for img, lines in items:
            shutil.copy2(img, args.out / "images" / split / img.name)
            (args.out / "labels" / split / f"{img.stem}.txt").write_text("\n".join(lines))

    (args.out / "data.yaml").write_text(
        f"path: {args.out.resolve()}\ntrain: images/train\nval: images/val\nnames:\n  0: pothole\n"
    )
    print(f"positives={len(positives)} background={len(negatives)} "
          f"train={len(splits['train'])} val={len(splits['val'])}")


if __name__ == "__main__":
    main()
