# Spec Report

> **This report is derived documentation. It must not introduce new
> requirements. If this report conflicts with an approved spec, the approved
> spec wins.**

Reports may be updated by agents when useful, but they must not become the
authoritative source of project truth. Regenerate this with `/spec-report`.

_Last updated: 2026-08-04._

```
Spec report

Draft:               none
In review:           none
Approved:            none
In implementation:   SPEC-001; SPEC-002; SPEC-003; SPEC-004; SPEC-005; SPEC-006; SPEC-007
Implemented:         none
Needs human decision: none
Missing verification: none identified
Potential blockers:   related PR references and merged-delivery evidence are absent for every spec
```

## Roadmap snapshot

- **SPEC-001 — F1 Data Analysis Charting Framework:** In Implementation, one
  amendment, no unresolved decisions, and all trace rows implemented.
- **SPEC-002 — V2 Plugin, Preview, and Configuration Workbench:** In
  Implementation, one amendment. The plugin, preview, run-history, and package
  contracts are traced to current surfaces. Export draft/integrity behavior and
  refreshed preview performance/scale evidence are complete.
- **SPEC-003 — V2 Tailwind UI System and Application Rebuild:** In
  Implementation, three amendments. Responsive, lightbox/review interaction,
  keyboard, package-scale, and Markdown safety evidence are complete.
- **SPEC-004 — V2 Analysis Workbench and Staged Run Pipeline:** In
  Implementation, one amendment. Backend, frontend, persistence, snapshots,
  generation, review, and export are traced; Review/Export interaction evidence
  is complete.
- **SPEC-005 — V2 Chart Templates and Parameter Presets:** In Implementation,
  one amendment, no unresolved decisions, and a populated verification matrix.
- **SPEC-006 — Analyst-Grade Chart Parameters and Renderer Semantics:** In
  Implementation, one amendment, no unresolved decisions, and a populated
  verification matrix.
- **SPEC-007 — Visual Track Map Range Selection and Race Playback Explorer:**
  In Implementation, 24 amendments, no unresolved decisions, and a populated
  verification matrix. All 40 trace rows are implemented or intentionally
  deferred by an approved amendment.

## SPEC-007 effective amendment state

AMEND-001 through AMEND-004 refine telemetry selection and the chart editor,
including explicit driver-selection semantics, loading feedback, preview-first
layout, and consolidated chart-option controls. AMEND-005 through AMEND-008
establish lap-first manual playback, shared time interpolation, and readable
map-marker labels and hit areas.

AMEND-009 through AMEND-015 build and refine the race timing tower, remove the
premature chart-range handoff, improve timing provenance and density, and make
single-driver comparison consistently relative. AMEND-016 simplifies the Laps
view and tyre-age presentation. AMEND-017's automatic playback experiment is
explicitly superseded by AMEND-018, so manual Lap/Time scrubbing is the current
approved behavior.

AMEND-019 through AMEND-024 complete real-session Minis data, selected-driver
track overlays, the shared performance palette, multi-driver timing and sector
comparison, the darker slower-state color, and deterministic equal-driver
median session geometry with smooth seam closure and legacy snapshot rebuild.
AMEND-023 supersedes only the slower-state color introduced by AMEND-021;
AMEND-024 is the latest amendment.

## Cross-spec reconciliation

Traceability is reconciled at requirement level. SPEC-001, SPEC-005, SPEC-006,
and SPEC-007 have complete implementation/verification mappings, subject to the
intentional SPEC-007 deferral noted above.

AMEND-001 in SPEC-002 and AMEND-003 in SPEC-003 reconcile their original peer
Package Preview/Configuration Workbench page model with SPEC-004's approved
Analysis-first navigation. The surviving package review behavior belongs in the
Analysis Workbench Review/Export workflow; plugin, run-history, notification,
security, and reusable UI contracts remain in force.

Formal lifecycle state is deliberately separate from requirement delivery.
Every spec remains in the approved folder with status `In Implementation`
because `related_prs` is empty and merged-delivery evidence has not been
recorded. No spec should move to `Implemented` until that gate is satisfied.
