---
description: Short current-state report for the human (branch, spec, PR, CI, next action).
---

# /status

Produce a short, phone-friendly current-state report. Inspect what is available;
if a field cannot be determined, write `unknown` rather than guessing.

## Steps

1. **Current branch** — `git rev-parse --abbrev-ref HEAD`.
2. **Current phase** — infer from state (e.g. `Spec review`, `In implementation`,
   `In review`) using the lifecycle in `docs/workflow/AGENT_WORKFLOW.md`.
3. **Linked issue** — from the branch, recent commits, or open PR.
4. **Linked spec** — the governing `SPEC-XXX` under `docs/specs/`.
5. **Open PR** — check for a PR from the current branch.
6. **Checks** — CI / governance status for the branch or PR, if available.
7. **Changed files** — `git status --short` and `git diff --name-only`.
8. **Blockers** — open questions, required human decisions, or drift issues.
9. **Recommended next action** — the single most sensible next step.

## Output format

```
Project status

Current branch:
Current phase:
Linked issue:
Linked spec:
Open PR:
Checks:
Changed files:
Blockers:
Recommended next action:
```

Keep it short. This is meant to be read on a phone.
