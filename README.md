# paleo-map

> This repository is bootstrapped for **specification-first, AI-agent-led
> development**. No application code exists yet — the first commit set up the
> workflow, not a product.

## How this project works

- **Features start with specs.** Every feature or behavior change begins as a
  written, verifiable specification under [`docs/specs/`](docs/specs/).
- **Implementation starts only after spec approval.** An agent will not write
  product code until you approve the spec.
- **PRs must reference specs.** Every pull request links its spec and the
  requirement IDs it implements, with verification evidence.
- **Governance checks protect consistency.** Lightweight scripts under
  [`scripts/`](scripts/) run in CI to catch missing pieces and documentation
  drift.

This README is derived documentation. Authoritative truth lives in the specs.
See [`docs/workflow/DOCUMENTATION_AUTHORITY.md`](docs/workflow/DOCUMENTATION_AUTHORITY.md).

## Start here

- Agents: read [`CLAUDE.md`](CLAUDE.md) / [`AGENTS.md`](AGENTS.md) first.
- Humans: read the
  [Human Review Guide](docs/workflow/HUMAN_REVIEW_GUIDE.md) — you can control
  the project with short phrases from your phone.
- The full lifecycle: [`docs/workflow/AGENT_WORKFLOW.md`](docs/workflow/AGENT_WORKFLOW.md).
- Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Claude Code commands

- `/status` — short current-state report.
- `/spec-report` — state of all specs and the roadmap.
- `/drift-check` — detect documentation drift and conflicts.
- `/handoff` — leave a clear state for the next session.

## Project stack

Not yet defined — there is no application code. When code is added, the build
and test commands will be recorded in `CONTRIBUTING.md`, `CLAUDE.md`, and a CI
workflow. Build commands are intentionally not invented here.

## Manual setup still needed

Branch protection, required checks, and security features are **not** configured
by the bootstrap. See
[`docs/workflow/REPOSITORY_ADMIN_SETUP.md`](docs/workflow/REPOSITORY_ADMIN_SETUP.md).
