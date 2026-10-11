"""Render a plan-view PNG of a built region (sanity check without Unreal).

Usage: python tools/preview.py nursery-lane [out.png]
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    scene = trimesh.load(path, force="scene")
    return [g.copy().apply_transform(scene.graph.get(n)[0]) for n in scene.graph.nodes_geometry
            for g in [scene.geometry[scene.graph[n][1]]]]


def main():
    region = sys.argv[1]
    d = ROOT / "build" / "regions" / region
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else d / "preview.png"
    manifest = json.loads((d / "manifest.json").read_text())
    fig, ax = plt.subplots(figsize=(8, 12), dpi=110)
    t = load(d / "terrain.glb")[0]
    v = t.vertices  # glTF: x east, y up, z south
    sc = ax.tricontourf(v[:, 0], -v[:, 2], v[:, 1], levels=30, cmap="terrain")
    fig.colorbar(sc, ax=ax, shrink=0.5, label="height m (OD)")
    style = {"roads": ("#333", 1.0), "buildings": ("#d9cbb6", 1.0)}
    for name, (colour, alpha) in style.items():
        for m in load(d / f"{name}.glb"):
            tri = m.vertices[m.faces][:, :, [0, 2]] * [1, -1]
            ax.add_collection(matplotlib.collections.PolyCollection(tri, facecolors=colour, edgecolors="none", alpha=alpha))
    for lm in manifest["landmarks"]:
        for m in load(d / lm["file"]):
            tri = m.vertices[m.faces][:, :, [0, 2]] * [1, -1]
            ax.add_collection(matplotlib.collections.PolyCollection(tri, facecolors="#c0301e", edgecolors="#c0301e"))
        p = lm["local_m"]
        ax.annotate(lm["name"], (p["x_east"], p["y_north"]), xytext=(8, 8), textcoords="offset points",
                    fontsize=9, weight="bold", bbox=dict(boxstyle="round", fc="white", alpha=0.8))
    ax.set_aspect("equal")
    ax.set_title(f"{manifest['name']} - plan view (north up, metres from origin)")
    fig.tight_layout()
    fig.savefig(out)
    print(out)


if __name__ == "__main__":
    main()
