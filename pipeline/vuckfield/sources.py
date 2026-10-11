"""Downloads from public data sources, cached per region.

- OpenStreetMap API v0.6 `map` call (ODbL). Overpass is the usual choice but
  is unreliable from some networks; the core API is enough for small regions.
- Environment Agency LIDAR Composite DTM 1m via WCS (Open Government Licence).
"""
from __future__ import annotations

from pathlib import Path

import requests

from .region import Region

USER_AGENT = "vuckfield-pipeline/0.1 (+https://github.com/jmadness91/vuckfield)"
OSM_MAP_URL = "https://api.openstreetmap.org/api/0.6/map"
EA_WCS_URL = "https://environment.data.gov.uk/spatialdata/lidar-composite-digital-terrain-model-dtm-1m/wcs"
EA_DTM_COVERAGE = "13787b9a-26a4-4775-8523-806d13af58fc__Lidar_Composite_Elevation_DTM_1m"
# Last-return surface model: rooftops, with less tree canopy than first-return. Used for building heights.
EA_DSM_URL = "https://environment.data.gov.uk/spatialdata/lidar-composite-digital-surface-model-last-return-dsm-1m/wcs"
EA_DSM_COVERAGE = "9ba4d5ac-d596-445a-9056-dae3ddec0178__Lidar_Composite_Elevation_LZ_DSM_1m"

# Fetch a little beyond the region so roads and terrain don't stop short at the edge.
OSM_MARGIN_M = 50.0
DTM_MARGIN_M = 10.0


def _download(url: str, params: list[tuple[str, str]] | dict, dest: Path, timeout: int = 120) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    resp = requests.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    resp.raise_for_status()
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(resp.content)
    tmp.replace(dest)
    return dest


def fetch_osm(region: Region, refresh: bool = False) -> Path:
    dest = region.cache_dir / "map.osm"
    if dest.exists() and not refresh:
        return dest
    min_lon, min_lat, max_lon, max_lat = region.bbox_lonlat(OSM_MARGIN_M)
    bbox = f"{min_lon:.6f},{min_lat:.6f},{max_lon:.6f},{max_lat:.6f}"
    return _download(OSM_MAP_URL, {"bbox": bbox}, dest)


def _fetch_ea(region: Region, url: str, coverage: str, dest: Path, refresh: bool) -> Path:
    if dest.exists() and not refresh:
        return dest
    m = DTM_MARGIN_M
    params = [
        ("service", "WCS"),
        ("version", "2.0.1"),
        ("request", "GetCoverage"),
        ("CoverageId", coverage),
        ("format", "image/tiff"),
        ("subset", f"E({region.min_e - m:.0f},{region.max_e + m:.0f})"),
        ("subset", f"N({region.min_n - m:.0f},{region.max_n + m:.0f})"),
    ]
    return _download(url, params, dest)


def fetch_dtm(region: Region, refresh: bool = False) -> Path:
    return _fetch_ea(region, EA_WCS_URL, EA_DTM_COVERAGE, region.cache_dir / "dtm_1m.tif", refresh)


def fetch_dsm(region: Region, refresh: bool = False) -> Path:
    return _fetch_ea(region, EA_DSM_URL, EA_DSM_COVERAGE, region.cache_dir / "dsm_lz_1m.tif", refresh)
