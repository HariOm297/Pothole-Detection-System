"""YOLO inference on street-level images. `ultralytics` is imported lazily."""

from __future__ import annotations

from .geo import LatLon, offset_point


def severity_from_area(ratio: float, medium: float = 0.005, high: float = 0.02) -> str:
    """Rough severity proxy from the box's share of the frame (camera dependent!)."""
    if ratio >= high:
        return "high"
    if ratio >= medium:
        return "medium"
    return "low"


def load_model(weights: str):
    from ultralytics import YOLO

    return YOLO(weights)


def detect_image(model, path: str, conf: float, imgsz: int, min_y_frac: float) -> list[dict]:
    res = model.predict(source=str(path), conf=conf, imgsz=imgsz, verbose=False)[0]
    h, w = res.orig_shape
    out = []
    for box in res.boxes:
        x1, y1, x2, y2 = (float(v) for v in box.xyxy[0].tolist())
        if (y1 + y2) / 2 / h < min_y_frac:
            continue  # too far away: location estimate and detection are unreliable
        area = (x2 - x1) * (y2 - y1) / (w * h)
        out.append({
            "conf": float(box.conf[0]),
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "area_ratio": area,
            "severity": severity_from_area(area),
        })
    return out


def locate(lat: float, lon: float, heading: float | None, offset_m: float) -> LatLon:
    """Pothole position: shift the camera position forward along its heading."""
    if heading is None:
        return lat, lon
    return offset_point(lat, lon, heading, offset_m)
