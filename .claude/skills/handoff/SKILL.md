---
name: handoff
description: End-of-session (or pre-risk) checkpoint - update STATE.md, run checks, commit and push so the next session can resume with zero loss. Use at the end of every session and before any long or risky operation.
---
# Handoff

1. Rewrite `world-builder/STATE.md` (keep its section headings; stay under ~80 lines):
   - **Now**: active milestone and region, one line each.
   - **Done this session**: concrete, verifiable items (file paths, counts). Unreal-side work is listed as
     UNVERIFIED until the user has confirmed it in the editor.
   - **Next**: the 1-3 next actions, specific enough to start without asking.
   - **Blocked / waiting on user**: exact asks.
   - Update `Last updated`.
2. New decisions -> `record-decision`. New lessons -> `world-builder/memory/lessons.md`. Tick roadmap boxes only for passed exit tests.
3. `cd pipeline && python -m pytest -q` and `python world-builder/check.py` from the root.
4. `git add -A && git commit` and `git push -u origin <branch>`. Confirm the push succeeded; an unpushed handoff did not happen.
