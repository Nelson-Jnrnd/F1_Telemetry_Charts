# AGENTS.md

Tool-neutral operating rules for **any** AI coding agent working in this
repository (Claude Code, Copilot, Cursor, aider, or others). This is the
vendor-neutral companion to `CLAUDE.md`; both describe the same workflow.

This project is **specification-first**. The repository is the single source of
truth. The full lifecycle is in `docs/workflow/AGENT_WORKFLOW.md`.

## Before editing

1. Inspect current state: branch, linked issue, governing spec, open PR, CI.
2. Find the spec that governs the work. If none exists and the task is a
   feature or behavior change, write a spec first.

## Core rules

- Never implement a feature or behavior change without an **approved** spec.
  The only exception is explicit repository-maintenance work that changes no
  product behavior.
- Keep changes minimal and scoped to the approved spec.
- Do not perform opportunistic refactors.
- Do not invent requirements. Requirements live only in specs.
- Do not suppress, skip, or delete failing tests to force a pass.
- Do not hide failed commands. Report every command and its real result.
- Ask for clarification only when genuinely blocked; otherwise proceed with
  explicitly recorded assumptions.
- Record assumptions explicitly.
- Update traceability (requirement ID → implementation → evidence) after
  implementing.
- Run relevant checks before claiming completion.
- Produce short, phone-friendly summaries.
- Never create a second source of truth. Do not restate requirements outside
  specs.
- If documentation conflicts, stop and run the drift check. If a blocking
  conflict exists, ask the human to decide.

## Specification lifecycle

1. Human intent/task.
2. Agent writes a verifiable spec from `docs/specs/SPEC_TEMPLATE.md`.
3. Human approves.
4. Agent writes an implementation plan.
5. Agent implements only the approved scope.
6. Agent runs checks and tests.
7. Agent opens a PR with evidence and requirement traceability.
8. Agent maintains traceability.
9. Agent hands off cleanly.

Approved specs may not be changed behaviorally without a **Spec Amendments**
entry.

## Gates

- Definition of Ready: `docs/workflow/DEFINITION_OF_READY.md`
- Definition of Done: `docs/workflow/DEFINITION_OF_DONE.md`
- Documentation authority: `docs/workflow/DOCUMENTATION_AUTHORITY.md`

## Validation

Governance is enforced by scripts under `scripts/` and the
`.github/workflows/governance.yml` workflow:

- `python scripts/validate_governance.py`
- `python scripts/validate_specs.py`
- `python scripts/validate_drift.py`

Run these before claiming completion.
