# World-Builder

An agent framework for building virtual worlds, starting with Vuckfield. It exists to do one thing:
let a sequence of Claude sessions (and you) keep building the same world without losing context,
repeating mistakes, or re-deciding settled questions.

It currently lives inside this repo. It becomes a standalone framework when a second world gives
evidence of what is generic (decision D8).

## Design principle
World-Builder is built **on** Claude Code's native primitives, not beside them. There is no custom
orchestrator, queue or runtime. That is deliberate: a bespoke agent runtime is a second
product to maintain, and the world is the product.

| Capability | Mechanism | Where |
|---|---|---|
| Agents | Claude Code subagents with narrow roles and tool sets | `.claude/agents/*.md` |
| Skills | Repeatable procedures, invoked by name | `.claude/skills/*/SKILL.md` |
| Context management | One live state file, injected at session start by a hook | `world-builder/STATE.md`, `.claude/settings.json` |
| Long-term memory | Append-only decision log, lessons, data-source register | `world-builder/memory/` |
| Plan | Milestones with exit criteria | `world-builder/roadmap.md` |
| Guardrails | Framework integrity check + pipeline tests, run in CI | `world-builder/check.py`, `.github/workflows/ci.yml` |

## Agents
| Agent | Owns | Does not touch |
|---|---|---|
| `cartographer` | Region definitions, data sources, data QA | Unreal, mesh code |
| `pipeline-engineer` | `pipeline/` code and `build/` outputs | Region scope decisions, Unreal |
| `unreal-engineer` | `unreal/` project, config, import scripts | Pipeline geometry |
| `reviewer` | Read-only verification against acceptance criteria | Anything (reports only) |

The main session is the orchestrator: it reads STATE, chooses a skill, delegates to agents, and
hands off. Agents never update `STATE.md`; only the orchestrating session does, via `handoff`.

## Skills
| Skill | When |
|---|---|
| `add-region` | Extending the world to a new street/area |
| `build-region` | Regenerating a region's assets after pipeline or data changes |
| `record-decision` | Any choice a future session might otherwise re-litigate |
| `handoff` | End of every session, or before any risky operation |

## Context budget rules
- `STATE.md` stays under ~80 lines. Detail goes to memory files; STATE links to them.
- `decisions.md` and `lessons.md` are append-only; supersede entries rather than editing them.
- Agents receive a self-contained brief (goal, files, acceptance), never "see above".
