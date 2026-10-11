import numpy as np
import pytest
from shapely.geometry import LineString

from vuckfield import meshes
from vuckfield.osm import Way
from vuckfield.region import Region, lonlat_to_bng
from vuckfield.terrain import Terrain, _fill_gaps


def make_region(**kw):
    base = dict(id="t", name="t", min_e=0, min_n=0, max_e=100, max_n=100, origin_e=50, origin_n=50,
                mesh_spacing_m=10.0)
    base.update(kw)
    return Region(**base)


def flat(h=10.0):
    # 120x120 m at 1 m, top-left at (-10, 110)
    return Terrain(np.full((120, 120), h), west=-10, north=110, res=1.0)


def test_shipped_regions_are_valid():
    r = Region.load("nursery-lane")
    assert r.max_e - r.min_e == 400


def test_region_rejects_origin_outside_bbox():
    with pytest.raises(ValueError):
        make_region(origin_e=500).validate()


def test_nursery_lane_bng_is_in_uckfield():
    e, n = lonlat_to_bng(0.1005170, 50.9573983)
    assert 547_500 < e < 547_700 and 119_550 < n < 119_750


def test_terrain_bilinear_on_slope():
    cols = np.arange(4, dtype=float)
    t = Terrain(np.tile(cols, (4, 1)), west=0, north=4, res=1.0)
    # cell centres at x=0.5..3.5 carry 0..3, so x=2.0 is halfway between 1 and 2
    assert t.sample(2.0, 2.0) == pytest.approx(1.5)


def test_fill_gaps_removes_nans():
    a = np.array([[1.0, np.nan], [3.0, 5.0]])
    filled = _fill_gaps(a, np.isnan(a))
    assert not np.isnan(filled).any()
    assert filled[0, 1] == pytest.approx(3.0)


def test_axis_conversion_is_a_rotation_not_a_mirror():
    assert np.linalg.det(meshes.Z_UP_TO_Y_UP[:3, :3]) == pytest.approx(1.0)
    north = meshes.Z_UP_TO_Y_UP[:3, :3] @ [0, 1, 0]
    assert list(north) == [0, 0, -1]  # north is glTF -z


def _up_facing(mesh):
    # after conversion, glTF up is +y
    return (mesh.face_normals[:, 1] > 0.9).mean()


def test_terrain_faces_point_up():
    m = meshes.terrain_mesh(make_region(), flat())
    assert _up_facing(m) == 1.0
    assert m.vertices[:, 1].min() == pytest.approx(10.0)


def test_road_ribbon_faces_up_and_has_width():
    region = make_region()
    way = Way(1, {"highway": "residential"}, [(10, 50), (90, 50)])
    [m] = meshes.road_meshes([way], region, flat())
    assert _up_facing(m) == 1.0
    width = m.vertices[:, 2].max() - m.vertices[:, 2].min()
    assert width == pytest.approx(meshes.ROAD_WIDTH_M["residential"])
    assert m.vertices[:, 1].min() == pytest.approx(10.0 + meshes.LIFT_ROAD_M)


def test_roads_are_clipped_to_region():
    region = make_region()
    way = Way(1, {"highway": "service"}, [(-50, 50), (150, 50)])
    [m] = meshes.road_meshes([way], region, flat())
    assert m.vertices[:, 0].min() >= -50 - 2 and m.vertices[:, 0].max() <= 50 + 2


def test_unknown_highway_is_skipped():
    way = Way(1, {"highway": "proposed"}, [(10, 50), (90, 50)])
    assert meshes.road_meshes([way], make_region(), flat()) == []


@pytest.mark.parametrize("tags,expected", [
    ({"building": "yes", "height": "12 m"}, 12.0),
    ({"building": "yes", "building:levels": "3"}, 10.0),
    ({"building": "garage"}, 2.8),
    ({"building": "yes"}, meshes.FALLBACK_BUILDING_HEIGHT_M),
])
def test_building_height(tags, expected):
    assert meshes.building_height(Way(1, tags, [])) == expected


def test_building_is_watertight_and_reaches_height():
    square = [(40, 40), (50, 40), (50, 50), (40, 50), (40, 40)]
    [m] = meshes.building_meshes([Way(1, {"building": "house"}, square)], make_region(), flat())
    assert m.is_watertight
    assert m.vertices[:, 1].max() == pytest.approx(10.0 + 7.5)
    assert m.vertices[:, 1].min() == pytest.approx(10.0 - meshes.BUILDING_SINK_M)
