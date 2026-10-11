"""Render an oblique 3D close-up of a built region (sanity check for heights and roofs).

Usage: python tools/oblique.py <region> <east_m> <north_m> [radius_m] [out.png]
(east/north are local metres from the region origin, as in the plan-view preview)
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def triangles(path, cx, cy, r):
    scene = trimesh.load(path, force="scene")
    out = []
    for name in scene.graph.nodes_geometry:
        tf, gname = scene.graph[name]
        m = scene.geometry[gname].copy()
        m.apply_transform(tf)
        colour = getattr(m.visual.material, "baseColorFactor", None)
        colour = np.asarray(colour if colour is not None else [200, 200, 200, 255]) / 255.0
        tri = m.vertices[m.faces][:, :, [0, 2, 1]] * [1, -1, 1]  # -> east, north, up
        c = tri.mean(axis=1)
        keep = (np.abs(c[:, 0] - cx) < r) & (np.abs(c[:, 1] - cy) < r)
        if keep.any():
            n = np.cross(tri[keep, 1] - tri[keep, 0], tri[keep, 2] - tri[keep, 0])
            n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
            shade = 0.55 + 0.45 * np.clip(n @ np.array([0.4, -0.5, 0.77]), 0, 1)
            out.append((tri[keep], np.clip(colour[None, :3] * shade[:, None], 0, 1)))
    return out


def main():
    region, cx, cy = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    r = float(sys.argv[4]) if len(sys.argv) > 4 else 60.0
    d = ROOT / "build" / "regions" / region
    out = Path(sys.argv[5]) if len(sys.argv) > 5 else d / f"oblique_{int(cx)}_{int(cy)}.png"
    fig = plt.figure(figsize=(12, 9), dpi=100)
    ax = fig.add_subplot(projection="3d")
    tris, cols = [], []
    for f in sorted(d.glob("*.glb")):
        for tri, col in triangles(f, cx, cy, r):
            tris.append(tri)
            cols.append(col)
    # One collection so matplotlib depth-sorts every triangle together (painter's algorithm).
    tris, cols = np.concatenate(tris), np.concatenate(cols)
    ax.add_collection3d(Poly3DCollection(tris, facecolors=cols, edgecolors="none"))
    zs = [tris[:, :, 2]]
    z = np.concatenate([a.ravel() for a in zs])
    ax.set_xlim(cx - r, cx + r)
    ax.set_ylim(cy - r, cy + r)
    ax.set_zlim(z.min(), z.min() + 2 * r * 0.35)
    ax.set_box_aspect((1, 1, 0.35))
    ax.view_init(elev=32, azim=-60)
    ax.set_axis_off()
    fig.tight_layout()
    fig.savefig(out)
    print(out)


if __name__ == "__main__":
    main()
