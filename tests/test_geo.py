from pothole.geo import (
    area_tiles,
    corridor_tiles,
    distance_to_polyline_m,
    haversine_m,
    interpolate_polyline,
    offset_point,
    point_in_polygon,
    split_bbox,
)

PANIPAT = (29.3909, 76.9635)
KARNAL = (29.6857, 76.9905)


def test_haversine_panipat_karnal():
    d = haversine_m(*PANIPAT, *KARNAL)
    assert 32_000 < d < 34_500


def test_haversine_zero():
    assert haversine_m(*PANIPAT, *PANIPAT) == 0


def test_offset_north_100m():
    lat, lon = offset_point(*PANIPAT, bearing_deg=0, dist_m=100)
    assert abs(haversine_m(*PANIPAT, lat, lon) - 100) < 0.5
    assert lat > PANIPAT[0]
    assert abs(lon - PANIPAT[1]) < 1e-6


def test_offset_east():
    lat, lon = offset_point(*PANIPAT, bearing_deg=90, dist_m=50)
    assert lon > PANIPAT[1]
    assert abs(haversine_m(*PANIPAT, lat, lon) - 50) < 0.5


def test_distance_to_polyline():
    line = [PANIPAT, KARNAL]
    assert distance_to_polyline_m(*PANIPAT, line) < 1
    # ~100 m east of a point on the line
    mid = (29.54, 76.9770)
    east = offset_point(*mid, 90, 100)
    d = distance_to_polyline_m(*east, line)
    assert 80 < d < 120


def test_interpolate_step():
    pts = interpolate_polyline([PANIPAT, KARNAL], 500)
    gaps = [haversine_m(*a, *b) for a, b in zip(pts, pts[1:], strict=False)]
    assert max(gaps) <= 501
    assert pts[0] == PANIPAT
    assert pts[-1] == KARNAL


def test_corridor_tiles_cover_endpoints():
    tiles = corridor_tiles([PANIPAT, KARNAL], tile_deg=0.01)
    assert len(tiles) == len(set(tiles))

    def covered(lat, lon):
        return any(t[0] <= lon <= t[2] and t[1] <= lat <= t[3] for t in tiles)

    assert covered(*PANIPAT)
    assert covered(*KARNAL)
    assert covered(29.54, 76.9770)


def test_split_bbox_quadrants():
    parts = split_bbox((0.0, 0.0, 2.0, 2.0))
    assert len(parts) == 4
    assert (1.0, 1.0, 2.0, 2.0) in parts


SQUARE = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]
# L-shape: the top-right quadrant is missing
L_SHAPE = [(0.0, 0.0), (0.0, 2.0), (1.0, 2.0), (1.0, 1.0), (2.0, 1.0), (2.0, 0.0)]


def test_point_in_polygon_square():
    assert point_in_polygon(0.5, 0.5, SQUARE)
    assert not point_in_polygon(1.5, 0.5, SQUARE)
    assert not point_in_polygon(0.5, -0.1, SQUARE)


def test_point_in_polygon_concave():
    assert point_in_polygon(0.5, 1.5, L_SHAPE)
    assert point_in_polygon(1.5, 0.5, L_SHAPE)
    assert not point_in_polygon(1.5, 1.5, L_SHAPE)


def test_area_tiles_rectangle_full_grid():
    tiles = area_tiles(SQUARE, tile_deg=0.25)
    assert len(tiles) == 16
    assert len(set(tiles)) == 16


def test_area_tiles_skip_empty_corner_of_concave_polygon():
    tiles = area_tiles(L_SHAPE, tile_deg=0.5)
    centres = {((t[0] + t[2]) / 2, (t[1] + t[3]) / 2) for t in tiles}
    assert (1.75, 1.75) not in centres  # inside the missing quadrant
    assert (0.25, 0.25) in centres
