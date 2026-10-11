# vuckfield
A virtual representation of Uckfield, England: a walkable 3D town in Unreal Engine 5, built from
public data and developed with **Surveyor**, this repo's own agent framework.

**Current region:** Nursery Lane to The Highlands pub, Ridgewood (400 m x 650 m).

## Fly around it (Unreal Engine 5.4+)
1. Open `unreal/Vuckfield.uproject`. If asked, choose your installed engine version.
   On first open, a "map not found" warning is expected; the level doesn't exist yet.
2. Menu **Vuckfield > Build level: nursery-lane**. This imports `build/regions/nursery-lane/*.glb`,
   creates `/Game/Vuckfield/Maps/L_nursery_lane`, adds sky and lighting, and puts the camera over Nursery Lane facing The Highlands.
3. Press **Play**. WASD + mouse to fly, E/Q for up/down. Landmarks are red.

No Python install is needed for this: region outputs are committed.

## Rebuild a region from source data (Python 3.11+)
```
cd pipeline
pip install -e ".[dev]"
python -m pytest -q
python -m vuckfield build nursery-lane      # cached downloads; --refresh to re-fetch
python tools/preview.py nursery-lane        # plan-view PNG sanity check
```

## How it's organised
- `regions/`: region definitions (British National Grid bbox, origin, landmarks, acceptance criteria)
- `pipeline/`: OpenStreetMap + Environment Agency LIDAR -> glb meshes + manifest
- `build/regions/`: generated outputs
- `unreal/`: UE5 project and the `vuckfield_ue` editor importer
- `surveyor/`, `.claude/`: the development framework (state, memory, roadmap, agents, skills).
  Start with `CLAUDE.md` and `surveyor/README.md`.

## Data and attribution
Map data (c) OpenStreetMap contributors, ODbL 1.0.
Contains Environment Agency information (c) Environment Agency and database right, OGL v3.0.
