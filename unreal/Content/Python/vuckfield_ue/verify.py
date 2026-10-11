"""Checks an imported region against its manifest. Pure Python, no `unreal` import,
so it runs in the editor AND in pipeline/tests (where it is unit-tested).

The importer measures each file's actors' world-space bounds in Unreal and passes them here as
{file_key: {"centre": (x, y, z), "extent": (x, y, z)}} in centimetres. We then work out how
geography (east, north, up in metres) actually landed in Unreal, instead of assuming it.
"""
import itertools
import math

CM_PER_M = 100.0
SCALE_TOLERANCE = 0.02  # +-2% of 100 cm/m
# The pipeline's bounds are exact (rounded to 1 cm), so limits can be tight. Roads sit only
# 15 cm above the terrain: a looser height limit would pass roads buried under it.
MAX_HORIZONTAL_ERROR_CM = 25.0  # per file: bounds centre and size, east/north
MAX_Z_ERROR_CM = 10.0           # per file: bounds centre and size, up


def _axis_maps():
    """All 8 axis-aligned 2D maps (signed permutations), as ((a, b), (c, d)) with
    ue_x = a*east + b*north, ue_y = c*east + d*north."""
    maps = []
    for swap in (False, True):
        for sx, sy in itertools.product((1, -1), (1, -1)):
            maps.append(((0, sx), (sy, 0)) if swap else ((sx, 0), (0, sy)))
    return maps


def _apply(m, e, n):
    return m[0][0] * e + m[0][1] * n, m[1][0] * e + m[1][1] * n


def _det(m):
    return m[0][0] * m[1][1] - m[0][1] * m[1][0]


def _axis_name(m, column):
    """Which UE axis a geographic axis (column 0 = east, 1 = north) points along, e.g. '-Y'."""
    x, y = m[0][column], m[1][column]
    return ("+" if (x or y) > 0 else "-") + ("X" if x else "Y")


def _swap_abs(m, e, n):
    """Half-extents (always positive) under an axis map: a swap moves east's extent to Y."""
    return (abs(m[0][0]) * e + abs(m[0][1]) * n, abs(m[1][0]) * e + abs(m[1][1]) * n)


def fit_horizontal(items):
    """items: [(key, (east_m, north_m) centre, (east_m, north_m) half-size,
                     (x_cm, y_cm) measured centre, (x_cm, y_cm) measured half-size), ...]

    Tries all 8 axis-aligned maps, fits a scale on the centres, and scores each map by its worst
    per-file error over centres AND sizes (sizes disambiguate swapped axes)."""
    results = []
    for m in _axis_maps():
        pred = [_apply(m, *c) for _, c, _, _, _ in items]
        num = sum(px * mc[0] + py * mc[1] for (px, py), (_, _, _, mc, _) in zip(pred, items))
        den = sum(px * px + py * py for px, py in pred)
        s = max(num / den, 0.0) if den else 0.0  # negative scale would just be the opposite map
        per_file = {}
        for (px, py), (key, _, half, mc, mh) in zip(pred, items):
            hx, hy = _swap_abs(m, *half)
            per_file[key] = max(abs(s * px - mc[0]), abs(s * py - mc[1]),
                                abs(s * hx - mh[0]), abs(s * hy - mh[1]))
        results.append((max(per_file.values()), s, m, per_file))
    results.sort(key=lambda r: r[0])
    worst, scale, m, per_file = results[0]
    return {
        "east_is": _axis_name(m, 0),
        "north_is": _axis_name(m, 1),
        "scale_cm_per_m": round(scale, 3),
        "worst_error_cm": round(worst, 1),
        "error_cm_by_file": {k: round(v, 1) for k, v in per_file.items()},
        "next_best_worst_error_cm": round(results[1][0], 1),
        # UE is left-handed (Z up, Y right of X), so a faithful (unmirrored) map has det -1:
        # facing north, east must be on your right.
        "mirrored": _det(m) == 1,
        "matrix": m,
    }


def _centre_m(bounds):
    return {k: (v[0] + v[1]) / 2.0 for k, v in bounds.items()}


def evaluate(manifest, measured):
    """manifest: parsed manifest.json (v2). measured: {file_key: {"centre": xyz_cm, "extent": xyz_cm}}.
    Returns {"verdict": "PASS"|"FAIL", "checks": [...], "fit": {...}}."""
    checks = []

    def check(name, ok, detail):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    files = manifest["files"]
    missing = [k for k in files if k not in measured]
    check("all files imported and placed", not missing,
          f"missing: {missing}" if missing else f"{len(files)} files")

    items = []
    for key, info in files.items():
        if key in measured:
            b = info["bounds_local_m"]
            c = _centre_m(b)
            half = ((b["x_east"][1] - b["x_east"][0]) / 2, (b["y_north"][1] - b["y_north"][0]) / 2)
            mc, mh = measured[key]["centre"], measured[key]["extent"]
            items.append((key, (c["x_east"], c["y_north"]), half, (mc[0], mc[1]), (mh[0], mh[1])))

    fit = None
    if len(items) >= 3:
        fit = fit_horizontal(items)
        scale_ok = abs(fit["scale_cm_per_m"] / CM_PER_M - 1) <= SCALE_TOLERANCE
        check("scale is metres -> centimetres", scale_ok,
              f"{fit['scale_cm_per_m']} cm per m (expected {CM_PER_M:.0f})")
        check("not mirrored", not fit["mirrored"],
              f"east -> {fit['east_is']}, north -> {fit['north_is']}")
        worst_key = max(fit["error_cm_by_file"], key=fit["error_cm_by_file"].get)
        check("every file in the right place and size", fit["worst_error_cm"] <= MAX_HORIZONTAL_ERROR_CM,
              f"worst {worst_key}: {fit['worst_error_cm']} cm (limit {MAX_HORIZONTAL_ERROR_CM:.0f}); "
              f"next best orientation {fit['next_best_worst_error_cm']} cm")
    else:
        check("orientation measurable", False, f"need >= 3 placed files, got {len(items)}")

    z_errors = {}
    for key, info in files.items():
        if key in measured:
            z = info["bounds_local_m"]["z"]
            centre_err = measured[key]["centre"][2] - (z[0] + z[1]) / 2 * CM_PER_M
            size_err = measured[key]["extent"][2] - (z[1] - z[0]) / 2 * CM_PER_M
            z_errors[key] = round(max(centre_err, size_err, key=abs), 1)
    worst = max(z_errors.items(), key=lambda kv: abs(kv[1]), default=(None, 0.0))
    check("heights match (metres above Ordnance Datum)", abs(worst[1]) <= MAX_Z_ERROR_CM,
          f"worst {worst[0]}: {worst[1]} cm off (limit {MAX_Z_ERROR_CM:.0f})")

    verdict = "PASS" if checks and all(c["ok"] for c in checks) else "FAIL"
    if fit:
        fit = {k: v for k, v in fit.items() if k != "matrix"}
    return {"verdict": verdict, "checks": checks, "fit": fit, "z_error_cm": z_errors}


def summary_line(region_id, result):
    failed = [c["name"] for c in result["checks"] if not c["ok"]]
    tail = "all checks passed" if not failed else "failed: " + "; ".join(failed)
    return f"VUCKFIELD BUILD {region_id}: {result['verdict']} - {tail}"
