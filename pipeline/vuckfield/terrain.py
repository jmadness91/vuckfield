"""Height sampling over the LIDAR DTM."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio


class Terrain:
    """Bilinear height lookup in BNG metres, with gaps filled."""

    def __init__(self, heights: np.ndarray, west: float, north: float, res: float):
        self.h = heights
        self.west = west
        self.north = north
        self.res = res

    @classmethod
    def from_geotiff(cls, path: Path) -> "Terrain":
        with rasterio.open(path) as ds:
            if ds.crs.to_epsg() != 27700:
                raise ValueError(f"{path}: expected EPSG:27700, got {ds.crs}")
            a = ds.read(1).astype(np.float64)
            nodata = ds.nodata
            west, north, res = ds.bounds.left, ds.bounds.top, ds.res[0]
        bad = ~np.isfinite(a) | (a < -1000)
        if nodata is not None:
            bad |= a == nodata
        if bad.all():
            raise ValueError(f"{path}: DTM has no valid cells")
        if bad.any():
            a = _fill_gaps(a, bad)
        return cls(a, west, north, res)

    def sample(self, e, n):
        """Height at BNG points (scalars or arrays). Samples are cell centres."""
        e = np.asarray(e, dtype=np.float64)
        n = np.asarray(n, dtype=np.float64)
        col = (e - self.west) / self.res - 0.5
        row = (self.north - n) / self.res - 0.5
        rows, cols = self.h.shape
        col = np.clip(col, 0, cols - 1.000001)
        row = np.clip(row, 0, rows - 1.000001)
        c0 = np.floor(col).astype(int)
        r0 = np.floor(row).astype(int)
        fc = col - c0
        fr = row - r0
        h = self.h
        top = h[r0, c0] * (1 - fc) + h[r0, c0 + 1] * fc
        bot = h[r0 + 1, c0] * (1 - fc) + h[r0 + 1, c0 + 1] * fc
        return top * (1 - fr) + bot * fr


def _fill_gaps(a: np.ndarray, bad: np.ndarray) -> np.ndarray:
    """Iteratively fill missing cells with the mean of valid 4-neighbours."""
    a = a.copy()
    a[bad] = np.nan
    while np.isnan(a).any():
        p = np.pad(a, 1, mode="edge")
        neigh = np.stack([p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
        with np.errstate(invalid="ignore"):
            fill = np.nanmean(neigh, axis=0)
        holes = np.isnan(a) & ~np.isnan(fill)
        if not holes.any():
            a[np.isnan(a)] = np.nanmean(a)
            break
        a[holes] = fill[holes]
    return a
