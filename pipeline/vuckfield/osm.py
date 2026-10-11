"""Minimal OSM XML reader: just the ways we turn into geometry."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import LineString, Polygon

from .region import Region, lonlat_to_bng


@dataclass
class Way:
    id: int
    tags: dict[str, str]
    coords: list[tuple[float, float]]  # BNG metres

    @property
    def closed(self) -> bool:
        return len(self.coords) >= 4 and self.coords[0] == self.coords[-1]

    def line(self) -> LineString:
        return LineString(self.coords)

    def polygon(self) -> Polygon:
        return Polygon(self.coords)


def read_ways(path: Path) -> list[Way]:
    root = ET.parse(path).getroot()
    nodes: dict[str, tuple[float, float]] = {}
    for n in root.iter("node"):
        nodes[n.get("id")] = lonlat_to_bng(float(n.get("lon")), float(n.get("lat")))
    ways = []
    for w in root.iter("way"):
        refs = [nd.get("ref") for nd in w.iter("nd")]
        if any(r not in nodes for r in refs) or len(refs) < 2:
            continue  # partially outside the download; the API includes all nodes, so rare
        tags = {t.get("k"): t.get("v") for t in w.iter("tag")}
        ways.append(Way(int(w.get("id")), tags, [nodes[r] for r in refs]))
    return ways


def roads(ways: list[Way]) -> list[Way]:
    return [w for w in ways if "highway" in w.tags and w.tags.get("area") != "yes"]


def buildings(ways: list[Way], region: Region) -> list[Way]:
    out = []
    for w in ways:
        if "building" not in w.tags or not w.closed:
            continue
        poly = w.polygon()
        if not poly.is_valid or poly.area < 4.0:
            continue
        c = poly.centroid
        if region.min_e <= c.x <= region.max_e and region.min_n <= c.y <= region.max_n:
            out.append(w)
    return out
