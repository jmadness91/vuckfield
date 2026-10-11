"""Procedural, seamlessly tiling textures. Deterministic (fixed seeds), so rebuilds are byte-stable.

Each texture covers `tile_m` metres of surface; meshes write UVs in metres / tile_m.
Generated in code rather than downloaded: no licence questions, no binary assets in git.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from PIL import Image

SIZE = 256


@dataclass(frozen=True)
class Spec:
    tile_m: float
    roughness: float


SPECS = {
    "grass": Spec(6.0, 0.95),
    "tarmac": Spec(4.0, 0.9),
    "paving": Spec(1.8, 0.85),
    "brick_red": Spec(2.0, 0.85),
    "brick_buff": Spec(2.0, 0.85),
    "render": Spec(2.0, 0.9),
    "roof_clay": Spec(2.0, 0.8),
    "roof_slate": Spec(2.0, 0.7),
    "roof_felt": Spec(2.0, 0.95),
}


def _tileable_noise(rng: np.random.Generator, scale: int) -> np.ndarray:
    """Smooth noise in [0, 1] that wraps at the edges (bilinear upsample of a periodic grid)."""
    g = rng.random((scale, scale))
    t = np.arange(SIZE) * scale / SIZE
    i0 = np.floor(t).astype(int)
    f = t - i0
    f = f * f * (3 - 2 * f)
    i1 = (i0 + 1) % scale
    rows = g[i0][:, i0] * (1 - f)[None, :] + g[i0][:, i1] * f[None, :]
    rows1 = g[i1][:, i0] * (1 - f)[None, :] + g[i1][:, i1] * f[None, :]
    return rows * (1 - f)[:, None] + rows1 * f[:, None]


def _fbm(seed: int, octaves=(4, 8, 16, 32), gains=(0.5, 0.25, 0.15, 0.1)) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = sum(g * _tileable_noise(rng, o) for o, g in zip(octaves, gains))
    return (n - n.min()) / (np.ptp(n) + 1e-9)


def _colour(base, variation: np.ndarray, amount: float) -> np.ndarray:
    base = np.asarray(base, dtype=float)[None, None, :]
    return np.clip(base * (1 - amount / 2 + amount * variation[..., None]), 0, 255)


def _courses(rows: int, cols: int, mortar_px: int, base, mortar, seed: int, stagger=True) -> np.ndarray:
    """Running-bond units (bricks, tiles, slabs) with per-unit colour variation."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[0:SIZE, 0:SIZE]
    row_h, col_w = SIZE / rows, SIZE / cols
    r = (y // row_h).astype(int)
    shift = np.where((r % 2 == 1) & stagger, col_w / 2, 0)
    c = (((x + shift) % SIZE) // col_w).astype(int)
    unit_var = rng.random((rows, cols + 1))[r, c]
    img = _colour(base, 0.6 * unit_var + 0.4 * _fbm(seed + 1), 0.35)
    in_mortar = ((y % row_h) < mortar_px) | ((((x + shift) % SIZE) % col_w) < mortar_px)
    img[in_mortar] = _colour(mortar, _fbm(seed + 2), 0.2)[in_mortar]
    return img


def _make(name: str) -> np.ndarray:
    if name == "grass":
        n = _fbm(11, octaves=(4, 16, 64), gains=(0.4, 0.35, 0.25))
        return _colour((86, 112, 60), n, 0.45)
    if name == "tarmac":
        n = _fbm(21, octaves=(8, 64, 128), gains=(0.3, 0.4, 0.3))
        return _colour((62, 62, 66), n, 0.35)
    if name == "paving":   # 600 mm slabs, 3 x 3 per tile
        return _courses(3, 3, 3, (150, 146, 138), (110, 106, 100), 31, stagger=False)
    if name == "brick_red":   # 26 courses x 9 bricks per 2 m (~75 x 220 mm)
        return _courses(26, 9, 2, (150, 70, 52), (190, 182, 168), 41)
    if name == "brick_buff":
        return _courses(26, 9, 2, (196, 168, 120), (205, 198, 185), 51)
    if name == "render":
        return _colour((228, 224, 214), _fbm(61, octaves=(8, 32, 128), gains=(0.4, 0.3, 0.3)), 0.12)
    if name == "roof_clay":   # 8 rows x 7 tiles per 2 m
        return _courses(8, 7, 3, (140, 66, 44), (90, 44, 30), 71)
    if name == "roof_slate":
        return _courses(10, 8, 2, (70, 74, 82), (40, 42, 48), 81)
    if name == "roof_felt":
        return _colour((58, 58, 60), _fbm(91), 0.25)
    raise KeyError(name)


@lru_cache(maxsize=None)
def image(name: str) -> Image.Image:
    return Image.fromarray(_make(name).astype(np.uint8), "RGB")
