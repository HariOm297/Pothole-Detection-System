from pothole.compare import (
    Detection,
    Status,
    cluster_detections,
    compare_periods,
)
from pothole.geo import offset_point

P = (29.50, 76.97)


def near(dist_m, bearing=0.0):
    return offset_point(*P, bearing, dist_m)


def det(pt, conf=0.6):
    return Detection(pt[0], pt[1], conf)


def test_cluster_merges_nearby_frames():
    dets = [det(P, 0.9), det(near(3), 0.5), det(near(5, 90), 0.4), det(near(200), 0.7)]
    clusters = cluster_detections(dets, radius_m=8)
    assert len(clusters) == 2
    big = max(clusters, key=lambda c: c.hits)
    assert big.hits == 3
    assert big.conf == 0.9  # seeded by highest confidence


def test_cluster_min_hits_filters_singletons():
    dets = [det(P), det(near(2)), det(near(500))]
    assert len(cluster_detections(dets, radius_m=8, min_hits=2)) == 1


def test_cluster_empty():
    assert cluster_detections([]) == []


def _pair(pt):
    return [det(pt), det(offset_point(*pt, 0, 2))]


def test_persistent_new_fixed():
    old_pothole = P
    new_pothole = near(300)
    fixed_pothole = near(600)

    baseline = _pair(old_pothole) + _pair(fixed_pothole)
    current = _pair(old_pothole) + _pair(new_pothole)
    # imagery existed in both periods along the whole stretch
    cov = [near(d) for d in range(0, 700, 10)]

    res = compare_periods(baseline, current, cov, cov, min_hits=2)
    by_status = {}
    for r in res:
        by_status.setdefault(r.status, []).append(r)
    assert len(by_status[Status.PERSISTENT]) == 1
    assert len(by_status[Status.NEW]) == 1
    assert len(by_status[Status.FIXED]) == 1
    assert Status.UNCONFIRMED not in by_status


def test_no_baseline_coverage_means_unconfirmed_not_new():
    current = _pair(near(300))
    baseline_cov = [near(d) for d in range(0, 100, 10)]  # nothing near 300 m
    current_cov = [near(d) for d in range(0, 700, 10)]
    res = compare_periods([], current, baseline_cov, current_cov)
    assert [r.status for r in res] == [Status.UNCONFIRMED]


def test_no_current_coverage_means_unconfirmed_not_fixed():
    baseline = _pair(near(300))
    baseline_cov = [near(d) for d in range(0, 700, 10)]
    current_cov = [near(d) for d in range(0, 100, 10)]
    res = compare_periods(baseline, [], baseline_cov, current_cov)
    assert [r.status for r in res] == [Status.UNCONFIRMED]


def test_single_detection_ignored_with_min_hits_2():
    cov = [near(d) for d in range(0, 100, 10)]
    res = compare_periods([], [det(P)], cov, cov, min_hits=2)
    assert res == []
