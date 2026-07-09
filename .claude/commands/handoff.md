---
description: Leave a clear state for the next agent or future session.
---

# /handoff

Leave a clear, honest state for the next agent or future session. Do not hide
failures. Use `docs/workflow/AGENT_HANDOFF_TEMPLATE.md` as the shape.

## What to gather

1. **Current branch** — `git rev-parse --abbrev-ref HEAD`.
2. **Current task** — one line: the task and its governing spec.
3. **Last completed action** — what is finished and verified.
4. **Files changed** — `git status --short`; group by category.
5. **Checks run** — every command run and its real result.
6. **Failing checks** — any failures, with the error text. Never omit these.
7. **Assumptions made** — decisions taken without explicit instruction.
8. **Open decisions** — what the human still needs to decide.
9. **Next safe action** — the single most sensible next step.

## Output format

```
Handoff

Current branch:
Current task:
Completed:
Files changed:
Checks run:
Failures:
Assumptions:
Open decisions:
Next safe action:
```
