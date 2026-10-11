---
name: build-region
description: Regenerate a region's meshes and manifest from source data and verify them. Use after pipeline code changes, data refreshes, or region definition edits.
---
# Build a region

From `pipeline/`:
1. `python -m pytest -q` - stop if red.
2. `python -m vuckfield build <id>` (add `--refresh` only to re-download OSM/LIDAR; cached otherwise).
3. `python tools/preview.py <id>` and **look at** `build/regions/<id>/preview.png`: roads on streets,
   buildings on plots, landmarks red, north up. Anything odd is a finding, not a footnote.
4. Compare the new `manifest.json` counts/triangles with the committed one (`git diff --stat`, `git diff build/regions/<id>/manifest.json`).
   Explain every large change.
5. From repo root: `python surveyor/check.py`.
6. Commit code + regenerated outputs together and push.
