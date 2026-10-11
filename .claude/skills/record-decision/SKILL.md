---
name: record-decision
description: Append an architectural or scope decision to Surveyor memory so future sessions do not re-decide it. Use whenever a choice is made between real alternatives, or a previous decision is reversed.
---
# Record a decision

Append to `surveyor/memory/decisions.md` (never edit earlier entries):

```
## D<next number>: <short title>
<YYYY-MM-DD>. <The decision in one or two sentences.> Why: <the reason, including the rejected alternative>.
<Consequences / when to revisit.> [Supersedes D<n>.]
```

If it supersedes an entry, also append `Superseded by D<new>.` under the old entry - the only permitted edit.
If the decision came from a mistake, also add a line to `surveyor/memory/lessons.md`.
Commit with the change it relates to.
