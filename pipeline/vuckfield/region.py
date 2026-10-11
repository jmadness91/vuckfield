"""Region definitions: the unit of work for building the world.

A region is a rectangle in British National Grid (EPSG:27700) metres with a
local origin. Every generated asset for a region is expressed relative to that
origin so Unreal never has to deal with six-figure coordinates.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from pyproj import Transformer

REPO_ROOT = Path(__file__).resolve().parents[2]
REGIONS_DIR = REPO_ROOT / "regions"
CACHE_DIR = REPO_ROOT / "data" / "cache"
BUILD_DIR = REPO_ROOT / "build" / "regions"

_to_bng = Transformer.from_crs(4326, 27700, always_xy=True)
_to_wgs = Transformer.from_crs(27700, 4326, always_xy=True)


def lonlat_to_bng(lon: float, lat: float) -> tuple[float, float]:
    return _to_bng.transform(lon, lat)


def bng_to_lonlat(e: float, n: float) -> tuple[float, float]:
    return _to_wgs.transform(e, n)


@dataclass(frozen=True)
class Region:
    id: str
    name: str
    min_e: float
    min_n: float
    max_e: float
    max_n: float
    origin_e: float
    origin_n: float
    mesh_spacing_m: float
    landmarks: list[dict] = field(default_factory=list)
    acceptance: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, region_id: str) -> "Region":
        path = REGIONS_DIR / f"{region_id}.json"
        raw = json.loads(path.read_text())
        bbox, origin = raw["bbox_bng"], raw["origin_bng"]
        region = cls(
            id=raw["id"],
            name=raw["name"],
            min_e=bbox["min_e"],
            min_n=bbox["min_n"],
            max_e=bbox["max_e"],
            max_n=bbox["max_n"],
            origin_e=origin["e"],
            origin_n=origin["n"],
            mesh_spacing_m=raw["terrain"]["mesh_spacing_m"],
            landmarks=raw.get("landmarks", []),
            acceptance=raw.get("acceptance", []),
        )
        region.validate()
        return region

    def validate(self) -> None:
        if not (self.min_e < self.max_e and self.min_n < self.max_n):
            raise ValueError(f"{self.id}: bbox is empty or inverted")
        if not (self.min_e <= self.origin_e <= self.max_e and self.min_n <= self.origin_n <= self.max_n):
            raise ValueError(f"{self.id}: origin lies outside bbox")
        # OSM API /map refuses areas over 0.25 sq deg; keep regions well inside that.
        if (self.max_e - self.min_e) * (self.max_n - self.min_n) > 4_000_000:
            raise ValueError(f"{self.id}: region larger than 4 km^2; split it")
        for lm in self.landmarks:
            e, n = lonlat_to_bng(lm["lon"], lm["lat"])
            if not (self.min_e <= e <= self.max_e and self.min_n <= n <= self.max_n):
                raise ValueError(f"{self.id}: landmark {lm['id']!r} lies outside bbox")

    def bbox_lonlat(self, margin_m: float = 0.0) -> tuple[float, float, float, float]:
        """(min_lon, min_lat, max_lon, max_lat) enclosing the BNG rectangle."""
        corners = [
            bng_to_lonlat(e, n)
            for e in (self.min_e - margin_m, self.max_e + margin_m)
            for n in (self.min_n - margin_m, self.max_n + margin_m)
        ]
        lons, lats = zip(*corners)
        return min(lons), min(lats), max(lons), max(lats)

    def to_local(self, e: float, n: float) -> tuple[float, float]:
        """BNG metres -> local metres (x east, y north) from the region origin."""
        return e - self.origin_e, n - self.origin_n

    @property
    def cache_dir(self) -> Path:
        return CACHE_DIR / self.id

    @property
    def build_dir(self) -> Path:
        return BUILD_DIR / self.id
