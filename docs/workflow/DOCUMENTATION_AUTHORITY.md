# Documentation Authority

This document prevents documentation drift by defining which documents are
allowed to introduce which kinds of truth. When two documents disagree, this
hierarchy decides who wins.

## Categories

### Authoritative documents

The only place new truth may be introduced.

- **Specs** (`docs/specs/**`) — the only place **requirements** may be
  introduced.
- **ADRs** (Architecture Decision Records) — the only place **architecture
  decisions** may be introduced, **if** an ADR system exists. This repository
  has no ADR system yet, so architecture decisions are recorded in specs until
  one is added.
- **Glossary** — the only place **terms** may be authoritatively defined, **if**
  a glossary exists. This repository has no glossary yet.

### Derived documents

Summarize or reorganize authoritative content. Must link back and must not
introduce new truth.

- `docs/SPEC_INDEX.md`
- `README.md`
- `CONTRIBUTING.md`
- Anything under `docs/reports/`

### Generated reports

Machine- or agent-produced summaries. Snapshot in time. Never authoritative.

- `docs/reports/PROJECT_STATUS.md`
- `docs/reports/SPEC_REPORT.md`
- `docs/reports/DRIFT_REPORT.md`

### Historical documents

Kept for the record, not for current truth.

- Archived, superseded, and rejected specs under `docs/specs/archived/`.

## Rules

1. **Requirements may only be introduced in specs.** Not in reports, READMEs,
   issues, code comments, or commit messages.
2. **Architecture decisions** may only be introduced in ADRs if the ADR system
   exists, otherwise in specs.
3. **Terms** may only be authoritatively defined in the glossary if one exists.
4. **Reports may summarize but must not introduce new requirements.**
5. **README may summarize but must link to authoritative documents.**
6. **Approved specs may not be behaviorally changed without an amendment**
   (see the Spec Amendments section of the spec template).
7. **Superseded specs must link to their replacement** via the `superseded_by`
   frontmatter field, and the replacement must list the old one in `supersedes`.
8. **If two authoritative documents conflict, the agent must stop and ask the
   human to decide.** Do not silently pick one.

## Conflict resolution order

When documents disagree:

1. Approved spec (most recent, accounting for supersession + amendments).
2. Other authoritative documents.
3. Derived documents.
4. Generated reports.

A lower tier never overrides a higher tier. If two documents at the same tier
conflict, stop and escalate to the human.
