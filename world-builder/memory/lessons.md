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
