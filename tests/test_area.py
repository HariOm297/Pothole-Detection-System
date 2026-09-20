import json

from pothole.config import Area, load_area
from pothole.coverage import coverage_stats
from pothole.geo import offset_point

BASE_CFG = {"area": {"name": "t", "bbox": [29.34, 76.92, 29.44, 77.02], "tile_deg": 0.01}}


def test_bbox_area_contains_city_centre_not_karnal():
    area = load_area(BASE_CFG)
    assert area.contains(29.3909, 76.9635)  # Panipat centre
    assert not area.contains(29.6857, 76.9905)  # Karnal
    assert len(area.tiles()) == 100  # 10 x 10 tiles of 0.01 deg


def test_polygon_geojson_overrides_bbox(tmp_path):
    # small triangle in [lon, lat] order, as GeoJSON stores it
    gj = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": {},
        "geometry": {"type": "Polygon", "coordinates": [[
            [76.95, 29.38], [76.98, 29.38], [76.965, 29.41], [76.95, 29.38]]]},
    }]}
    f = tmp_path / "area.geojson"
    f.write_text(json.dumps(gj))
    cfg = {"area": {**BASE_CFG["area"], "polygon_geojson": str(f)}}
    area = load_area(cfg)
    assert area.contains(29.39, 76.965)
    assert not area.contains(29.35, 77.01)  # inside the bbox, outside the triangle
    assert len(area.tiles()) < 20


def test_multiple_polygons(tmp_path):
    def ring(lo, la):
        return [[lo, la], [lo + 0.01, la], [lo + 0.01, la + 0.01], [lo, la + 0.01], [lo, la]]

    gj = {"type": "MultiPolygon", "coordinates": [[ring(76.95, 29.38)], [ring(77.00, 29.42)]]}
    f = tmp_path / "m.geojson"
    f.write_text(json.dumps(gj))
    area = load_area({"area": {**BASE_CFG["area"], "polygon_geojson": str(f)}})
    assert area.contains(29.385, 76.955)
    assert area.contains(29.425, 77.005)
    assert not area.contains(29.40, 76.98)


def test_highway_extends_area_beyond_polygon(tmp_path):
    hw = {"type": "LineString", "coordinates": [[76.9635, 29.44], [76.97, 29.50]]}
    f = tmp_path / "hw.geojson"
    f.write_text(json.dumps(hw))
    cfg = {"area": {**BASE_CFG["area"], "highway_geojson": str(f), "highway_buffer_m": 100}}
    area = load_area(cfg)
    assert area.contains(29.47, 76.9668)  # on the highway, north of the bbox
    assert not area.contains(29.47, 76.99)  # 2 km off the highway
    assert len(area.tiles()) > 100


def test_coverage_stats_counts_cells():
    area = Area("sq", [[(29.40, 76.95), (29.40, 76.96), (29.41, 76.96), (29.41, 76.95)]])
    empty = coverage_stats([], area, cell_m=100)
    assert empty["cells_total"] > 50 and empty["cells_covered"] == 0

    line = [offset_point(29.4005, 76.9505, 90, d) for d in range(0, 900, 20)]  # one E-W lane
    stats = coverage_stats(line, area, cell_m=100)
    assert 5 <= stats["cells_covered"] <= 11
    assert 0 < stats["coverage_pct"] < 25

    outside = coverage_stats([(29.5, 77.0)], area, cell_m=100)
    assert outside["images_in_area"] == 0
