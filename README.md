# vuckfield
A virtual Uckfield, England: a walkable 3D town in Unreal Engine 5, built from public data and
developed with **World-Builder**, this repo's agent framework for building worlds.

**Current region:** Nursery Lane to The Highlands pub, Ridgewood (400 m x 650 m).
**Status:** milestone M0 (fly-through). The Unreal importer has not yet been confirmed in the editor.
See `world-builder/STATE.md`.

---

## Prerequisites

### To fly around the town (Unreal only)
| Requirement | Notes |
|---|---|
| Windows 10/11 64-bit (or macOS / Linux supported by UE5) | Instructions below assume Windows |
| **Unreal Engine 5.4 or later** | Install through the [Epic Games Launcher](https://www.unrealengine.com/download) -> Unreal Engine -> Library -> `+` |
| ~60 GB free disk for the engine, a few GB for the project | |
| DirectX 12 GPU with 6 GB+ VRAM (RTX 2070 / RX 6700 class or better) | Lumen lighting and virtual shadow maps are enabled |
| **Git** | [git-scm.com](https://git-scm.com/downloads). Git LFS is not needed |

No Visual Studio or C++ toolchain is needed: the project has no C++ code, so it opens without compiling.

### To rebuild regions from source data or run tests (optional)
| Requirement | Notes |
|---|---|
| **Python 3.11 – 3.13** | [python.org](https://www.python.org/downloads/); on Windows tick *Add python.exe to PATH* |
| Internet access | OpenStreetMap API and Environment Agency LIDAR service (both free, no key) |

All Python dependencies (numpy, shapely, pyproj, rasterio, trimesh, …) install from pip wheels; no GDAL install is needed.

### To develop with World-Builder (optional)
- [Claude Code](https://claude.com/claude-code). Opening the repo loads the agents, skills and the
  session-start hook from `.claude/` automatically.

---

## Install and run locally

### 1. Clone
```
git clone https://github.com/jmadness91/vuckfield.git
cd vuckfield
```

### 2. Open in Unreal and build the level
1. Double-click `unreal/Vuckfield.uproject`.
   - If Windows asks which program to use, or nothing happens: right-click the file ->
     **Switch Unreal Engine version…** -> pick your installed 5.x. (Alternatively: Epic Launcher ->
     Unreal Engine -> Library -> *Browse* -> select the `.uproject`.)
   - If prompted to enable the Python Editor Script Plugin or restart, accept.
   - A **"failed to load map L_nursery_lane"** warning on first open is expected; the level doesn't exist until step 2.
2. In the main menu bar choose **Vuckfield > Build level: nursery-lane**.
   It imports `build/regions/nursery-lane/*.glb`, creates `/Game/Vuckfield/Maps/L_nursery_lane`,
   adds sky and lighting, places the camera above Nursery Lane facing The Highlands, and saves.
   Re-running it is safe: it replaces the region's assets and actors.
3. Press **Play** (Alt+P).

| Control | Action |
|---|---|
| Mouse | Look |
| W / A / S / D | Fly forward / left / back / right |
| E / Q | Up / down |
| Esc | Stop playing |

Landmarks (Nursery Lane, The Highlands) are red. Terrain is green, roads dark grey, buildings beige.

**If the Vuckfield menu is missing:** open *Window > Output Log*, switch the input box from `Cmd` to
`Python` and run:
```
import vuckfield_ue; vuckfield_ue.build_level("nursery-lane")
```
Copy any red errors from the Output Log into an issue or your next Claude session.

### 3. Set up the Python pipeline (optional)
Windows (PowerShell):
```
cd pipeline
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```
macOS / Linux:
```
cd pipeline
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 4. Test
From `pipeline/` with the venv active:
```
python -m pytest -q              # pipeline unit tests (includes the framework check)
python ../world-builder/check.py # framework integrity: agents, skills, STATE, region builds
```
Both run in GitHub Actions on every push (`.github/workflows/ci.yml`).

### 5. Rebuild a region
```
python -m vuckfield regions                 # list and validate region definitions
python -m vuckfield build nursery-lane      # downloads are cached in data/cache/; add --refresh to re-fetch
python tools/preview.py nursery-lane        # writes build/regions/nursery-lane/preview.png (plan view)
```
Then in Unreal run **Vuckfield > Build level: nursery-lane** again to pick up the new meshes.

---

## How it's organised
| Path | What |
|---|---|
| `regions/` | Region definitions: British National Grid bbox, origin, landmarks, acceptance criteria |
| `pipeline/` | Python: OpenStreetMap + Environment Agency LIDAR -> glb meshes + `manifest.json` |
| `build/regions/` | Generated outputs, committed so Unreal works without Python. Never hand-edit |
| `unreal/` | UE5 project; `Content/Python/vuckfield_ue` is the importer and editor menu |
| `world-builder/` | Framework state (`STATE.md`), roadmap, memory (decisions, lessons, sources), `check.py` |
| `.claude/` | Framework agents (cartographer, pipeline-engineer, unreal-engineer, reviewer), skills, hooks |
| `CLAUDE.md` | Rules every development session follows |

Start with `world-builder/README.md` to understand the framework, and `world-builder/roadmap.md` for what's next.

## Data and attribution
Map data (c) OpenStreetMap contributors, ODbL 1.0.
Contains Environment Agency information (c) Environment Agency and database right, OGL v3.0.
