# Agent Handoff Template

Fill this in at the end of a session (or when asked to hand off) so the next
agent or future session can resume safely. This is the same shape the
`/handoff` command produces.

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

## Field guidance

- **Current branch** — the branch the work lives on.
- **Current task** — one line: what is being worked on and its governing spec.
- **Completed** — what is finished and verified.
- **Files changed** — grouped by category (docs, tooling, tests, source).
- **Checks run** — every command run and its real result.
- **Failures** — any failing check, with the error. Do not hide these.
- **Assumptions** — decisions made in the absence of explicit instruction.
- **Open decisions** — what the human still needs to decide.
- **Next safe action** — the single most sensible next step.
