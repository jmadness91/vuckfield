"""Geometry generation. Everything is built z-up in local metres
(x east, y north, z = height above Ordnance Datum) and converted to glTF's
y-up convention only at export time.
"""
from __future__ import annotations

import re

import numpy as np
import trimesh
from shapely.geometry import LineString, MultiLineString, Polygon, box

from . import roofs
from .osm import Way
from .region import Region
from .terrain import Terrain

# Road half-widths in metres by OSM highway class. Unknown classes are skipped.
ROAD_WIDTH_M = {
    "trunk": 8.0, "primary": 7.5, "secondary": 7.0, "tertiary": 6.5,
    "unclassified": 5.5, "residential": 5.5, "living_street": 5.0,
    "service": 3.5, "track": 3.0,
    "footway": 1.8, "path": 1.5, "cycleway": 2.0, "pedestrian": 3.0,
    "bridleway": 1.8, "steps": 1.5,
}
FOOTWAY_CLASSES = {"footway", "path", "cycleway", "pedestrian", "bridleway", "steps"}
# Small lifts above terrain; distinct per layer to avoid z-fighting where they overlap.
LIFT_ROAD_M = 0.15
LIFT_FOOTWAY_M = 0.10
RIBBON_STEP_M = 2.0
BUILDING_SINK_M = 0.5


COLOURS = {
    "terrain": (0.36, 0.45, 0.28, 1.0),
    "road": (0.22, 0.22, 0.24, 1.0),
    "footway": (0.55, 0.53, 0.50, 1.0),
    "building": (0.80, 0.76, 0.70, 1.0),
    "roof": (0.45, 0.25, 0.20, 1.0),
    "landmark": (0.75, 0.18, 0.12, 1.0),
}

# z-up local -> glTF y-up. A proper rotation (det +1), so winding is preserved
# and the map is not mirrored: glTF x = east, y = up, z = south.
Z_UP_TO_Y_UP = np.array([
    [1, 0, 0, 0],
    [0, 0, 1, 0],
    [0, -1, 0, 0],
    [0, 0, 0, 1],
], dtype=np.float64)


def _material(name: str) -> trimesh.visual.material.PBRMaterial:
    return trimesh.visual.material.PBRMaterial(
        name=f"M_{name}", baseColorFactor=COLOURS[name], metallicFactor=0.0, roughnessFactor=0.9,
    )


def _finish(mesh: trimesh.Trimesh, material: str) -> trimesh.Trimesh:
    mesh.visual = trimesh.visual.TextureVisuals(material=_material(material))
    mesh.apply_transform(Z_UP_TO_Y_UP)
    return mesh


# --- terrain -----------------------------------------------------------------

class TerrainSurface:
    """The terrain mesh's exact surface: heights on the region grid, interpolated on the same two
    triangles per cell that the mesh uses. Roads and buildings sample this, not the raw 1 m DTM,
    so nothing dips below the triangles that are actually drawn."""

    def __init__(self, region: Region, terrain: Terrain):
        s = region.mesh_spacing_m
        self.es = np.arange(region.min_e, region.max_e + s / 2, s)
        self.ns = np.arange(region.min_n, region.max_n + s / 2, s)
        self.E, self.N = np.meshgrid(self.es, self.ns)  # rows run south -> north
        self.Z = terrain.sample(self.E, self.N)
        self.spacing = s

    def sample(self, e, n):
        e = np.asarray(e, dtype=np.float64)
        n = np.asarray(n, dtype=np.float64)
        rows, cols = self.Z.shape
        fx = np.clip((e - self.es[0]) / self.spacing, 0, cols - 1.000001)
        fy = np.clip((n - self.ns[0]) / self.spacing, 0, rows - 1.000001)
        j, i = np.floor(fx).astype(int), np.floor(fy).astype(int)
        fx, fy = fx - j, fy - i
        za, zb = self.Z[i, j], self.Z[i, j + 1]          # south-west, south-east
        zc, zd = self.Z[i + 1, j], self.Z[i + 1, j + 1]  # north-west, north-east
        # Cells are split on the SW-NE diagonal: triangle (a, b, d) where fx >= fy, else (a, d, c).
        lower = za + fx * (zb - za) + fy * (zd - zb)
        upper = za + fy * (zc - za) + fx * (zd - zc)
        return np.where(fx >= fy, lower, upper)


def terrain_mesh(region: Region, surface: TerrainSurface) -> trimesh.Trimesh:
    x, y = region.to_local(surface.E, surface.N)
    verts = np.column_stack([x.ravel(), y.ravel(), surface.Z.ravel()])
    rows, cols = surface.E.shape
    idx = np.arange(rows * cols).reshape(rows, cols)
    a, b = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel()
    c, d = idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    # Counter-clockwise seen from above (+z) so normals face up. Must match TerrainSurface.sample.
    faces = np.concatenate([np.column_stack([a, b, d]), np.column_stack([a, d, c])])
    return _finish(trimesh.Trimesh(verts, faces, process=False), "terrain")


# --- roads -------------------------------------------------------------------

def road_width(way: Way) -> float | None:
    w = way.tags.get("width")
    if w:
        m = re.match(r"^\s*([\d.]+)", w)
        if m:
            return float(m.group(1))
    return ROAD_WIDTH_M.get(way.tags.get("highway", ""))


def _ribbon(line: LineString, width: float, lift: float, region: Region, terrain: Terrain | TerrainSurface) -> trimesh.Trimesh | None:
    line = line.segmentize(RIBBON_STEP_M)
    pts = np.asarray(line.coords)[:, :2]
    # Drop consecutive duplicates, which would give zero-length tangents.
    keep = np.r_[True, np.linalg.norm(np.diff(pts, axis=0), axis=1) > 1e-6]
    pts = pts[keep]
    if len(pts) < 2:
        return None
    seg = np.diff(pts, axis=0)
    seg /= np.linalg.norm(seg, axis=1)[:, None]
    tangent = np.vstack([seg[:1], seg[:-1] + seg[1:], seg[-1:]])
    norms = np.linalg.norm(tangent, axis=1)
    tangent[norms < 1e-9] = np.vstack([seg[:1], seg])[norms < 1e-9]  # hairpin fallback
    tangent /= np.linalg.norm(tangent, axis=1)[:, None]
    left = np.column_stack([-tangent[:, 1], tangent[:, 0]])
    half = width / 2.0
    edges = [pts + left * half, pts - left * half]
    verts = []
    for edge in edges:
        z = terrain.sample(edge[:, 0], edge[:, 1]) + lift
        lx, ly = region.to_local(edge[:, 0], edge[:, 1])
        verts.append(np.column_stack([lx, ly, z]))
    L, R = verts
    k = len(pts)
    v = np.vstack([L, R])
    i = np.arange(k - 1)
    # L[i], R[i], R[i+1] / L[i], R[i+1], L[i+1]: CCW from above for a left-pointing L edge.
    faces = np.vstack([
        np.column_stack([i, k + i, k + i + 1]),
        np.column_stack([i, k + i + 1, i + 1]),
    ])
    return trimesh.Trimesh(v, faces, process=False)


def _clip_lines(way: Way, region: Region) -> list[LineString]:
    clipped = way.line().intersection(box(region.min_e, region.min_n, region.max_e, region.max_n))
    if isinstance(clipped, LineString):
        return [] if clipped.is_empty else [clipped]
    if isinstance(clipped, MultiLineString):
        return list(clipped.geoms)
    return [g for g in getattr(clipped, "geoms", []) if isinstance(g, LineString)]


def road_meshes(ways: list[Way], region: Region, terrain: Terrain | TerrainSurface, material: str | None = None) -> list[trimesh.Trimesh]:
    parts: dict[str, list[trimesh.Trimesh]] = {"road": [], "footway": []}
    for way in ways:
        width = road_width(way)
        if width is None:
            continue
        kind = "footway" if way.tags.get("highway") in FOOTWAY_CLASSES else "road"
        lift = LIFT_FOOTWAY_M if kind == "footway" else LIFT_ROAD_M
        for line in _clip_lines(way, region):
            m = _ribbon(line, width, lift, region, terrain)
            if m is not None:
                parts[kind].append(m)
    meshes = []
    for kind, ms in parts.items():
        if ms:
            meshes.append(_finish(trimesh.util.concatenate(ms), material or kind))
    return meshes


# --- buildings ---------------------------------------------------------------

def _from_part(part: roofs.Part, material: str) -> trimesh.Trimesh:
    mesh = trimesh.Trimesh(part.verts, part.faces, process=False)
    mesh.visual = trimesh.visual.TextureVisuals(uv=part.uv, material=_material(material))
    mesh.apply_transform(Z_UP_TO_Y_UP)
    return mesh


def building_roof(way: Way, surface: TerrainSurface, fitted: dict[int, roofs.Roof]) -> roofs.Roof:
    if way.id in fitted:
        return fitted[way.id]
    ring = np.asarray(way.polygon().exterior.coords)
    return roofs.default_roof(way, float(np.median(surface.sample(ring[:, 0], ring[:, 1]))))


def building_meshes(ways: list[Way], region: Region, surface: TerrainSurface,
                    fitted: dict[int, roofs.Roof] | None = None,
                    wall_material: str = "building", roof_material: str = "roof") -> list[trimesh.Trimesh]:
    """Walls (with floors) and roofs as two meshes. `fitted` holds LIDAR roofs by way id;
    buildings without one get tag/default heights."""
    fitted = fitted or {}
    walls, tops = [], []
    for way in ways:
        ring = np.asarray(way.polygon().exterior.coords)
        base = float(surface.sample(ring[:, 0], ring[:, 1]).min()) - BUILDING_SINK_M
        w, r = roofs.building_parts(way.polygon(), building_roof(way, surface, fitted), base,
                                    (region.origin_e, region.origin_n))
        walls.append(w)
        tops.append(r)
    out = []
    for parts, material in ((walls, wall_material), (tops, roof_material)):
        joined = roofs.Part.join(parts)
        if len(joined.faces):
            out.append(_from_part(joined, material))
    return out
