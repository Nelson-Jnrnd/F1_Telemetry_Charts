# Specification Index

This is the catalog of all specifications in this repository. It is **derived**
documentation: it summarizes specs but does not introduce requirements. If this
index conflicts with a spec, the spec wins.

Specs live under `docs/specs/` and move between lifecycle folders as their
status changes:

- `docs/specs/active/` — Draft and In Review specs being worked on.
- `docs/specs/approved/` — Approved specs, ready to implement.
- `docs/specs/implemented/` — Implemented specs.
- `docs/specs/archived/` — Archived, Superseded, or Rejected specs.

## How to add a spec

1. Copy `docs/specs/SPEC_TEMPLATE.md` to
   `docs/specs/active/SPEC-XXX-short-slug.md`.
2. Pick the next unused `SPEC-XXX` id.
3. Fill in the frontmatter and requirements.
4. Add a row to the table below.

## Spec statuses

`Draft` → `In Review` → `Approved` → `In Implementation` → `Implemented`.
Terminal alternatives: `Superseded`, `Archived`, `Rejected`.

## Index

| Spec ID | Title | Status | Owner | Related issue | Related PRs | Location |
| ------- | ----- | ------ | ----- | ------------- | ----------- | -------- |
| SPEC-001 | F1 Data Analysis Charting Framework | In Implementation | Nelson Jeanrenaud | | [] | `docs/specs/approved/SPEC-001-f1-analysis-framework.md` |
| SPEC-002 | V2 Plugin, Preview, and Configuration Workbench | In Implementation | Nelson Jeanrenaud | | [] | `docs/specs/approved/SPEC-002-v2-plugin-preview-workbench.md` |
| SPEC-003 | V2 Tailwind UI System and Application Rebuild | In Implementation | Nelson Jeanrenaud | | [] | `docs/specs/approved/SPEC-003-v2-tailwind-ui-system.md` |
| SPEC-004 | V2 Analysis Workbench and Staged Run Pipeline | In Implementation | Nelson Jeanrenaud | | [] | `docs/specs/approved/SPEC-004-v2-analysis-workbench-pipeline.md` |
| SPEC-005 | V2 Chart Templates and Parameter Presets | In Implementation | Nelson Jeanrenaud | | [] | `docs/specs/approved/SPEC-005-v2-chart-templates-and-presets.md` |
| SPEC-006 | Analyst-Grade Chart Parameters and Renderer Semantics | In Implementation | Nelson Jeanrenaud | | [] | `docs/specs/approved/SPEC-006-analyst-grade-chart-parameters.md` |
| SPEC-007 | Visual Track Map Range Selection and Race Playback Explorer | In Implementation | Nelson Jeanrenaud | | [] | `docs/specs/approved/SPEC-007-track-map-range-and-race-playback.md` |

Requirement-level implementation and verification evidence was reconciled on
2026-08-04. All seven specs remain formally `In Implementation` because none
has a related PR/merged-delivery reference; see `docs/reports/SPEC_REPORT.md`
for current lifecycle status.

> Keep this table in sync with the frontmatter of each spec. `/spec-report` and
> `scripts/validate_drift.py` help detect drift between this index and the
> actual spec files.
