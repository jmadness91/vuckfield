"""Checks an imported region against its manifest. Pure Python, no `unreal` import,
so it runs in the editor AND in pipeline/tests (where it is unit-tested).

The importer measures each file's actors' world-space bounds in Unreal and passes them here as
{file_key: {"centre": (x, y, z), "extent": (x, y, z)}} in centimetres. We then work out how
geography (east, north, up in metres) actually landed in Unreal, instead of assuming it.
"""
import itertools
import math

CM_PER_M = 100.0
SCALE_TOLERANCE = 0.05  # +-5% of 100 cm/m
MAX_RMS_CM = 200.0      # bounds centres within ~2 m of where they should be
MAX_Z_ERROR_CM = 100.0


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


def fit_horizontal(pairs):
    """pairs: [((east_m, north_m), (ue_x_cm, ue_y_cm)), ...] -> best axis map, scale and error."""
    results = []
    for m in _axis_maps():
        pred = [_apply(m, e, n) for (e, n), _ in pairs]
        num = sum(px * qx + py * qy for (px, py), (_, q) in zip(pred, pairs) for qx, qy in [q])
        den = sum(px * px + py * py for px, py in pred)
        s = max(num / den, 0.0) if den else 0.0  # negative scale would just be the opposite map
        rms = math.sqrt(sum((s * px - q[0]) ** 2 + (s * py - q[1]) ** 2
                            for (px, py), (_, q) in zip(pred, pairs)) / len(pairs))
        results.append((rms, s, m))
    results.sort(key=lambda r: r[0])
    rms, scale, m = results[0]
    return {
        "east_is": _axis_name(m, 0),
        "north_is": _axis_name(m, 1),
        "scale_cm_per_m": round(scale, 3),
        "rms_cm": round(rms, 1),
        "next_best_rms_cm": round(results[1][0], 1),
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

    pairs, keys = [], []
    for key, info in files.items():
        if key in measured:
            c = _centre_m(info["bounds_local_m"])
            mc = measured[key]["centre"]
            pairs.append(((c["x_east"], c["y_north"]), (mc[0], mc[1])))
            keys.append(key)

    fit = None
    if len(pairs) >= 3:
        fit = fit_horizontal(pairs)
        scale_ok = abs(fit["scale_cm_per_m"] / CM_PER_M - 1) <= SCALE_TOLERANCE
        check("scale is metres -> centimetres", scale_ok,
              f"{fit['scale_cm_per_m']} cm per m (expected {CM_PER_M:.0f})")
        check("not mirrored", not fit["mirrored"],
              f"east -> {fit['east_is']}, north -> {fit['north_is']}")
        check("pieces line up with each other", fit["rms_cm"] <= MAX_RMS_CM,
              f"rms {fit['rms_cm']} cm (limit {MAX_RMS_CM:.0f}); next best orientation {fit['next_best_rms_cm']} cm")
    else:
        check("orientation measurable", False, f"need >= 3 placed files, got {len(pairs)}")

    z_errors = {}
    for key, info in files.items():
        if key in measured:
            expected = _centre_m(info["bounds_local_m"])["z"] * CM_PER_M
            z_errors[key] = round(measured[key]["centre"][2] - expected, 1)
    worst = max(z_errors.items(), key=lambda kv: abs(kv[1]), default=(None, 0.0))
    check("heights match terrain (Ordnance Datum)", abs(worst[1]) <= MAX_Z_ERROR_CM,
          f"worst {worst[0]}: {worst[1]} cm off")

    if "terrain" in measured:
        b = files["terrain"]["bounds_local_m"]
        want = sorted([(b["x_east"][1] - b["x_east"][0]) * CM_PER_M, (b["y_north"][1] - b["y_north"][0]) * CM_PER_M])
        got = sorted([2 * measured["terrain"]["extent"][0], 2 * measured["terrain"]["extent"][1]])
        ok = all(abs(g / w - 1) <= SCALE_TOLERANCE for g, w in zip(got, want))
        check("terrain size", ok, f"{[round(g) for g in got]} cm vs expected {[round(w) for w in want]} cm")

    verdict = "PASS" if checks and all(c["ok"] for c in checks) else "FAIL"
    if fit:
        fit = {k: v for k, v in fit.items() if k != "matrix"}
    return {"verdict": verdict, "checks": checks, "fit": fit, "z_error_cm": z_errors}


def summary_line(region_id, result):
    failed = [c["name"] for c in result["checks"] if not c["ok"]]
    tail = "all checks passed" if not failed else "failed: " + "; ".join(failed)
    return f"VUCKFIELD BUILD {region_id}: {result['verdict']} - {tail}"
