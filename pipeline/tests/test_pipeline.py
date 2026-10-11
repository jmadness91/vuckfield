import numpy as np
import pytest
from shapely.geometry import LineString

from vuckfield import meshes
from vuckfield.osm import Way
from vuckfield.region import REGIONS_DIR, Region, lonlat_to_bng
from vuckfield.terrain import Terrain, _fill_gaps


def make_region(**kw):
    base = dict(id="t", name="t", min_e=0, min_n=0, max_e=100, max_n=100, origin_e=50, origin_n=50,
                mesh_spacing_m=10.0)
    base.update(kw)
    return Region(**base)


def flat(h=10.0):
    # 120x120 m at 1 m, top-left at (-10, 110)
    return Terrain(np.full((120, 120), h), west=-10, north=110, res=1.0)


@pytest.mark.parametrize("region_id", sorted(p.stem for p in REGIONS_DIR.glob("*.json")))
def test_shipped_regions_are_valid(region_id):
    Region.load(region_id)  # validate() raises on bad bbox/origin/landmarks


def test_region_rejects_landmark_outside_bbox():
    r = make_region(landmarks=[{"id": "x", "name": "x", "osm": "a=b", "lat": 51.5, "lon": -0.1}])
    with pytest.raises(ValueError, match="landmark"):
        r.validate()


def test_framework_check_passes():
    import subprocess, sys
    root = REGIONS_DIR.parent
    out = subprocess.run([sys.executable, str(root / "world-builder" / "check.py")], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout


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
    m = meshes.terrain_mesh(make_region(), meshes.TerrainSurface(make_region(), flat()))
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


def test_buildings_export_walls_and_roofs_on_terrain():
    region = make_region()
    surface = meshes.TerrainSurface(region, flat())
    square = [(40, 40), (50, 40), (50, 48), (40, 48), (40, 40)]
    way = Way(1, {"building": "house", "building:material": "brick", "roof:material": "slate"}, square)
    walls, roof = meshes.building_meshes([way], region, surface)  # sorted by material name
    assert walls.visual.material.name == "M_brick_red" and roof.visual.material.name == "M_roof_slate"
    assert walls.visual.material.baseColorTexture is not None and walls.visual.uv is not None
    # glTF y-up: walls start below ground (sunk), roof ridge above the default eave.
    assert walls.vertices[:, 1].min() == pytest.approx(10.0 - meshes.BUILDING_SINK_M)
    assert roof.vertices[:, 1].max() > 10.0 + 5.2


def _height_on_triangles(mesh, east, north):
    """Height of a y-up mesh at (east, north) by brute-force barycentric lookup (small meshes only)."""
    tri = mesh.vertices[mesh.faces]  # glTF: x east, y up, z south
    ax, an = tri[:, 0, 0], -tri[:, 0, 2]
    bx, bn = tri[:, 1, 0], -tri[:, 1, 2]
    cx, cn = tri[:, 2, 0], -tri[:, 2, 2]
    den = (bn - cn) * (ax - cx) + (cx - bx) * (an - cn)
    w1 = ((bn - cn) * (east - cx) + (cx - bx) * (north - cn)) / den
    w2 = ((cn - an) * (east - cx) + (ax - cx) * (north - cn)) / den
    w3 = 1 - w1 - w2
    k = np.flatnonzero((w1 >= -1e-9) & (w2 >= -1e-9) & (w3 >= -1e-9))[0]
    return w1[k] * tri[k, 0, 1] + w2[k] * tri[k, 1, 1] + w3[k] * tri[k, 2, 1]


def test_surface_matches_terrain_mesh_triangles():
    # Roads/buildings are draped on TerrainSurface; it must agree with the drawn triangles exactly.
    rng = np.random.default_rng(1)
    region = make_region()
    t = Terrain(rng.uniform(0, 20, (120, 120)), west=-10, north=110, res=1.0)
    surface = meshes.TerrainSurface(region, t)
    mesh = meshes.terrain_mesh(region, surface)
    for e, n in rng.uniform(1, 99, (200, 2)):
        expected = _height_on_triangles(mesh, e - region.origin_e, n - region.origin_n)
        assert surface.sample(e, n) == pytest.approx(expected, abs=1e-9)


def test_region_1_roads_never_below_terrain():
    # Reviewer finding: 43 road vertices were below the 2 m terrain mesh (draped on the 1 m DTM).
    import trimesh
    region = Region.load("nursery-lane")
    d = REGIONS_DIR.parent / "build" / "regions" / "nursery-lane"
    tv = trimesh.load(d / "terrain.glb", force="mesh").vertices
    # Rebuild the drawn surface from the committed terrain.glb itself (grid order is row-major S->N).
    surface = meshes.TerrainSurface.__new__(meshes.TerrainSurface)
    surface.spacing = region.mesh_spacing_m
    surface.es = np.unique(np.round(tv[:, 0], 6)) + region.origin_e
    surface.ns = np.unique(np.round(-tv[:, 2], 6)) + region.origin_n
    surface.Z = tv[:, 1].reshape(len(surface.ns), len(surface.es))
    for f in ["roads.glb", "landmark_nursery-lane.glb"]:
        v = trimesh.load(d / f, force="mesh").vertices
        e, n = v[:, 0] + region.origin_e, -v[:, 2] + region.origin_n
        inside = (e > region.min_e) & (e < region.max_e) & (n > region.min_n) & (n < region.max_n)
        gap = v[inside, 1] - surface.sample(e[inside], n[inside])
        assert gap.min() > 0.05, f"{f}: road vertex {gap.min():.3f} m relative to terrain"


def test_textures_and_uv_scale_survive_glb_round_trip(tmp_path):
    import trimesh

    from vuckfield import textures
    region = make_region()
    surface = meshes.TerrainSurface(region, flat())
    square = [(40, 40), (50, 40), (50, 48), (40, 48), (40, 40)]
    way = Way(1, {"building": "house", "building:material": "brick", "roof:material": "slate"}, square)
    walls, _ = meshes.building_meshes([way], region, surface)
    path = tmp_path / "b.glb"
    path.write_bytes(trimesh.Scene([walls]).export(file_type="glb"))
    [m] = trimesh.load(path, force="scene").geometry.values()
    assert m.visual.material.baseColorTexture.size == (textures.SIZE, textures.SIZE)
    # Wall UVs start at 0 along each wall: a 10 m wall spans 10 / 2 m-per-tile = 5 texture repeats.
    assert m.visual.uv[:, 0].max() == pytest.approx(10 / textures.SPECS["brick_red"].tile_m, abs=1e-3)


def test_textures_tile_seamlessly():
    from vuckfield import textures
    for name in textures.SPECS:
        a = np.asarray(textures.image(name), dtype=float)
        for img in (a, a.transpose(1, 0, 2)):  # rows, then columns
            # The wrap-around seam must look like an ordinary boundary inside the texture (e.g. a
            # mortar line), never stronger than the strongest one already there.
            seam = np.abs(img[0] - img[-1]).mean()
            interior = np.abs(np.diff(img, axis=0)).mean(axis=(1, 2)).max()
            assert seam <= 1.05 * interior + 1, name
