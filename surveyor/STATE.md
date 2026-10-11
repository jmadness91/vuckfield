# Vuckfield state

Last updated: 2026-10-11

## Now
- Milestone **M0: fly-through of region 1** (`surveyor/roadmap.md`)
- Region `nursery-lane`: Nursery Lane to The Highlands, Ridgewood. 400 m x 650 m, BNG origin 547600, 119800.

## Done this session
- Pipeline (`pipeline/`): OSM core API + EA LIDAR DTM 1 m -> glb. 17 tests passing.
- Region 1 built (`build/regions/nursery-lane/`): terrain 130k tris (heights 30-63 m OD),
  373 buildings, 124 road/path ways, landmarks The Highlands (OSM way 416462289) and Nursery Lane
  (ways 30317859, 61193065). Plan-view preview checked: geography and orientation correct.
- Unreal project (`unreal/Vuckfield.uproject`) + importer `vuckfield_ue` + *Vuckfield* editor menu.
  **UNVERIFIED: never run in Unreal.**
- Surveyor: 4 agents, 4 skills, SessionStart hook, memory files, `surveyor/check.py`, CI workflow.

## Next
1. User runs the M0 exit test (below) and reports the result or the Output Log errors.
2. Fix whatever the first Unreal run breaks (expect something: the importer is untested).
3. Start M1 with pitched roofs + LIDAR DSM building heights (`surveyor/memory/sources.md`).

## Blocked / waiting on user
- **M0 exit test in UE 5.4+:** open `unreal/Vuckfield.uproject` (pick your engine version if asked) ->
  menu *Vuckfield > Build level: nursery-lane* -> Play -> fly (WASD + mouse, E/Q up/down) from Nursery Lane
  north to The Highlands. Report: did it build, do roads/buildings sit on the terrain, are the landmarks red.
