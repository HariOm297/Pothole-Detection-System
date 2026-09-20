"""Glue between the database and the change-detection logic."""

from __future__ import annotations

import sqlite3

from .compare import Detection, PotholeStatus, compare_periods
from .db import load_coverage, load_detections


def run_analysis(conn: sqlite3.Connection, split_ms: int, cfg: dict) -> list[PotholeStatus]:
    """Images/detections before `split_ms` are the baseline, the rest are 'current'."""
    c = cfg["compare"]
    dets = load_detections(conn)
    cov = load_coverage(conn)
    baseline = [Detection(r["lat"], r["lon"], r["conf"]) for r in dets
                if r["captured_at"] < split_ms]
    current = [Detection(r["lat"], r["lon"], r["conf"]) for r in dets
               if r["captured_at"] >= split_ms]
    base_cov = [(r["lat"], r["lon"]) for r in cov if r["captured_at"] < split_ms]
    cur_cov = [(r["lat"], r["lon"]) for r in cov if r["captured_at"] >= split_ms]
    return compare_periods(
        baseline, current, base_cov, cur_cov,
        cluster_radius_m=c["cluster_radius_m"],
        match_radius_m=c["match_radius_m"],
        coverage_radius_m=c["coverage_radius_m"],
        min_hits=c["min_hits"],
    )
