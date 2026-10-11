---
name: add-region
description: Extend the Vuckfield world with a new region (street or area) - define it, build it, review it, hand it to Unreal. Use when the user names a new street, building or area to model.
---
# Add a region

1. **Define** (delegate to `cartographer`): locate the area and its landmarks with Nominatim/OSM, choose a
   BNG bbox on whole metres that abuts existing regions where adjacent, origin at the bbox centre (rounded
   to 10 m), and write `regions/<id>.json` with landmarks (name + OSM tag) and testable acceptance criteria.
   Validate: `cd pipeline && python -m vuckfield regions`.
2. **Commit and push** the definition.
3. **Build**: run the `build-region` skill for `<id>`.
4. **Review** (delegate to `reviewer`) against the region's acceptance criteria.
5. **Unreal**: the Vuckfield menu picks up the new region automatically at editor start. Give the user the
   verification steps; mark the region UNVERIFIED-IN-UE in `STATE.md` until they confirm.
6. Run `handoff`.
