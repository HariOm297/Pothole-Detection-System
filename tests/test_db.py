from pothole.db import (
    connect,
    date_range,
    images_to_download,
    images_to_process,
    load_coverage,
    load_detections,
    save_detections,
    set_image_path,
    upsert_images,
)
from pothole.mapillary import to_row


def _img(i, t=1_700_000_000_000):
    return {"id": str(i), "captured_at": t, "lat": 29.5, "lon": 76.97, "heading": 10.0, "url": "u"}


def test_roundtrip(tmp_path):
    conn = connect(tmp_path / "t.db")
    assert upsert_images(conn, [_img(1), _img(2, 1_800_000_000_000)]) == 2
    upsert_images(conn, [_img(1)])  # idempotent
    assert len(images_to_download(conn)) == 2

    set_image_path(conn, "1", "x.jpg")
    assert [r["id"] for r in images_to_process(conn)] == ["1"]

    det = {"lat": 29.5, "lon": 76.97, "conf": 0.8, "area_ratio": 0.01, "severity": "medium",
           "x1": 0, "y1": 0, "x2": 1, "y2": 1}
    save_detections(conn, "1", [det])
    assert images_to_process(conn) == []
    assert len(load_detections(conn)) == 1
    assert len(load_coverage(conn)) == 1
    assert date_range(conn) == (1_700_000_000_000, 1_700_000_000_000)


def test_date_range_empty(tmp_path):
    assert date_range(connect(tmp_path / "e.db")) is None


def test_to_row_skips_panos_and_missing_url():
    base = {"id": 5, "captured_at": 1, "geometry": {"coordinates": [76.9, 29.4]},
            "thumb_1024_url": "http://x", "compass_angle": 90}
    assert to_row({**base, "is_pano": True}) is None
    assert to_row({**base, "thumb_1024_url": None}) is None
    row = to_row(base)
    assert row["lat"] == 29.4 and row["lon"] == 76.9 and row["id"] == "5"
