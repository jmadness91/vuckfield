# Vuckfield

A walkable 3D Uckfield, England, in Unreal Engine 5, built from public data.
Development is run by **World-Builder**, this repo's own agent framework (`world-builder/`, `.claude/`).

## Start of every session
1. Read `world-builder/STATE.md` (the SessionStart hook prints it). It is the only source of truth for
   "where are we"; do not reconstruct state from git log or memory.
2. If the task touches a decision area, read `world-builder/memory/decisions.md` first.
3. Pick the skill that fits (`.claude/skills/`) rather than improvising a process.

## Layout
| Path | What | Edited by |
|---|---|---|
| `regions/<id>.json` | Region definitions: BNG bbox, origin, landmarks, acceptance criteria | `add-region` skill |
| `pipeline/` | Python: OSM + EA LIDAR -> glb meshes + manifest | pipeline-engineer agent |
| `build/regions/<id>/` | Generated, committed so Unreal works without Python | pipeline only, never by hand |
| `unreal/` | UE5 project; `Content/Python/vuckfield_ue` imports regions | unreal-engineer agent |
| `world-builder/` | State, memory, roadmap, framework checks | every session via `handoff` |
| `.claude/agents`, `.claude/skills` | World-Builder agents and skills | framework changes only |

## Rules
- **Commit and push after every step that works.** Unpushed work is lost work; a stopped run must cost minutes, not the session.
- **End every session with the `handoff` skill** (updates `STATE.md`, commits, pushes).
- Regions are the unit of work. Grow the world by adding regions, not by enlarging one.
- Generated files (`build/`, `unreal/Content/Vuckfield/`) are never hand-edited; change the pipeline and rebuild.
- Every pipeline change: `cd pipeline && python -m pytest -q` and `python ../world-builder/check.py` must pass.
- Data must be open-licensed and attributed in `world-builder/memory/sources.md`.
- Unreal cannot run in the cloud container. Anything Unreal-side is **unverified** until the user
  confirms it in the editor; say so explicitly and record the result in `STATE.md`.
- Framework growth is earned: add an agent, skill or tool only when a real task needed it twice.
