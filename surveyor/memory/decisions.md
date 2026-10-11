# Decisions

Append-only. To change a decision, add a new entry that supersedes the old one by number.
Format: `## D<n>: title` / date / decision / why / consequences.

## D1: Surveyor uses Claude Code primitives, no custom runtime
2026-10-11. Agents = `.claude/agents`, skills = `.claude/skills`, context = `STATE.md` + SessionStart hook,
memory = markdown files. Why: a bespoke orchestrator is a second product; the world is the product.
Revisit only if a concrete need cannot be met by subagents/skills/hooks.

## D2: British National Grid (EPSG:27700) is the world coordinate system
2026-10-11. All regions are rectangles in BNG metres. Each region has its own origin for float precision.
Why: UK source data is native BNG, metres are uniform, no projection distortion at town scale.
Consequence: cross-region seams are exact as long as both use BNG; Unreal placement = (origin delta) * 100.

## D3: Terrain from Environment Agency LIDAR DTM 1 m, meshed at 2 m
2026-10-11. Why: open (OGL), 1 m bare-earth, covers Uckfield. 2 m spacing keeps region 1 at 130k triangles.
Terrain ships as a static mesh in M0; Landscape conversion is deferred to M1.

## D4: OSM via the core API `/map` call, not Overpass
2026-10-11. Overpass endpoints were unreachable from the cloud environment; the core API works and is
sufficient for regions under ~4 km^2 (enforced in `Region.validate`). Cached in `data/cache/` (gitignored).

## D5: glTF (.glb) is the pipeline -> Unreal interchange format
2026-10-11. Pure-Python export (trimesh), imported by UE's Interchange. Geometry is converted from
z-up (x east, y north) to glTF y-up with a proper rotation (glTF +z = south) so nothing is mirrored.

## D6: Generated region outputs are committed
2026-10-11. `build/regions/<id>/` (~3 MB per region) is committed so the Unreal side works without a
Python environment. Unreal `.uasset`s generated from it are NOT committed; the import script rebuilds them.
Revisit when the repo exceeds ~200 MB (move to Git LFS or a release artifact).

## D7: Unreal side targets UE 5.4+ with Python editor scripting
2026-10-11. `EngineAssociation` is left blank so the user picks their installed version. Import is an
idempotent Python script exposed as a *Vuckfield* editor menu, not C++. C++ only when Python cannot.
