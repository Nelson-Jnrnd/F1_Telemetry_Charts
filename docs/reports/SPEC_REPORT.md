# Spec Report

> **This report is derived documentation. It must not introduce new
> requirements. If this report conflicts with an approved spec, the approved
> spec wins.**

Reports may be updated by agents when useful, but they must not become the
authoritative source of project truth. Regenerate this with `/spec-report`.

_Last updated: 2026-07-23._

```
Spec report

Draft:               none
In review:           none
Approved:            none
In implementation:   SPEC-001 F1 Data Analysis Charting Framework (AMEND-001); SPEC-002 V2 Plugin, Preview, and Configuration Workbench; SPEC-003 V2 Tailwind UI System and Application Rebuild; SPEC-004 V2 Analysis Workbench and Staged Run Pipeline; SPEC-005 V2 Chart Templates and Parameter Presets; SPEC-006 Analyst-Grade Chart Parameters and Renderer Semantics
Implemented:         none
Needs human decision: none
Missing verification: SPEC-002/SPEC-003/SPEC-004 browser visual evidence pending
Potential blockers:   SPEC-004 browser visual evidence pending
```

SPEC-001 is in implementation. The MVP and V1 slice sets are complete. SPEC-002
is approved and in implementation. Package preview, plugin discovery,
configuration workbench API, run history, and the React/Vite local UI shell have
initial implementation evidence. Browser visual verification remains pending
because the Codex browser connector failed to initialize.

SPEC-003 is approved and in implementation as a dedicated UI spec depending on
SPEC-002. It defines the Tailwind/Radix frontend rebuild, reusable components,
package preview, workbench, plugins, and run history UI behavior. Initial
implementation is complete with frontend typecheck/build and targeted API tests
passing; browser visual evidence remains pending because the Codex browser
connector failed to initialize.

SPEC-004 is approved and in implementation. It addresses the product model
change from package-first generation to an Analysis Workbench. It defines
Analysis as the top-level user object, with sessions, deterministic JSON dataset
snapshots, chart instances, editable recipe parameters, reusable local/global
presets, review/export state, and save/load behavior. It records `chart
template` as the preferred future user-facing term while deferring the rename.
Initial backend, API, LLM contract, and frontend Workbench implementation is in
place with tests, frontend build, and snapshot-regeneration benchmark passing.
The primary UI is now Analysis-first, with exported package inspection embedded
inside the Export workflow. Browser visual verification remains blocked by the
in-app browser connector initialization failure.

SPEC-005 is approved and in implementation. It addresses the chart recipe
bottleneck by making `Chart template` the user-facing concept, preserving
internal `recipe_id` compatibility, defining parameter-only template editing,
Analysis and global parameter presets, built-in plus validated plugin template
sources, and LLM-safe template inspection/parameter updates with no code
authoring and no pre-generation preview. Initial implementation adds template
catalog payloads/endpoints, typed parameter schemas and controls, preset CRUD,
LLM template aliases, and behavior-changing parameters for `telemetry_trace`,
`lap_time_delta`, `tyre_strategy`, and `position_progression`.

SPEC-006 implementation is complete but remains in the approved/in
implementation lifecycle folder until a related PR reference exists. It records
FastF1 3.8.3 as the target, defaults new Analysis sessions to all-session
driver loading, saves new chart parameters in normalized sections while
preserving legacy flat inputs, exposes Basic/Advanced and dependency metadata,
provides diagnostics/effective configuration, implements lap-validity,
track-status, box-lap, missing-series, telemetry-gap, and chart-specific
policies, adds analyst presets, and extends renderer primitives for step lines,
horizontal stint bars, vertical markers, shaded regions, and axis inversion.
