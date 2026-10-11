# Lessons

Append-only. Things that cost time once and must not cost it twice.

- **2026-10-11: An earlier session's work was lost** because it was never committed or pushed before the
  run was stopped. Hence the rule: commit and push after every working step; end with `handoff`.
- **2026-10-11: Triangle winding is easy to get backwards.** Road ribbons were first generated facing
  down, which Unreal would back-face cull (invisible roads). Caught by `test_road_ribbon_faces_up_and_has_width`.
  Any new mesh generator needs an "up-facing" test.
- **2026-10-11: Names are not unique.** "The Highlands" is both the pub and a nearby road. Landmarks
  match on name AND an OSM tag (`amenity=pub`, `highway=*`).
- **2026-10-11: Overpass blocked from cloud sessions** (connection reset). Use the OSM core API.
- **2026-10-11: An aggregate tolerance hides a single bad part.** The first in-editor verifier used one
  RMS across all files with a 2 m limit and a 1 m height limit; the reviewer showed a single file 4 m off,
  or roads 99 cm under the terrain, would PASS. Verify per part, with limits sized to the smallest
  meaningful offset (roads are lifted 15 cm, so heights need ~10 cm).
- **2026-10-11: Sample the surface you draw.** Roads draped on the 1 m DTM dipped up to 19 cm under the
  2 m terrain mesh. Anything placed on terrain samples `TerrainSurface`, never the raw DTM.
- **2026-10-11: Decide the verdict last.** The report's verdict was computed before the save step, so a
  failed save still printed PASS. Caught by a test written for the reviewer's finding.
- **2026-10-11: The reviewer and an API-docs check paid for themselves** before any local test:
  7 real bugs found with no Unreal available. Run both before handing Unreal work to the user.
