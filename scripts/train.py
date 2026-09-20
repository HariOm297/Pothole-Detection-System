"""Fine-tune YOLOv8 on the converted pothole dataset and export best weights."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/yolo/data.yaml")
    ap.add_argument("--model", default="yolov8s.pt")
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--name", default="pothole_v1")
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    from ultralytics import YOLO

    model = YOLO(args.model)
    model.train(
        data=args.data, epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
        project="runs", name=args.name, device=args.device,
        hsv_v=0.5, degrees=3.0, translate=0.1, scale=0.5, mosaic=1.0,
    )
    print(f"run dir: {model.trainer.save_dir}")
    m = model.val()
    print(f"precision={m.box.mp:.3f} recall={m.box.mr:.3f} "
          f"mAP50={m.box.map50:.3f} mAP50-95={m.box.map:.3f}")

    Path("models").mkdir(exist_ok=True)
    shutil.copy2(model.trainer.best, "models/best.pt")
    print("saved models/best.pt")


if __name__ == "__main__":
    main()
