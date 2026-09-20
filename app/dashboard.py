"""Streamlit dashboard: run with `streamlit run app/dashboard.py`."""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime, timezone

import streamlit as st
from streamlit_folium import st_folium

from pothole.analysis import run_analysis
from pothole.config import load_config, load_corridor
from pothole.db import connect, date_range
from pothole.report import make_map

st.set_page_config(page_title="Panipat-Karnal Road Monitor", layout="wide")
cfg = load_config(os.environ.get("POTHOLE_CONFIG", "config.yaml"))
conn = connect(cfg["paths"]["db"])

st.title("Panipat - Karnal road health")
rng = date_range(conn)
if rng is None:
    st.info("No processed images yet. Run `pothole fetch --download` then `pothole detect`.")
    st.stop()

lo, hi = (datetime.fromtimestamp(t / 1000, tz=timezone.utc).date() for t in rng)
st.sidebar.header("Compare periods")
split = st.sidebar.date_input(
    "Baseline = before this date", value=lo + (hi - lo) / 2, min_value=lo, max_value=hi
)
show = st.sidebar.multiselect(
    "Show", ["new", "persistent", "fixed", "unconfirmed"], default=["new", "persistent", "fixed"]
)

split_ms = int(datetime(split.year, split.month, split.day, tzinfo=timezone.utc).timestamp() * 1000)
statuses = [s for s in run_analysis(conn, split_ms, cfg) if s.status.value in show]

counts = Counter(s.status.value for s in statuses)
cols = st.columns(4)
for col, key in zip(cols, ["new", "persistent", "fixed", "unconfirmed"], strict=True):
    col.metric(key.capitalize(), counts.get(key, 0))

st_folium(make_map(statuses, load_corridor(cfg)), width=None, height=650, returned_objects=[])
st.caption(
    "Fixed = not detected in newer imagery of the same spot (a candidate, not a confirmed repair). "
    "Unconfirmed = no imagery of that spot in the other period."
)
