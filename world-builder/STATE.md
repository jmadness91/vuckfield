# Vuckfield state

Last updated: 2026-10-11

## Now
- Milestone **M0: fly-through of region 1** (`world-builder/roadmap.md`), all pre-test work done.
- Region `nursery-lane`: Nursery Lane to The Highlands, Ridgewood. 400 m x 650 m, BNG origin 547600, 119800.

## Done this session
- Pipeline (`pipeline/`): OSM core API + EA LIDAR DTM 1 m -> glb, manifest v2 with per-file bounds.
  Roads/buildings drape on the exact 2 m terrain mesh surface (`meshes.TerrainSurface`). 36 tests passing.
- Region 1 built (`build/regions/nursery-lane/`): terrain 130k tris (30-63 m OD), 373 buildings,
  79 drawn road/path ways, landmarks The Highlands (way 416462289), Nursery Lane (ways 30317859, 61193065).
- Reviewer pass: all 4 pipeline acceptance criteria MET, verified independently against OSM; rebuild is
  byte-identical (no hand-edits). Its 2 HIGH + 3 MEDIUM findings fixed and regression-tested.
- Unreal API check against Epic docs 5.4-5.7: no wrong names/signatures; 5 bugs fixed (stale meshes
  re-spawned, unchecked load/save results, relative paths, dead Cancel button); terrain complex collision.
- Importer self-verifies (`vuckfield_ue/verify.py`): fits axis map, scale, mirroring, per-file position/size
  (25 cm) and height (10 cm); writes `unreal/Saved/Vuckfield/report_<region>.json` + one PASS/FAIL log line.
  Verifier and importer flow are unit-tested here against simulated imports and a fake `unreal` module.
- **UNVERIFIED: nothing has run in Unreal yet.**

## Next
1. User runs the M0 exit test (below) and sends the report JSON.
2. If FAIL: fix from the report (the `steps` list has tracebacks; `fit` shows axes/scale).
3. If PASS: M1 - LIDAR DSM building heights + pitched roofs (`world-builder/memory/sources.md`).

## Blocked / waiting on user
- **M0 exit test in UE 5.4+:** open `unreal/Vuckfield.uproject` -> *Vuckfield > Build level: nursery-lane*
  -> read the `VUCKFIELD BUILD nursery-lane: PASS/FAIL` line in the Output Log -> Play and fly
  (WASD + mouse, E/Q) from Nursery Lane to The Highlands.
  Send back: `unreal/Saved/Vuckfield/report_nursery-lane.json`, and whether flying looked right.

## Known cosmetic issues (not blocking M0)
- Buildings on the region edge overhang the terrain by up to 5 m (centroid-inside rule).
- Alignment fit leans on the two landmarks; regions with fewer landmarks need corner-based fitting.
