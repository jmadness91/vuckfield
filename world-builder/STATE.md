# Vuckfield state

Last updated: 2026-10-11

## Now
- Milestone **M1: looks like Ridgewood** (`world-builder/roadmap.md`); M0 exit test still owed by the user.
- Region `nursery-lane`: Nursery Lane to The Highlands, Ridgewood. 400 m x 650 m, BNG origin 547600, 119800.

## Done this session
- OSM aligned to LIDAR: shift (-1.86 E, +1.53 N), roof coverage 82% -> 98% (D9, D10).
- Building heights + roofs from EA LIDAR DSM - DTM (`pipeline/vuckfield/roofs.py`): 371/373 from LIDAR.
  Shapes: 199 gabled, 130 gabled-across, 30 hipped, 14 flat (none of them houses with sloped LIDAR).
  19 complex roofs use a gable at LIDAR 10th/90th percentile heights. All 373 meshes watertight, outward.
- Textured materials (`textures.py`): red/buff brick, render, clay tile, slate, felt, tarmac, paving, grass;
  UVs in true metres (roof courses level on every face); glbs carry normals. Region 1 = ~4.6 MB.
- Reviewer FAILED the first attempt (flat houses, rotated roof textures); all findings fixed + regression-tested.
- 78 tests passing. **UNVERIFIED: nothing has run in Unreal yet** (incl. how Interchange imports textures).

## Next
1. User runs the M0 exit test (below) and sends the report JSON; also: do textures/roofs look right?
2. Fix whatever the report shows.
3. Remaining M1: complex roofs by LIDAR segmentation (The Highlands), pavements/kerbs, Landscape terrain.

## Blocked / waiting on user
- **M0 exit test in UE 5.4+:** open `unreal/Vuckfield.uproject` -> *Vuckfield > Build level: nursery-lane*
  -> read the `VUCKFIELD BUILD nursery-lane: PASS/FAIL` line in the Output Log -> Play and fly
  (WASD + mouse, E/Q) from Nursery Lane to The Highlands.
  Send back: `unreal/Saved/Vuckfield/report_nursery-lane.json`, plus a screenshot or two.

## Known issues (not blocking)
- The Highlands' OSM outline includes ~25% non-building (north strip is ground in LIDAR); fixable in OSM itself.
- Roads sit ~1 m north of where the LIDAR prefers them (D10).
- Buildings on the region edge overhang the terrain by up to 5 m (centroid-inside rule).
- Alignment fit in the verifier leans on the two landmarks; regions with fewer landmarks need corner-based fitting.
