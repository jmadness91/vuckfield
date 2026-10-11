# Roadmap

Each milestone has an exit test. A milestone is done when its exit test passes, not when code exists.

## M0: Fly-through of region 1 (current)
Nursery Lane to The Highlands, Ridgewood.
- [x] Pipeline: OSM roads + buildings, EA 1 m LIDAR terrain -> glb
- [x] Surveyor: agents, skills, state, memory, check, CI
- [ ] **Exit test (user, in UE5):** open `unreal/Vuckfield.uproject`, run *Vuckfield > Build level: nursery-lane*,
      press Play, fly from Nursery Lane to The Highlands. Terrain, roads, buildings visible; landmarks red.

## M1: Looks like Ridgewood, not a diagram
- Pitched roofs (OSM `roof:shape`, else a gable heuristic by footprint)
- Pavements/kerbs alongside residential roads; road junction cleanup
- Real materials (tarmac, brick, grass) instead of flat colours
- Terrain as a UE Landscape (heightmap export) so foliage and paint layers work
- Exit test: side-by-side screenshot against Street View at 3 chosen spots is recognisable

## M2: Walkable
- Collision on terrain/buildings; first-person character; ground-snapped start
- Exit test: walk Nursery Lane to The Highlands at walking pace without falling through or getting stuck

## M3: Region 2+
- Second region via `add-region` with seams matching region 1 (shared origin convention)
- Exit test: walk across the seam without a visible step

## M4: Landmarks with authored detail
- Hand-built or photogrammetry model for The Highlands; replace OSM box
- Exit test: user signs off the pub
