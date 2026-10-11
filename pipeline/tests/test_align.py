import numpy as np
import pytest

from vuckfield import align
from vuckfield.osm import Way
from vuckfield.terrain import Terrain


def scene(true_dx, true_dy, n=12):
    """Flat ground at 10 m with n 8x6 m houses (7 m tall) in the DSM; OSM footprints drawn
    offset by (-true_dx, -true_dy), i.e. OSM needs shifting by (true_dx, true_dy)."""
    dtm = Terrain(np.full((200, 200), 10.0), west=0, north=200, res=1.0)
    h = np.full((200, 200), 10.0)
    ways = []
    for i in range(n):
        x0, y0 = 20 + (i % 4) * 40, 30 + (i // 4) * 50
        # DSM raster rows run north -> south
        h[200 - (y0 + 6):200 - y0, x0:x0 + 8] = 17.0
        fx, fy = x0 - true_dx, y0 - true_dy
        ways.append(Way(i, {"building": "house"},
                        [(fx, fy), (fx + 8, fy), (fx + 8, fy + 6), (fx, fy + 6), (fx, fy)]))
    return ways, dtm, Terrain(h, west=0, north=200, res=1.0)


def test_recovers_known_offset():
    ways, dtm, dsm = scene(2.0, -1.5)
    a = align.estimate_offset(ways, dtm, dsm)
    assert a.applied
    assert a.dx == pytest.approx(2.0, abs=0.26) and a.dy == pytest.approx(-1.5, abs=0.26)
    assert a.coverage_after > 0.95 > a.coverage_before


def test_aligned_data_is_left_alone():
    ways, dtm, dsm = scene(0.0, 0.0)
    a = align.estimate_offset(ways, dtm, dsm)
    assert not a.applied and (a.dx, a.dy) == (0.0, 0.0)


def test_too_few_buildings_is_not_guessed():
    ways, dtm, dsm = scene(2.0, 0.0, n=3)
    assert not align.estimate_offset(ways, dtm, dsm).applied


def test_shift_moves_every_coordinate():
    w = Way(1, {}, [(0.0, 0.0), (1.0, 1.0)])
    [s] = align.shift_ways([w], 2.0, -1.0)
    assert s.coords == [(2.0, -1.0), (3.0, 0.0)]
