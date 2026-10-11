import math

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
