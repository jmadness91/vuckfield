"""Align OpenStreetMap geometry to the LIDAR.

OSM outlines are traced from aerial imagery that is often offset by a few metres. The EA LIDAR is
surveyed (~0.5 m horizontal), so it is the reference: we find the single (dx, dy) shift that puts
the most OSM building footprint over raised ground (DSM - DTM), and apply it to all OSM geometry
so roads and buildings stay consistent with each other and with the terrain.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import shapely

from .osm import Way
from .terrain import Terrain

ROOF_MIN_HEIGHT_M = 2.0   # nDSM above this counts as "building here"
EDGE_INSET_M = 0.7        # ignore footprint edges where 1 m LIDAR pixels blend roof and ground
SAMPLE_STEP_M = 0.5
MAX_SHIFT_M = 4.0
MIN_IMPROVEMENT = 0.05    # apply a shift only if it raises coverage by 5 percentage points
PLATEAU_TOLERANCE = 0.005  # shifts within 0.5 points of the best count as equally good


@dataclass
class Alignment:
    dx: float
    dy: float
    coverage_before: float
    coverage_after: float
    applied: bool

    def as_dict(self) -> dict:
        return {"dx_east_m": self.dx, "dy_north_m": self.dy, "applied": self.applied,
                "roof_coverage_before": round(self.coverage_before, 3),
                "roof_coverage_after": round(self.coverage_after, 3)}


def footprint_samples(way: Way, inset: float = EDGE_INSET_M, step: float = SAMPLE_STEP_M) -> np.ndarray:
    """Grid points (BNG) inside a building footprint, inset from its edges. Empty if too small."""
    poly = way.polygon().buffer(-inset)
    if poly.is_empty:
        return np.empty((0, 2))
    minx, miny, maxx, maxy = poly.bounds
    xs, ys = np.meshgrid(np.arange(minx + step / 2, maxx, step), np.arange(miny + step / 2, maxy, step))
    xs, ys = xs.ravel(), ys.ravel()
    inside = shapely.contains_xy(poly, xs, ys)
    return np.column_stack([xs[inside], ys[inside]])


def _coverage(samples: list[np.ndarray], dtm: Terrain, dsm: Terrain, dx: float, dy: float) -> float:
    """Mean over buildings of the fraction of footprint samples over raised ground."""
    pts = np.vstack(samples)
    sizes = [len(s) for s in samples]
    raised = (dsm.sample(pts[:, 0] + dx, pts[:, 1] + dy) - dtm.sample(pts[:, 0] + dx, pts[:, 1] + dy)) > ROOF_MIN_HEIGHT_M
    per_building = np.add.reduceat(raised.astype(float), np.cumsum([0] + sizes[:-1])) / sizes
    return float(per_building.mean())


def estimate_offset(buildings: list[Way], dtm: Terrain, dsm: Terrain) -> Alignment:
    samples = [s for s in (footprint_samples(w) for w in buildings) if len(s) >= 3]
    if len(samples) < 10:
        return Alignment(0.0, 0.0, 0.0, 0.0, applied=False)
    before = _coverage(samples, dtm, dsm, 0.0, 0.0)

    def search(cx, cy, half, step):
        """Best shift on a grid. Inset footprints give a plateau of equally good shifts; take its
        centre rather than whichever edge the loop order happens to favour."""
        scores = [(_coverage(samples, dtm, dsm, dx, dy), dx, dy)
                  for dx in np.arange(cx - half, cx + half + 1e-9, step)
                  for dy in np.arange(cy - half, cy + half + 1e-9, step)]
        top = max(s for s, _, _ in scores)
        plateau = np.array([(dx, dy) for s, dx, dy in scores if s >= top - PLATEAU_TOLERANCE])
        return top, float(plateau[:, 0].mean()), float(plateau[:, 1].mean())

    _, cx, cy = search(0.0, 0.0, MAX_SHIFT_M, 0.5)
    _, dx, dy = search(cx, cy, 1.0, 0.125)
    dx, dy = round(float(dx), 3), round(float(dy), 3)
    score = _coverage(samples, dtm, dsm, dx, dy)  # report the shift actually applied
    applied = score - before >= MIN_IMPROVEMENT and max(abs(dx), abs(dy)) < MAX_SHIFT_M
    if not applied:
        return Alignment(0.0, 0.0, before, before, applied=False)
    return Alignment(dx, dy, before, score, applied=True)


def shift_ways(ways: list[Way], dx: float, dy: float) -> list[Way]:
    if dx == 0 and dy == 0:
        return ways
    return [Way(w.id, w.tags, [(x + dx, y + dy) for x, y in w.coords]) for w in ways]
