"""Tests for the in-editor verifier (unreal/Content/Python/vuckfield_ue/verify.py), which has no
`unreal` dependency. Simulates what Unreal could do to the import and checks each is caught."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "ue_verify", ROOT / "unreal" / "Content" / "Python" / "vuckfield_ue" / "verify.py")
verify = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verify)

MANIFEST = json.loads((ROOT / "build" / "regions" / "nursery-lane" / "manifest.json").read_text())


def simulate(transform, scale=100.0, z_offset_cm=0.0, drop=()):
    """Measured bounds as Unreal would report them under a given (east, north) -> (x, y) transform."""
    out = {}
    for key, info in MANIFEST["files"].items():
        if key in drop:
            continue
        b = info["bounds_local_m"]
        corners = [transform(e, n) for e in b["x_east"] for n in b["y_north"]]
        xs, ys = [c[0] * scale for c in corners], [c[1] * scale for c in corners]
        zc = (b["z"][0] + b["z"][1]) / 2 * scale + z_offset_cm
        out[key] = {
            "centre": ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, zc),
            "extent": ((max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2, (b["z"][1] - b["z"][0]) / 2 * scale),
        }
    return out


# Faithful maps for a left-handed Z-up world: facing north, east is on the right.
FAITHFUL = {
    "east=+X, north=-Y": lambda e, n: (e, -n),
    "north=+X, east=+Y": lambda e, n: (n, e),
}
MIRRORED = {
    "east=+X, north=+Y": lambda e, n: (e, n),
    "east=-X, north=-Y": lambda e, n: (-e, -n),
}


@pytest.mark.parametrize("name", FAITHFUL)
def test_faithful_import_passes(name):
    r = verify.evaluate(MANIFEST, simulate(FAITHFUL[name]))
    assert r["verdict"] == "PASS", r["checks"]
    assert r["fit"]["worst_error_cm"] < 1
    assert r["fit"]["next_best_worst_error_cm"] > 2000  # orientation is unambiguous, not a near-tie


@pytest.mark.parametrize("name", MIRRORED)
def test_mirrored_import_fails(name):
    r = verify.evaluate(MANIFEST, simulate(MIRRORED[name]))
    assert r["verdict"] == "FAIL"
    assert not next(c for c in r["checks"] if c["name"] == "not mirrored")["ok"]


def test_import_left_in_metres_fails_scale():
    r = verify.evaluate(MANIFEST, simulate(FAITHFUL["east=+X, north=-Y"], scale=1.0))
    assert not next(c for c in r["checks"] if c["name"] == "scale is metres -> centimetres")["ok"]


def test_meshes_recentred_on_import_fails():
    measured = simulate(FAITHFUL["east=+X, north=-Y"])
    for m in measured.values():
        m["centre"] = (0.0, 0.0, m["centre"][2])
    assert verify.evaluate(MANIFEST, measured)["verdict"] == "FAIL"


def test_height_offset_fails():
    r = verify.evaluate(MANIFEST, simulate(FAITHFUL["east=+X, north=-Y"], z_offset_cm=-5000))
    assert not next(c for c in r["checks"] if c["name"].startswith("heights"))["ok"]


def test_missing_file_fails():
    r = verify.evaluate(MANIFEST, simulate(FAITHFUL["east=+X, north=-Y"], drop=("roads",)))
    assert r["verdict"] == "FAIL"
    assert "PASS" not in verify.summary_line("nursery-lane", r)


@pytest.mark.parametrize("key", ["roads", "buildings", "terrain", "landmark_the-highlands"])
def test_single_file_shifted_one_metre_fails(key):
    # Reviewer finding: an rms over all files let one file sit 4 m off and still PASS.
    measured = simulate(FAITHFUL["east=+X, north=-Y"])
    c = measured[key]["centre"]
    measured[key]["centre"] = (c[0] + 100, c[1], c[2])
    r = verify.evaluate(MANIFEST, measured)
    assert r["verdict"] == "FAIL"
    assert key in next(c for c in r["checks"] if c["name"].startswith("every file"))["detail"]


def test_roads_sunk_below_terrain_fail():
    # Reviewer finding: roads sit 15 cm above terrain; 99 cm low used to PASS.
    measured = simulate(FAITHFUL["east=+X, north=-Y"])
    c = measured["roads"]["centre"]
    measured["roads"]["centre"] = (c[0], c[1], c[2] - 20)
    assert verify.evaluate(MANIFEST, measured)["verdict"] == "FAIL"


def test_swapped_axes_with_wrong_size_detected():
    # Terrain imported with east/north extents swapped is caught by the size comparison.
    measured = simulate(FAITHFUL["east=+X, north=-Y"])
    e = measured["terrain"]["extent"]
    measured["terrain"]["extent"] = (e[1], e[0], e[2])
    assert verify.evaluate(MANIFEST, measured)["verdict"] == "FAIL"
