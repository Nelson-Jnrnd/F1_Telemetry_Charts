# CLAUDE.md

Authoritative operating instructions for Claude Code agents working in this
repository. Read this before doing anything. These rules override convenience.

This project uses a **specification-first, agent-led** workflow. The repository
is the single source of truth. See `docs/workflow/AGENT_WORKFLOW.md` for the
full lifecycle and `AGENTS.md` for the tool-neutral version of these rules.

## Before you edit anything

1. Inspect current state first: branch, linked issue, relevant spec, open PR,
   and CI status. Use `/status` if in doubt.
2. Identify which spec governs the work. If none exists and the work is a
   feature or behavior change, you must write a spec first (see below).

## Core rules

- **Never implement a feature or behavior change without an approved spec.**
  The only exception is explicit repository-maintenance tasks (docs, tooling,
  chores) that change no product behavior.
- **Keep changes minimal and scoped** to the approved spec. Do only what the
  spec requires.
- **Do not do opportunistic refactors.** If you spot unrelated cleanup, note it
  for a future spec; do not fold it into the current change.
- **Do not invent requirements.** Requirements live only in specs. If something
  is unspecified, record it as an assumption or an open question — do not decide
  silently.
- **Do not suppress, skip, or delete failing tests** to make a build pass.
- **Do not hide failed commands.** Report every command you run and its real
  result, including failures.
- **Ask for clarification only when genuinely blocked.** Otherwise proceed with
  explicitly recorded assumptions.
- **Record assumptions explicitly** in the spec, PR, or handoff.
- **Update traceability after implementation** — map each changed behavior back
  to a requirement ID in the spec's verification matrix.
- **Run relevant checks before claiming completion.** Never report work as done
  without running the governance scripts and any discoverable tests.
- **Produce phone-friendly summaries** — short, plain-language, skimmable on a
  phone.
- **Never create a second source of truth.** Do not restate requirements in
  READMEs, reports, or code comments as if they were authoritative.
- **If documentation conflicts, stop** and run `/drift-check`. If a blocking
  conflict exists, ask the human to decide — do not guess.

## Specification workflow (summary)

1. Human gives an intent/task.
2. Agent writes a detailed, point-by-point, verifiable spec from
   `docs/specs/SPEC_TEMPLATE.md` into `docs/specs/active/`.
3. Human reviews and approves (status → `Approved`, moved to `approved/`).
4. Agent writes an implementation plan.
5. Agent implements only the approved scope.
6. Agent runs checks and tests.
7. Agent opens a PR with evidence, linking the spec and requirement IDs.
8. Agent maintains traceability from requirement to implementation.
9. Agent leaves the repo in a clear state (`/handoff`).

An approved spec must not be silently rewritten. Behavioral changes to an
approved spec require a **Spec Amendments** entry (see the template).

## Definition of Ready / Done

Implementation cannot start until the spec meets
`docs/workflow/DEFINITION_OF_READY.md`. Work is not complete until it meets
`docs/workflow/DEFINITION_OF_DONE.md`.

## Commands

- `/status` — short current-state report.
- `/spec-report` — state of all specs and the roadmap.
- `/drift-check` — detect documentation drift and conflicting specs.
- `/handoff` — leave a clear state for the next agent.

## Project stack

At bootstrap time this repository contains no application code, so build and
test commands are not yet defined. When code is added, record the build/test
commands here and in `CONTRIBUTING.md`, and wire them into
`.github/workflows/ci.yml`. Do not invent build commands.
