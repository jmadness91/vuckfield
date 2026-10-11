"""Building heights and roof shapes, fitted to the LIDAR, and the geometry that follows from them.

Every roof is described in the building's own frame: its minimum rotated rectangle, with `a` along
the long side and `b` across it (half-sizes hl >= hw). A roof shape is a set of planar regions in
that frame, each with a height function f in [0, 1] (0 at the eaves, 1 at the ridge):

    flat      one region, f = 0
    gabled    ridge along a: two halves, f = 1 - |b| / hw
    gabled_x  ridge across (along b): two halves, f = 1 - |a| / hl
    hipped    four regions split by the hip lines, f = (hw - |b|) / hw on the sides and
              (hl - |a|) / hw on the ends (equal pitch all round)

The footprint is cut by those regions, so every roof piece is planar and the walls under it
follow the roof line exactly: gable ends come out as walls rising to the ridge.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import shapely
import trimesh
from shapely.geometry import Polygon, box
from shapely.geometry.polygon import orient

from .align import footprint_samples
from .osm import Way
from .terrain import Terrain

SHAPES = ("flat", "gabled", "gabled_x", "hipped")
MIN_LIDAR_COVERAGE = 0.5   # fraction of footprint samples on raised ground to trust the LIDAR
ROOF_SAMPLE_MIN_M = 1.5    # samples lower than this above ground are not roof
MIN_PITCHED_RISE_M = 0.8   # less rise than this is a flat roof
PITCH_GAIN = 0.8           # a pitched model must cut the flat model's rms error by 20%
HIP_GAIN = 0.9             # hipped must beat gabled by 10% to be chosen (gabled is commoner here)
EAVE_RANGE_M = (2.0, 30.0)
RISE_RANGE_M = (0.0, 8.0)
DEFAULT_PITCH_DEG = 35.0
WALL_UV_M = 2.0            # metres of wall per texture repeat
ROOF_UV_M = 2.0
GRID_M = 1e-4

OSM_ROOF_SHAPES = {"flat": "flat", "gabled": "gabled", "hipped": "hipped", "pyramidal": "hipped",
                   "half-hipped": "hipped", "skillion": "gabled", "gambrel": "gabled", "mansard": "hipped"}
DEFAULT_EAVE_M = {"house": 5.2, "detached": 5.2, "semidetached_house": 5.2, "terrace": 5.2,
                  "residential": 5.2, "bungalow": 2.6, "apartments": 9.0, "garage": 2.4,
                  "garages": 2.4, "shed": 2.2, "roof": 2.6}
FLAT_BY_DEFAULT = {"garage", "garages", "shed", "commercial", "retail", "industrial", "warehouse", "roof"}
FALLBACK_EAVE_M = 5.0


@dataclass(frozen=True)
class Frame:
    cx: float
    cy: float
    ux: float  # unit vector along the long side
    uy: float
    hl: float  # half-length (along u)
    hw: float  # half-width (across)

    @classmethod
    def of(cls, poly: Polygon) -> "Frame":
        rect = np.asarray(poly.minimum_rotated_rectangle.exterior.coords)[:4]
        e1, e2 = rect[1] - rect[0], rect[2] - rect[1]
        long_, short = (e1, e2) if np.linalg.norm(e1) >= np.linalg.norm(e2) else (e2, e1)
        u = long_ / np.linalg.norm(long_)
        c = rect.mean(axis=0)
        return cls(float(c[0]), float(c[1]), float(u[0]), float(u[1]),
                   float(np.linalg.norm(long_) / 2), float(np.linalg.norm(short) / 2))

    def to_ab(self, x, y):
        dx, dy = np.asarray(x) - self.cx, np.asarray(y) - self.cy
        return dx * self.ux + dy * self.uy, -dx * self.uy + dy * self.ux

    def from_ab(self, a, b):
        a, b = np.asarray(a), np.asarray(b)
        return self.cx + a * self.ux - b * self.uy, self.cy + a * self.uy + b * self.ux


@dataclass(frozen=True)
class Roof:
    shape: str
    ground: float  # metres OD the eave/ridge heights are measured from
    eave: float    # metres above ground
    rise: float    # ridge minus eave, metres
    source: str    # "lidar" | "tags" | "default"

    @property
    def ridge(self) -> float:
        return self.eave + self.rise


def _f(shape: str, a, b, frame: Frame):
    """Height fraction over the whole rectangle (the max of the region planes, i.e. the roof)."""
    a, b = np.abs(a), np.abs(b)
    hl, hw = frame.hl, frame.hw
    if shape == "flat":
        return np.zeros_like(a)
    if shape == "gabled":
        return np.clip(1 - b / hw, 0, 1)
    if shape == "gabled_x":
        return np.clip(1 - a / hl, 0, 1)
    return np.clip(np.minimum(hw - b, hl - a) / hw, 0, 1)  # hipped


def _regions(shape: str, frame: Frame) -> list[Polygon]:
    """Planar roof regions in a/b frame coords, covering the rectangle with margin. Heights always
    come from the single continuous `_f`, so points shared by neighbouring pieces agree exactly."""
    hl, hw = frame.hl, frame.hw
    big = 2 * (hl + hw) + 10
    if shape == "flat":
        return [box(-big, -big, big, big)]
    if shape == "gabled":
        return [box(-big, 0, big, big), box(-big, -big, big, 0)]
    if shape == "gabled_x":
        return [box(0, -big, big, big), box(-big, -big, 0, big)]
    # hipped: hip lines leave the ridge ends (+-r, 0) at 45 degrees to the corners.
    # A square footprint has no ridge (r = 0): the sides become triangles, i.e. a pyramid.
    r, k = hl - hw, 1.5
    far = (r + k * hw, k * hw)
    ridge_n = [(r, 0), (-r, 0)] if r > GRID_M else [(0, 0)]
    ridge_s = [(-r, 0), (r, 0)] if r > GRID_M else [(0, 0)]
    return [
        Polygon([(-far[0], far[1]), (far[0], far[1]), *ridge_n]),
        Polygon([(-far[0], -far[1]), *ridge_s, (far[0], -far[1])]),
        Polygon([(far[0], far[1]), (far[0], -far[1]), (r, 0)]),
        Polygon([(-far[0], far[1]), (-r, 0), (-far[0], -far[1])]),
    ]


# --- fitting -----------------------------------------------------------------

def fit_roof(way: Way, dtm: Terrain, dsm: Terrain) -> Roof | None:
    """Least-squares eave/rise for each shape against LIDAR heights; None if the LIDAR doesn't
    show this building (e.g. built after the survey)."""
    pts = footprint_samples(way, inset=0.5)
    if len(pts) < 6:
        return None
    ground = dtm.sample(pts[:, 0], pts[:, 1])
    h = dsm.sample(pts[:, 0], pts[:, 1]) - ground
    roof = h > ROOF_SAMPLE_MIN_M
    if roof.mean() < MIN_LIDAR_COVERAGE:
        return None
    pts, h = pts[roof], h[roof]
    frame = Frame.of(way.polygon())
    a, b = frame.to_ab(pts[:, 0], pts[:, 1])

    fits = {}
    for shape in SHAPES:
        f = _f(shape, a, b, frame)
        if shape == "flat" or np.ptp(f) < 1e-6:
            eave, rise = float(h.mean()), 0.0
        else:
            A = np.column_stack([np.ones_like(f), f])
            (eave, rise), *_ = np.linalg.lstsq(A, h, rcond=None)
            if rise < 0:
                eave, rise = float(h.mean()), 0.0
        rms = float(np.sqrt(np.mean((eave + rise * f - h) ** 2)))
        fits[shape] = (rms, float(eave), float(rise))

    pitched = min(("gabled", "gabled_x"), key=lambda s: fits[s][0])
    if fits["hipped"][0] < HIP_GAIN * fits[pitched][0]:
        pitched = "hipped"
    rms, eave, rise = fits[pitched]
    if rise < MIN_PITCHED_RISE_M or rms > PITCH_GAIN * fits["flat"][0]:
        pitched, (rms, eave, rise) = "flat", fits["flat"]
    tag_shape = OSM_ROOF_SHAPES.get(way.tags.get("roof:shape", ""))
    if tag_shape and tag_shape != pitched:  # mapper knowledge beats the fit for shape
        pitched = tag_shape
        _, eave, rise = fits[tag_shape if tag_shape in fits else "gabled"]
    eave = float(np.clip(eave, *EAVE_RANGE_M))
    rise = float(np.clip(rise, *RISE_RANGE_M)) if pitched != "flat" else 0.0
    return Roof(pitched, float(np.median(ground)), eave, rise, "lidar")


def default_roof(way: Way, ground: float) -> Roof:
    t = way.tags
    kind = t.get("building", "")
    try:
        levels = int(float(t["building:levels"]))
        eave, source = levels * 2.7 + 0.3, "tags"
    except (KeyError, ValueError):
        eave, source = DEFAULT_EAVE_M.get(kind, FALLBACK_EAVE_M), "default"
    shape = OSM_ROOF_SHAPES.get(t.get("roof:shape", ""), "flat" if kind in FLAT_BY_DEFAULT else "gabled")
    hw = Frame.of(way.polygon()).hw
    rise = 0.0 if shape == "flat" else min(hw * math.tan(math.radians(DEFAULT_PITCH_DEG)), 5.0)
    try:
        total = float(t.get("height", t.get("building:height", "")).split()[0])
        if total > eave:
            rise = total - eave if shape != "flat" else 0.0
            eave = eave if shape != "flat" else total
            source = "tags"
    except (ValueError, IndexError):
        pass
    return Roof(shape, ground, eave, rise, source)


# --- geometry ----------------------------------------------------------------

@dataclass
class Part:
    """Raw geometry for one material: z-up local metres, with texture coordinates."""
    verts: np.ndarray
    faces: np.ndarray
    uv: np.ndarray

    @staticmethod
    def join(parts: list["Part"]) -> "Part":
        parts = [p for p in parts if len(p.faces)]
        if not parts:
            return Part(np.empty((0, 3)), np.empty((0, 3), int), np.empty((0, 2)))
        offsets = np.cumsum([0] + [len(p.verts) for p in parts[:-1]])
        return Part(np.vstack([p.verts for p in parts]),
                    np.vstack([p.faces + o for p, o in zip(parts, offsets)]),
                    np.vstack([p.uv for p in parts]))


def _polygons(geom) -> list[Polygon]:
    if geom.is_empty:
        return []
    if isinstance(geom, Polygon):
        return [geom] if geom.area > 1e-6 else []
    return [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon) and g.area > 1e-6]


def _triangulate(poly: Polygon) -> tuple[np.ndarray, np.ndarray]:
    v2, f = trimesh.creation.triangulate_polygon(poly, engine="earcut")
    return np.asarray(v2, dtype=np.float64), np.asarray(f, dtype=np.int64)


def building_parts(footprint: Polygon, roof: Roof, base: float, origin: tuple[float, float]) -> tuple[Part, Part]:
    """(walls incl. floor, roof) for a footprint in BNG metres. Output in local metres (minus origin)."""
    ox, oy = origin
    local = Polygon([(x - ox, y - oy) for x, y in footprint.exterior.coords],
                    [[(x - ox, y - oy) for x, y in r.coords] for r in footprint.interiors]).buffer(0)
    local = shapely.set_precision(local, GRID_M)
    frame = Frame.of(local)
    eave_z, rise = roof.ground + roof.eave, roof.rise
    boundary = local.boundary

    walls, roofs, floors = [], [], []
    for region_ab in _regions(roof.shape, frame):
        region = Polygon(np.column_stack(frame.from_ab(*np.asarray(region_ab.exterior.coords).T)))
        # Snap to a 0.1 mm grid: floating-point intersections otherwise leave sub-millimetre edges
        # that open cracks between roof pieces and walls. Snapping is global, so neighbours agree.
        for piece in _polygons(shapely.set_precision(local.intersection(region), GRID_M)):
            piece = orient(piece, 1.0)

            def z_of(x, y):
                a, b = frame.to_ab(x, y)
                return eave_z + rise * _f(roof.shape, a, b, frame)

            v2, f = _triangulate(piece)
            vz = z_of(v2[:, 0], v2[:, 1])
            v3 = np.column_stack([v2, vz])
            n = np.cross(v3[f[:, 1]] - v3[f[:, 0]], v3[f[:, 2]] - v3[f[:, 0]])
            if len(f) and n[:, 2].sum() < 0:
                f = f[:, ::-1]
            a, b = frame.to_ab(v2[:, 0], v2[:, 1])
            slope = math.sqrt(1 + (rise / max(frame.hw, 1e-6)) ** 2)  # stretch v along the slope
            roofs.append(Part(v3, f, np.column_stack([a / ROOF_UV_M, b * slope / ROOF_UV_M])))
            floors.append(Part(np.column_stack([v2, np.full(len(v2), base)]), f[:, ::-1] if len(f) else f,
                               np.column_stack([v2[:, 0], v2[:, 1]]) / WALL_UV_M))

            for ring in [piece.exterior, *piece.interiors]:
                pts = np.asarray(ring.coords)
                for p0, p1 in zip(pts[:-1], pts[1:]):
                    length = float(np.hypot(*(p1 - p0)))
                    if length < GRID_M or boundary.distance(shapely.Point((p0 + p1) / 2)) > 2 * GRID_M:
                        continue  # crease between roof pieces, not an outside wall
                    z0, z1 = float(z_of(*p0)), float(z_of(*p1))
                    v = np.array([[*p0, base], [*p1, base], [*p1, z1], [*p0, z0]])
                    uv = np.array([[0, 0], [length, 0], [length, z1 - base], [0, z0 - base]]) / WALL_UV_M
                    walls.append(Part(v, np.array([[0, 1, 2], [0, 2, 3]]), uv))
    return Part.join(walls + floors), Part.join(roofs)
