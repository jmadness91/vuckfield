"""Region build: sources -> meshes -> glb files + manifest.json."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import trimesh

from . import align, meshes, osm, roofs, sources
from .region import Region, bng_to_lonlat, lonlat_to_bng
from .terrain import Terrain

MANIFEST_VERSION = 2  # v2: per-file bounds_local_m for in-editor verification


def _matches(way: osm.Way, landmark: dict) -> bool:
    key, _, value = landmark["osm"].partition("=")
    return way.tags.get("name") == landmark["name"] and way.tags.get(key) == value


def _export(parts: list[trimesh.Trimesh], path: Path, node_prefix: str) -> dict:
    scene = trimesh.Scene()
    for i, m in enumerate(parts):
        scene.add_geometry(m, node_name=f"{node_prefix}_{i}", geom_name=f"{node_prefix}_{i}")
    path.write_bytes(scene.export(file_type="glb"))
    return {
        "file": path.name,
        "triangles": int(sum(len(m.faces) for m in parts)),
        "bytes": path.stat().st_size,
        "bounds_local_m": _bounds_local(parts),
    }


def _bounds_local(parts: list[trimesh.Trimesh]) -> dict:
    """AABB in local metres. Parts are already glTF y-up: east = x, up = y, north = -z."""
    v = np.vstack([m.vertices for m in parts])
    east, up, north = v[:, 0], v[:, 1], -v[:, 2]
    r = lambda a: [round(float(a.min()), 2), round(float(a.max()), 2)]  # noqa: E731
    return {"x_east": r(east), "y_north": r(north), "z": r(up)}


def build(region_id: str, refresh: bool = False, out_dir: Path | None = None) -> dict:
    region = Region.load(region_id)
    out = out_dir or region.build_dir
    out.mkdir(parents=True, exist_ok=True)

    terrain = Terrain.from_geotiff(sources.fetch_dtm(region, refresh))
    dsm = Terrain.from_geotiff(sources.fetch_dsm(region, refresh))
    ways = osm.read_ways(sources.fetch_osm(region, refresh))
    alignment = align.estimate_offset(osm.buildings(ways, region), terrain, dsm)
    ways = align.shift_ways(ways, alignment.dx, alignment.dy)
    roads = osm.roads(ways)
    buildings = osm.buildings(ways, region)
    fitted = {w.id: r for w in buildings if (r := roofs.fit_roof(w, terrain, dsm)) is not None}

    files: dict[str, dict] = {}
    surface = meshes.TerrainSurface(region, terrain)
    files["terrain"] = _export([meshes.terrain_mesh(region, surface)], out / "terrain.glb", "Terrain")

    landmark_info = []
    claimed: set[int] = set()
    for lm in region.landmarks:
        is_road = lm["osm"].startswith("highway=")
        pool = roads if is_road else buildings
        hits = [w for w in pool if _matches(w, lm)]
        if not hits:
            raise RuntimeError(f"landmark {lm['id']!r} not found in OSM data ({lm['osm']}, name={lm['name']!r})")
        claimed.update(w.id for w in hits)
        parts = (meshes.road_meshes(hits, region, surface, material="landmark") if is_road
                 else meshes.building_meshes(hits, region, surface, fitted, wall_material="landmark"))
        if not parts:
            raise RuntimeError(f"landmark {lm['id']!r} produced no geometry inside the region bbox")
        key = f"landmark_{lm['id']}"
        files[key] = _export(parts, out / f"{key}.glb", f"Landmark_{lm['id'].replace('-', '_')}")
        e, n = lonlat_to_bng(lm["lon"], lm["lat"])
        x, y = region.to_local(e, n)
        landmark_info.append({
            "id": lm["id"], "name": lm["name"], "file": f"{key}.glb",
            "osm_way_ids": sorted(w.id for w in hits),
            "local_m": {"x_east": round(x, 2), "y_north": round(y, 2),
                        "z": round(float(terrain.sample(e, n)), 2)},
        })

    files["roads"] = _export(
        meshes.road_meshes([w for w in roads if w.id not in claimed], region, surface), out / "roads.glb", "Roads")
    files["buildings"] = _export(
        meshes.building_meshes([w for w in buildings if w.id not in claimed], region, surface, fitted),
        out / "buildings.glb", "Buildings")

    grid = terrain.sample(*np.meshgrid(np.linspace(region.min_e, region.max_e, 50),
                                       np.linspace(region.min_n, region.max_n, 50)))
    olon, olat = bng_to_lonlat(region.origin_e, region.origin_n)
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "region": region.id,
        "name": region.name,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "coordinates": {
            "units": "metres",
            "convention": "glTF y-up: +x east, +y up (metres above Ordnance Datum), +z south",
            "origin_bng": {"e": region.origin_e, "n": region.origin_n},
            "origin_wgs84": {"lat": round(olat, 7), "lon": round(olon, 7)},
            "extent_local_m": {
                "x_east": [region.min_e - region.origin_e, region.max_e - region.origin_e],
                "y_north": [region.min_n - region.origin_n, region.max_n - region.origin_n],
            },
            "height_range_m": [round(float(grid.min()), 2), round(float(grid.max()), 2)],
        },
        "osm_alignment": alignment.as_dict(),
        "counts": {
            "road_ways_drawn": sum(1 for w in roads if meshes.road_width(w) is not None
                                   and meshes._clip_lines(w, region)),
            "buildings": len(buildings),
            "unnamed_buildings": sum(1 for w in buildings if "name" not in w.tags),
            "building_heights_from_lidar": len(fitted),
            "roof_shapes": {shape: sum(1 for w in buildings
                                       if meshes.building_roof(w, surface, fitted).shape == shape)
                            for shape in roofs.SHAPES},
        },
        "landmarks": landmark_info,
        "files": files,
        "attribution": [
            "Map data (c) OpenStreetMap contributors, ODbL 1.0",
            "Contains Environment Agency information (c) Environment Agency and database right; OGL v3.0",
        ],
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest

