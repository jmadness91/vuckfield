import math
from pathlib import Path

import numpy as np
import pytest
import shapely
import trimesh
from shapely.geometry import Polygon

from vuckfield import roofs
from vuckfield.osm import Way
from vuckfield.terrain import Terrain

GROUND = 40.0


def house_way(x0=50, y0=50, w=10, d=7, wid=1, tags=None):
    return Way(wid, tags or {"building": "house"},
               [(x0, y0), (x0 + w, y0), (x0 + w, y0 + d), (x0, y0 + d), (x0, y0)])


def lidar_for(way, shape, eave, rise, res=0.25):
    """Synthetic DTM/DSM at 0.25 m with a roof of the given shape over the footprint."""
    n = int(120 / res)
    dtm = Terrain(np.full((n, n), GROUND), west=0, north=120, res=res)
    xs = np.arange(n) * res + res / 2
    X, Y = np.meshgrid(xs, 120 - xs)
    frame = roofs.Frame.of(way.polygon())
    a, b = frame.to_ab(X, Y)
    inside = shapely.contains_xy(way.polygon(), X, Y)
    h = GROUND + np.where(inside, eave + rise * roofs._f(shape, a, b, frame), 0.0)
    return dtm, Terrain(h, west=0, north=120, res=res)


@pytest.mark.parametrize("shape", ["flat", "gabled", "gabled_x", "hipped"])
def test_fit_recovers_shape_and_heights(shape):
    way = house_way()
    rise = 0.0 if shape == "flat" else 3.0
    dtm, dsm = lidar_for(way, shape, 5.0, rise)
    roof = roofs.fit_roof(way, dtm, dsm)
    assert roof.shape == shape
    assert roof.eave == pytest.approx(5.0, abs=0.3)
    assert roof.rise == pytest.approx(rise, abs=0.4)
    assert roof.ground == pytest.approx(GROUND)
    assert roof.source == "lidar"


def test_building_missing_from_lidar_is_not_fitted():
    way = house_way()
    dtm, _ = lidar_for(way, "flat", 5.0, 0.0)
    assert roofs.fit_roof(way, dtm, dtm) is None


def test_osm_roof_shape_tag_wins():
    way = house_way(tags={"building": "house", "roof:shape": "hipped"})
    dtm, dsm = lidar_for(way, "gabled", 5.0, 3.0)
    assert roofs.fit_roof(way, dtm, dsm).shape == "hipped"


def test_default_roof_uses_levels_and_pitch():
    r = roofs.default_roof(house_way(tags={"building": "house", "building:levels": "3"}), GROUND)
    assert r.shape == "gabled" and r.eave == pytest.approx(8.4) and r.source == "tags"
    assert r.rise == pytest.approx(3.5 * math.tan(math.radians(35)))
    assert roofs.default_roof(house_way(tags={"building": "garage"}), GROUND).shape == "flat"


FOOTPRINTS = {
    "rectangle": Polygon([(0, 0), (10, 0), (10, 7), (0, 7)]),
    "rotated": Polygon([(0, 0), (8, 6), (4, 11.2), (-4, 5.2)]),
    "l_shape": Polygon([(0, 0), (12, 0), (12, 5), (5, 5), (5, 10), (0, 10)]),
    "courtyard": Polygon([(0, 0), (20, 0), (20, 14), (0, 14)], [[(6, 4), (6, 10), (14, 10), (14, 4)]]),
    "square": Polygon([(0, 0), (8, 0), (8, 8), (0, 8)]),
}


def _mesh(part):
    m = trimesh.Trimesh(part.verts, part.faces, process=False)
    m.merge_vertices(digits_vertex=5)
    return m


@pytest.mark.parametrize("shape", ["flat", "gabled", "gabled_x", "hipped"])
@pytest.mark.parametrize("name", list(FOOTPRINTS))
def test_building_is_closed_outward_and_reaches_ridge(name, shape):
    fp = FOOTPRINTS[name]
    roof = roofs.Roof(shape, GROUND, 5.0, 0.0 if shape == "flat" else 3.0, "lidar")
    walls, top = roofs.building_parts(fp, roof, GROUND - 0.5, (0.0, 0.0))
    m = _mesh(roofs.Part.join([walls, top]))
    assert m.is_watertight, f"{name}/{shape} has holes"
    assert m.volume > 0, f"{name}/{shape} faces point inwards"
    # Footprint area x eave height is a lower bound; ridge is the top.
    assert m.volume >= fp.area * 5.4
    expected_top = GROUND + 5.0 + (0 if shape == "flat" else 3.0)
    assert m.vertices[:, 2].max() <= expected_top + 1e-6
    if name in ("rectangle", "square", "rotated"):
        assert m.vertices[:, 2].max() == pytest.approx(expected_top, abs=1e-6)
    # Roof faces point up; texture coordinates exist for every vertex.
    rm = trimesh.Trimesh(top.verts, top.faces, process=False)
    assert (rm.face_normals[:, 2] > 0).all()
    assert len(walls.uv) == len(walls.verts) and len(top.uv) == len(top.verts)


def test_gable_end_wall_rises_to_ridge():
    fp = FOOTPRINTS["rectangle"]
    walls, _ = roofs.building_parts(fp, roofs.Roof("gabled", 0.0, 5.0, 3.0, "lidar"), 0.0, (0.0, 0.0))
    # Gable ends are the short (7 m) walls at x = 0 and x = 10; their top reaches the 8 m ridge.
    end = walls.verts[np.isclose(walls.verts[:, 0], 0.0)]
    assert end[:, 2].max() == pytest.approx(8.0)


def _uv_jacobians(part):
    """Per triangle: 3D displacement per unit u and per unit v."""
    P, T, f = part.verts, part.uv, part.faces
    dp = np.stack([P[f[:, 1]] - P[f[:, 0]], P[f[:, 2]] - P[f[:, 0]]], axis=2)   # (n, 3, 2)
    dt = np.stack([T[f[:, 1]] - T[f[:, 0]], T[f[:, 2]] - T[f[:, 0]]], axis=2)   # (n, 2, 2)
    return dp @ np.linalg.inv(dt)                                                 # (n, 3, 2)


@pytest.mark.parametrize("shape", ["gabled", "gabled_x", "hipped"])
@pytest.mark.parametrize("name", ["rectangle", "rotated", "l_shape"])
def test_roof_texture_runs_level_at_true_scale(name, shape):
    # Reviewer finding: gabled_x and hip-end faces had tile courses running down the slope.
    _, top = roofs.building_parts(FOOTPRINTS[name], roofs.Roof(shape, 0.0, 5.0, 3.0, "lidar"), 0.0, (0, 0))
    J = _uv_jacobians(top)
    du, dv = J[:, :, 0], J[:, :, 1]
    # 0.1% tolerance: the 0.1 mm snapping grid makes pieces planar only to ~1e-4.
    assert np.allclose(np.linalg.norm(du, axis=1), 1.0, atol=1e-3)  # 1 uv unit = 1 m along the eave
    assert np.allclose(np.linalg.norm(dv, axis=1), 1.0, atol=1e-3)  # ... and 1 m up the slope
    assert np.allclose(du[:, 2], 0.0, atol=1e-3)                     # courses are level
    assert (dv[:, 2] > 0).all()                                      # v increases uphill


def test_low_height_tag_is_respected():
    # Reviewer finding: height=4 on a house used to keep the 5.2 m default eave.
    r = roofs.default_roof(house_way(tags={"building": "house", "height": "4"}), GROUND)
    assert r.ridge == pytest.approx(4.0) and r.eave < 4.0


def test_pitched_roof_survives_offset_footprint_and_noise():
    # Reviewer finding: edge blur + misalignment made every model fit badly, so flat won.
    true = house_way(x0=50.8, y0=49.4)                   # where the LIDAR sees the house
    osm_way = house_way(x0=50.0, y0=50.0)                # OSM outline 1 m off
    dtm, dsm = lidar_for(true, "gabled", 5.0, 3.0)
    rng = np.random.default_rng(3)
    dsm.h += rng.normal(0, 0.3, dsm.h.shape)             # LIDAR noise
    roof = roofs.fit_roof(osm_way, dtm, dsm)
    assert roof.shape == "gabled"
    assert roof.eave == pytest.approx(5.0, abs=0.6) and roof.rise == pytest.approx(3.0, abs=0.8)


REGION_CACHE = Path(__file__).resolve().parents[2] / "data" / "cache" / "nursery-lane"


@pytest.mark.skipif(not (REGION_CACHE / "dsm_lz_1m.tif").exists(), reason="needs cached region 1 LIDAR")
def test_region_1_has_no_flat_houses_with_sloped_lidar():
    # Regression on real data for the reviewer's H1: houses with >2 m of roof height spread were flat.
    from vuckfield import align, osm, sources
    from vuckfield.region import Region
    region = Region.load("nursery-lane")
    dtm = Terrain.from_geotiff(sources.fetch_dtm(region))
    dsm = Terrain.from_geotiff(sources.fetch_dsm(region))
    ways = osm.read_ways(sources.fetch_osm(region))
    a = align.estimate_offset(osm.buildings(ways, region), dtm, dsm)
    flat_houses = [w.id for w in osm.buildings(align.shift_ways(ways, a.dx, a.dy), region)
                   if roofs._is_house(w) and (r := roofs.fit_roof(w, dtm, dsm)) and r.shape == "flat"
                   and _spread(w, dtm, dsm) > roofs.HOUSE_SPREAD_M]
    assert flat_houses == []


def _spread(way, dtm, dsm):
    from vuckfield.align import footprint_samples
    dx, dy = roofs._local_offset(way, dtm, dsm)  # measure where the fit samples
    p = footprint_samples(way, inset=1.0)
    h = dsm.sample(p[:, 0] + dx, p[:, 1] + dy) - dtm.sample(p[:, 0] + dx, p[:, 1] + dy)
    h = h[h > roofs.ROOF_SAMPLE_MIN_M]
    return np.percentile(h, 95) - np.percentile(h, 5) if len(h) >= 6 else 0.0
