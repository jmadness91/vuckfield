"""Command line: python -m vuckfield <command> <region>"""
from __future__ import annotations

import argparse
import json

from .build import build
from .region import REGIONS_DIR, Region


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="vuckfield")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="fetch data and generate meshes for a region")
    b.add_argument("region")
    b.add_argument("--refresh", action="store_true", help="re-download source data")
    sub.add_parser("regions", help="list and validate region definitions")
    args = p.parse_args(argv)

    if args.cmd == "regions":
        for path in sorted(REGIONS_DIR.glob("*.json")):
            r = Region.load(path.stem)
            print(f"{r.id:20} {r.max_e - r.min_e:.0f}m x {r.max_n - r.min_n:.0f}m  {r.name}")
        return 0
    manifest = build(args.region, refresh=args.refresh)
    print(json.dumps({k: manifest[k] for k in ("region", "counts", "files", "landmarks")}, indent=2))
    return 0
