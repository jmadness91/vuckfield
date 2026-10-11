# Vuckfield

A walkable 3D Uckfield, England, in Unreal Engine 5, built from public data.
Development is run by **Surveyor**, this repo's own agent framework (`surveyor/`, `.claude/`).

## Start of every session
1. Read `surveyor/STATE.md` (the SessionStart hook prints it). It is the only source of truth for
   "where are we"; do not reconstruct state from git log or memory.
2. If the task touches a decision area, read `surveyor/memory/decisions.md` first.
3. Pick the skill that fits (`.claude/skills/`) rather than improvising a process.

## Layout
| Path | What | Edited by |
|---|---|---|
| `regions/<id>.json` | Region definitions: BNG bbox, origin, landmarks, acceptance criteria | `add-region` skill |
| `pipeline/` | Python: OSM + EA LIDAR -> glb meshes + manifest | world-builder agent |
| `build/regions/<id>/` | Generated, committed so Unreal works without Python | pipeline only, never by hand |
| `unreal/` | UE5 project; `Content/Python/vuckfield_ue` imports regions | unreal-engineer agent |
| `surveyor/` | State, memory, roadmap, framework checks | every session via `handoff` |
| `.claude/agents`, `.claude/skills` | Surveyor agents and skills | framework changes only |

## Rules
- **Commit and push after every step that works.** Unpushed work is lost work; a stopped run must cost minutes, not the session.
- **End every session with the `handoff` skill** (updates `STATE.md`, commits, pushes).
- Regions are the unit of work. Grow the world by adding regions, not by enlarging one.
- Generated files (`build/`, `unreal/Content/Vuckfield/`) are never hand-edited; change the pipeline and rebuild.
- Every pipeline change: `cd pipeline && python -m pytest -q` and `python ../surveyor/check.py` must pass.
- Data must be open-licensed and attributed in `surveyor/memory/sources.md`.
- Unreal cannot run in the cloud container. Anything Unreal-side is **unverified** until the user
  confirms it in the editor; say so explicitly and record the result in `STATE.md`.
- Framework growth is earned: add an agent, skill or tool only when a real task needed it twice.
