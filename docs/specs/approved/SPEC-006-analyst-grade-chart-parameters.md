---
doc_type: spec
spec_id: SPEC-006
title: Analyst-Grade Chart Parameters and Renderer Semantics
status: In Implementation
owner: Nelson Jeanrenaud
related_issue:
related_prs: []
affected_components:
  - chart_templates
  - parameter_schema
  - chart_generation
  - chart_rendering
  - analysis_workspace
  - local_preview_ui
  - llm_contract
  - data_gateway
affected_interfaces:
  - Analysis Workbench UI
  - FastAPI local UI API
  - LLM contract
  - Analysis directory format
  - Built-in chart template schemas
  - Renderer-independent ChartSpec
  - Matplotlib renderer
supersedes: []
superseded_by:
depends_on:
  - SPEC-004
  - SPEC-005
conflicts_with: []
last_verified_at: 2026-07-23
---

# SPEC-006: Analyst-Grade Chart Parameters and Renderer Semantics

## Summary

This spec turns the broad chart-parameter review from 2026-07-22 into an
implementation-ready product contract. It replaces the minimum SPEC-005
parameter set with an analyst-grade model that separates data selection,
filtering, analytical transformations, ordering, visual styling, layout,
annotations, diagnostics, and saved effective configuration. It also requires
renderer semantics that can actually express the requested chart types instead
of rendering every template as a generic line chart.

## Context

SPEC-005 introduced chart templates, parameter schemas, parameter presets, and
template terminology while preserving internal `recipe_id` compatibility. That
implementation deliberately satisfied the minimum approved scope: templates
became parameterized, but their parameters are still shallow and some
parameters affect metadata more than the rendered chart.

On 2026-07-22, the human owner provided a full functional and user-interface
review titled "FastF1 Analysis Chart Parameters". The review says the current
inventory is a useful functional basis but is not suitable as a stable public
configuration contract. It identifies mixed concerns, imprecise FastF1
semantics, weak chart-specific rendering, insufficient dependency-aware UI
behavior, and missing reproducibility diagnostics.

This spec treats SPEC-005 as the plumbing baseline and defines the hardening
pass required before the built-in chart template parameter model should be
considered stable.

## Problem statement

The current chart templates do not yet behave like serious Formula 1 analysis
tools. They expose too few parameters, mix unrelated concerns in flat fields,
do not load or select full-field data well, use generic renderer primitives for
chart types that need specialized visuals, and fail to communicate active
filters and calculation semantics. This can produce charts that are technically
generated but analytically misleading.

## Goals

- Separate parameter concerns into normalized sections for chart, selection,
  filters, analysis, presentation, diagnostics, and effective configuration.
- Support Basic and Advanced configuration modes.
- Make parameter visibility, enabled state, required state, and validation
  dependency-aware.
- Define shared driver selection and driver ordering schemas.
- Replace broad pit-lap and incomplete-lap booleans with explicit policies.
- Add track-status filtering with clear Safety Car, VSC, red flag, and match
  semantics.
- Restrict missing-data interpolation to eligible continuous telemetry
  channels.
- Define analyst-safe telemetry trace, lap-time delta, tyre strategy, and
  position progression parameter contracts.
- Add renderer-independent chart primitives needed by the built-in templates.
- Ensure every visible analytical parameter affects generated chart content,
  rendered artifacts, metadata, or validation diagnostics.
- Serialize requested and effective configurations for reproducibility.

## Non-goals

- This spec does not add user-authored Python chart logic.
- This spec does not remove internal `recipe_id` compatibility.
- This spec does not require live network data in tests.
- This spec does not require every possible FastF1 channel to be implemented;
  unsupported channels must be unavailable or blocked rather than silently
  accepted.
- This spec does not require a full interactive notebook environment.
- This spec does not redefine the trusted plugin execution model from SPEC-002.

## Users or actors

- Human analyst: creates reproducible, meaningful F1 analysis charts.
- Human writer: prepares presentation/report charts without hidden analytical
  ambiguity.
- LLM agent: inspects templates and proposes valid parameter changes without
  authoring code.
- FastAPI backend: validates parameters, applies filters, computes effective
  configuration, and returns diagnostics.
- Analysis Workbench frontend: renders Basic/Advanced forms with dependencies
  and active-filter summaries.
- Renderer: renders chart-specific visuals from structured `ChartSpec`
  primitives.

## Terminology

- **Requested configuration:** Values explicitly chosen by the user, preset, or
  LLM.
- **Effective configuration:** The resolved configuration after defaults,
  automatic values, data availability, dependencies, and fallbacks are applied.
- **Basic mode:** Minimal controls required for a valid useful chart.
- **Advanced mode:** Full analytical, filtering, styling, axis, annotation, and
  diagnostic controls.
- **Box lap:** A lap involving pit entry, pit exit, or both.
- **Lap validity:** Structured quality classification using timing
  availability, deleted/generated status, accuracy, and sector completeness.
- **Track-status filter:** Filtering based on Safety Car, VSC, red flag, green
  flag, yellow flag, or custom status codes and match semantics.

## Functional requirements

### REQ-001: Normalized parameter sections

- **Statement:** Built-in chart template schemas must be organized into
  functional sections instead of one flat list: `chart`, `selection`,
  `filters`, `analysis`, `presentation`, `diagnostics`, and `effective`.
- **Rationale:** The review identified that data selection, filtering,
  transformations, ordering, styling, layout, and annotations are currently
  mixed together, making the contract hard to understand and unsafe to save.
- **Acceptance criteria:** A chart configuration payload can distinguish
  requested values from effective values and can serialize every section; no
  built-in template stores unrelated concerns under one ambiguous field.
- **Verification method:** Model/unit tests and serialized fixture inspection.
- **Evidence location:** To be filled during implementation.

### REQ-002: Basic and Advanced modes

- **Statement:** The Analysis Workbench must provide Basic and Advanced
  configuration modes for built-in chart templates.
- **Rationale:** Analysts need a simple useful graph path without losing access
  to precision controls.
- **Acceptance criteria:** Basic mode shows only required/commonly used controls
  for the selected template; Advanced mode exposes lap-quality rules,
  track-status matching, resampling, smoothing, outliers, styling, axis limits,
  interpolation limits, annotations, and calculation policies.
- **Verification method:** Frontend component tests or manual UI checklist plus
  schema visibility tests.
- **Evidence location:** To be filled during implementation.

### REQ-003: Dependency-aware controls

- **Statement:** Parameter schemas must support `visible_when`, `enabled_when`,
  `required_when`, allowed-values dependencies, and inactive-value retention.
- **Rationale:** Controls such as `reference_driver`,
  `rolling_window_laps`, `teams`, smoothing, and custom ordering should only
  affect the chart when their parent mode requires them.
- **Acceptance criteria:** Hidden or disabled controls preserve previous values
  but do not affect generated output while inactive; backend validation applies
  the same dependency rules as the UI.
- **Verification method:** Backend schema validation tests and frontend
  interaction tests.
- **Evidence location:** To be filled during implementation.

### REQ-004: Shared driver selection

- **Statement:** Built-in templates must use a shared driver selection schema
  with `driver_selection_mode`, `drivers`, `teams`, `top_n`, and
  `driver_limit`.
- **Rationale:** Selection scope must be separate from visual limiting and must
  avoid exposing implementation terms such as `all_loaded` as the analyst
  concept.
- **Acceptance criteria:** Supported modes are `all_session`, `selected`,
  `top_n`, and `teams`; `drivers`, `teams`, and `top_n` are required only for
  their modes; `driver_limit` never removes highlighted or reference drivers.
- **Verification method:** Unit/API tests with all modes and validation errors.
- **Evidence location:** To be filled during implementation.

### REQ-005: Full-session driver availability

- **Statement:** The Analysis workflow must support selecting all session
  drivers for built-in templates, not only the two-driver default currently
  seeded in the UI.
- **Rationale:** Full-field analysis is a baseline F1 workflow. Templates cannot
  show all drivers if the Analysis session only loaded two drivers.
- **Acceptance criteria:** A user can create an Analysis session that loads all
  available drivers from the session provider or fixture; templates using
  `driver_selection_mode: all_session` include that full available field unless
  explicitly limited.
- **Verification method:** API/service tests and UI/manual test with a
  full-field fixture or mocked provider.
- **Evidence location:** To be filled during implementation.

### REQ-006: Shared driver ordering

- **Statement:** Built-in templates must use a separate driver ordering schema:
  `driver_order` and `custom_driver_order`.
- **Rationale:** Ordering controls legend order, drawing order, table order, and
  vertical layout; it must not change which drivers are selected.
- **Acceptance criteria:** Supported orders are `classification`, `fastest_lap`,
  `team`, `grid`, `selection_order`, and `custom`; custom order validation
  appends missing selected drivers with a warning and rejects duplicates.
- **Verification method:** Unit tests and metadata assertions.
- **Evidence location:** To be filled during implementation.

### REQ-007: Shared lap range

- **Statement:** Lap range must use inclusive `start` and `end` bounds with
  automatic all-lap defaults and zero-result warnings.
- **Rationale:** Analysts need reproducible lap filtering while still quickly
  selecting whole-race, opening-phase, stint, and final-lap ranges.
- **Acceptance criteria:** The UI presents precise numeric controls plus range
  shortcuts; backend validates `start <= end`; metadata records effective lap
  range and per-driver coverage warnings.
- **Verification method:** API tests and frontend/manual checks.
- **Evidence location:** To be filled during implementation.

### REQ-008: Box-lap policy

- **Statement:** Built-in templates must replace overlapping pit-lap booleans
  with `box_lap_policy`.
- **Rationale:** In-laps and out-laps have different analytical meanings. One
  `include_pit_laps` boolean is not precise enough.
- **Acceptance criteria:** Supported policies are `include_all`,
  `exclude_in_laps`, `exclude_out_laps`, `exclude_in_and_out_laps`,
  `only_in_laps`, and `only_out_laps`; defaults are chart-specific.
- **Verification method:** Unit tests using laps with pit-in and pit-out flags.
- **Evidence location:** To be filled during implementation.

### REQ-009: Lap validity configuration

- **Statement:** Built-in lap-based templates must replace
  `include_incomplete_laps` with structured `lap_validity` settings.
- **Rationale:** Deleted laps, generated laps, inaccurate laps, missing lap
  times, and incomplete sectors are different conditions and must not be hidden
  behind one boolean.
- **Acceptance criteria:** `lap_validity` includes `require_lap_time`,
  `deleted_laps`, `generated_laps`, `accuracy_filter`, and
  `require_complete_sectors`; exclusion counts and reasons appear in metadata.
- **Verification method:** Model validation tests and fixture tests with
  synthetic lap-quality flags.
- **Evidence location:** To be filled during implementation.

### REQ-010: Track-status filtering

- **Statement:** Built-in templates must replace broad `session_phase` values
  with a dedicated `track_status_filter`.
- **Rationale:** Safety Car, VSC, red flags, yellows, and green running need
  explicit categories and match semantics.
- **Acceptance criteria:** Supported modes include `all`, `green_only`,
  `green_or_yellow`, `exclude_sc`, `exclude_sc_and_vsc`, and `custom`;
  `track_status_match` supports `any_overlap`, `full_lap`, and
  `status_at_lap_end`; effective included/excluded status codes are recorded.
- **Verification method:** Unit tests with synthetic track-status timelines.
- **Evidence location:** To be filled during implementation.

### REQ-011: Missing-data policies

- **Statement:** Built-in templates must split missing-series behavior from
  telemetry-gap handling.
- **Rationale:** Interpolation is not a valid generic response to missing data;
  it is only appropriate for eligible continuous telemetry channels under
  explicit limits.
- **Acceptance criteria:** `missing_series_policy` supports `error`,
  `warn_skip`, and `silent_skip`; telemetry templates support
  `telemetry_gap_policy` of `preserve`, `interpolate_continuous`, or `resample`
  with `maximum_interpolation_gap_ms`; interpolation is disabled for
  categorical/state-like metrics.
- **Verification method:** Unit tests for continuous and categorical telemetry
  channels.
- **Evidence location:** To be filled during implementation.

### REQ-012: Shared style configuration

- **Statement:** Built-in templates must use a unified style schema for colors,
  series styles, highlighted drivers, and highlight styles.
- **Rationale:** Teammates can share colors; analysts need line style, width,
  marker, opacity, z-order, and temporary highlight controls.
- **Acceptance criteria:** `color_source`, `series_colors`, `series_styles`,
  `highlight_drivers`, and `highlight_style` are supported; team colors remain
  automatic unless overridden.
- **Verification method:** Renderer metadata and visual artifact tests.
- **Evidence location:** To be filled during implementation.

### REQ-013: Shared legend, axis, density, and annotations

- **Statement:** Built-in templates must support shared presentation controls
  for legend visibility/position/grouping/columns, grid visibility, auto/manual
  axis ranges, output density, and structured annotations.
- **Rationale:** Presentation and report outputs need reliable display controls
  without conflating them with analytical calculations.
- **Acceptance criteria:** Automatic values are represented through explicit
  modes rather than undocumented null UI values; active annotations are recorded
  in metadata.
- **Verification method:** Frontend tests, renderer tests, and metadata
  assertions.
- **Evidence location:** To be filled during implementation.

### REQ-014: Telemetry trace contract

- **Statement:** The telemetry trace template must support metrics, source,
  lap selection, trace range, x-axis mode, layout, value transform, reference
  driver/lap, alignment, resampling, smoothing, markers, and metric-specific
  render modes.
- **Rationale:** Telemetry comparison requires explicit FastF1 channel
  semantics and should not pretend that all metrics can use the same transform
  and rendering.
- **Acceptance criteria:** Telemetry-specific schema includes metrics such as
  speed, throttle, brake, gear, RPM when available, and DRS when available;
  smoothing and interpolation are disabled for brake, gear, and DRS; corner
  distance is treated as annotation/alignment, not a separate x-axis.
- **Verification method:** Unit tests against fixture telemetry and schema
  dependency tests.
- **Evidence location:** To be filled during implementation.

### REQ-015: Lap-time delta contract

- **Statement:** The lap-time delta template must support explicit baseline,
  lap alignment, reference-lap behavior, delta mode, rolling window,
  lap-time/sector source, shared filtering controls, zero line, fastest-lap
  markers, sorting, symmetric axis, and outlier handling.
- **Rationale:** Cumulative filtered lap-time deltas must not be mistaken for
  actual race gaps, and sector/pacing calculations need clear formulas.
- **Acceptance criteria:** Cumulative mode is named
  `cumulative_filtered_pace_delta`; axis labels and metadata state the formula
  and sign convention; sector mode requires complete sector data.
- **Verification method:** Formula unit tests and generated metadata
  assertions.
- **Evidence location:** To be filled during implementation.

### REQ-016: Tyre strategy contract

- **Statement:** The tyre strategy template must support stint-oriented layouts,
  compound color mapping, pit anchoring, pit labels, stint labels, overlays,
  team grouping, identical-strategy collapse, sorting, minimum stint length,
  unknown-compound policy, tyre-life/fresh-used information, red flag periods,
  and non-pit compound changes.
- **Rationale:** A numeric compound-index line is not an analyst-grade tyre
  strategy chart.
- **Acceptance criteria:** Default layout is `stint_bars`; unknown compounds
  use one `unknown_compound_policy`; pit markers and labels render visually
  where enabled; metadata records stint source and hidden/filtered stint counts.
- **Verification method:** Renderer tests with synthetic stint data and fixture
  metadata tests.
- **Evidence location:** To be filled during implementation.

### REQ-017: Position progression contract

- **Statement:** The position progression template must use lap-end running
  position for progression and must support final-position source, axis
  inversion, retired drivers, pit markers, inferred position-event markers,
  SC/VSC/red-flag periods, start/finish labels, position-change highlighting,
  line mode, rank-delta mode, baseline mode, grid/final labels, axis range, and
  retirement-line policy.
- **Rationale:** Classified final result is not a lap-by-lap progression source,
  and inferred overtakes must not be presented as confirmed overtakes.
- **Acceptance criteria:** `classified_position` is not offered as a progression
  source; `invert_position_axis` changes rendering; inferred event markers are
  labelled as heuristic; retired drivers never continue with a solid active
  race line after retirement.
- **Verification method:** Unit tests, renderer tests, and UI dependency tests.
- **Evidence location:** To be filled during implementation.

### REQ-018: Renderer-specific chart primitives

- **Statement:** `ChartSpec` and the renderer must support primitives beyond
  generic line series, including step lines, horizontal stint bars, vertical
  markers, shaded periods, labels, annotations, style attributes, axis
  inversion, and optional overlays.
- **Rationale:** Tyre strategy, pit markers, position inversion, and track
  status periods cannot be implemented correctly with a single generic
  `axis.plot` loop.
- **Acceptance criteria:** Every built-in template parameter that claims visual
  behavior is represented by a renderer primitive and verified in metadata or
  rendered artifact tests.
- **Verification method:** Renderer unit tests and image/metadata regression
  tests.
- **Evidence location:** To be filled during implementation.

### REQ-019: Active-filter summary

- **Statement:** The UI and exports must show a compact active-filter summary
  for each chart.
- **Rationale:** Analysts need immediate visibility into selected drivers,
  laps, box-lap handling, track-status filters, lap-quality exclusions, and
  transformations.
- **Acceptance criteria:** The summary appears in the Chart Editor and exported
  metadata; it includes exclusion counts when available.
- **Verification method:** Frontend tests and metadata assertions.
- **Evidence location:** To be filled during implementation.

### REQ-020: Warnings and errors

- **Statement:** The backend must distinguish warnings from blocking errors for
  chart parameter resolution and generation.
- **Rationale:** Missing drivers, heavy filtering, interpolation, inferred
  events, and crowded charts should warn; no remaining data, invalid ranges, and
  missing required references must block.
- **Acceptance criteria:** Chart generation returns structured warnings and
  field-specific errors; the UI displays warnings without losing the current
  draft.
- **Verification method:** API tests and frontend/manual checks.
- **Evidence location:** To be filled during implementation.

### REQ-021: Reproducibility metadata

- **Statement:** Every generated chart must serialize requested parameters,
  effective parameters, FastF1/package version, session identity, data-load
  options, included drivers/laps, exclusion counts, reference details,
  resampling/smoothing details, and warnings.
- **Rationale:** Charts used in reports must be reproducible and auditable.
- **Acceptance criteria:** Generated metadata contains a complete
  `requested_configuration`, `effective_configuration`, and `diagnostics`
  section.
- **Verification method:** Artifact metadata tests.
- **Evidence location:** To be filled during implementation.

### REQ-022: Analyst-oriented presets

- **Statement:** Built-in global presets must be provided for common analyst
  workflows.
- **Rationale:** Presets should make the richer parameter model usable without
  forcing analysts through every Advanced control.
- **Acceptance criteria:** Presets include fastest-lap telemetry comparison,
  driver-input comparison, clean race pace, sector comparison, tyre strategy
  overview, position progression, race gain/loss, presentation export, and
  dense engineering report; presets remain editable after apply.
- **Verification method:** Preset listing tests and manual UI check.
- **Evidence location:** To be filled during implementation.

### REQ-023: Reset behavior

- **Statement:** The UI must support Reset section, Reset chart, Restore preset,
  and Clear custom overrides actions without mutating unrelated hidden advanced
  settings.
- **Rationale:** Rich parameter forms need safe recovery paths.
- **Acceptance criteria:** Reset actions are scoped and deterministic; hidden
  values are retained unless the selected reset operation explicitly clears
  them.
- **Verification method:** Frontend interaction tests.
- **Evidence location:** To be filled during implementation.

## Non-functional requirements

### NFR-001: Local-first performance

- **Statement:** Basic parameter edits and preview/regeneration must use
  existing Analysis snapshots where possible and must not reload FastF1 session
  data.
- **Rationale:** Rich controls are unusable if each change re-fetches or
  reloads the session.
- **Acceptance criteria:** Parameter changes reuse loaded snapshots; expensive
  recalculation is debounced or explicitly applied.
- **Verification method:** Service tests and benchmark.
- **Evidence location:** To be filled during implementation.

### NFR-002: UI scalability

- **Statement:** Full-field driver selection and dense chart forms must remain
  usable on supported desktop and tablet layouts.
- **Rationale:** All-session F1 charts can involve about 20 drivers and many
  Advanced controls.
- **Acceptance criteria:** Driver multi-selects are searchable; long forms are
  grouped; text and controls do not overlap.
- **Verification method:** Frontend build, component tests, and screenshot/manual
  QA.
- **Evidence location:** To be filled during implementation.

### NFR-003: Versioned stability

- **Statement:** The new parameter schema must include explicit schema version
  and migration behavior for renamed SPEC-005 parameters.
- **Rationale:** Presets and saved chart instances must survive the parameter
  contract hardening.
- **Acceptance criteria:** Existing SPEC-005 Analysis files load; renamed
  parameters are migrated or rejected with actionable diagnostics.
- **Verification method:** Migration fixture tests.
- **Evidence location:** To be filled during implementation.

## Security and privacy considerations

### SEC-001: No code authoring

- **Statement:** Rich parameter configuration must not introduce UI or LLM
  paths for authoring Python chart logic.
- **Rationale:** SPEC-005 intentionally limits users and LLM agents to validated
  parameter changes.
- **Acceptance criteria:** LLM and UI APIs expose only structured parameter
  operations; plugin code paths remain governed by SPEC-002.
- **Verification method:** API inspection and contract tests.
- **Evidence location:** To be filled during implementation.

## Data model impact

### DATA-001: Normalized configuration object

- **Statement:** Chart instance parameters must support the normalized object
  structure shown in this spec while preserving compatibility with legacy flat
  SPEC-005 fields through migration.
- **Rationale:** The saved public contract should not be a flat bag of mixed
  keys.
- **Acceptance criteria:** New chart instances save normalized configuration;
  legacy instances can be opened and either migrated or shown with clear
  diagnostics.
- **Verification method:** Model tests and saved Analysis fixture tests.
- **Evidence location:** To be filled during implementation.

### DATA-002: Effective configuration

- **Statement:** Chart generation must compute and save an effective
  configuration for every generated chart.
- **Rationale:** Automatic defaults, inactive values, full-field driver
  resolution, and filtering decisions must be auditable.
- **Acceptance criteria:** Effective configuration is deterministic for the same
  Analysis snapshot and requested configuration.
- **Verification method:** Snapshot/golden metadata tests.
- **Evidence location:** To be filled during implementation.

## API impact

### API-001: Rich schema payloads

- **Statement:** Template catalog and schema APIs must expose sections,
  dependency rules, Basic/Advanced mode visibility, defaults, allowed values,
  warnings, and validation constraints.
- **Rationale:** The frontend and LLM contract need the same authoritative
  parameter model.
- **Acceptance criteria:** API responses contain enough structured metadata to
  render the dependency-aware form without hardcoded per-template UI logic.
- **Verification method:** API schema tests.
- **Evidence location:** To be filled during implementation.

### API-002: Validation and diagnostics endpoint

- **Statement:** The backend must expose a way to validate and resolve chart
  parameters before or during generation.
- **Rationale:** Users need warnings, active-filter summaries, and effective
  configuration before accepting or exporting charts.
- **Acceptance criteria:** API returns field-specific errors, non-blocking
  warnings, exclusion counts, and effective configuration.
- **Verification method:** API tests.
- **Evidence location:** To be filled during implementation.

## UI or UX impact

### UX-001: Dependency-aware form engine

- **Statement:** The Analysis Workbench must render template schemas through a
  dependency-aware form engine with section grouping, Basic/Advanced mode, and
  appropriate control types.
- **Rationale:** A flat form with every parameter visible is not acceptable for
  this parameter set.
- **Acceptance criteria:** Controls follow the vocabulary from the attached
  review: toggles, segmented controls, combo boxes, searchable multi-selects,
  range controls with numeric inputs, steppers, reorderable lists, series
  tables, color pickers, auto/manual controls, and repeating annotation lists
  where applicable.
- **Verification method:** Frontend tests and manual checklist.
- **Evidence location:** To be filled during implementation.

### UX-002: Live or immediate preview

- **Statement:** Meaningful parameter changes should update a chart preview
  immediately where feasible, with debounce or explicit Apply for expensive
  changes.
- **Rationale:** The review requests immediate visibility into parameter
  effects. SPEC-005 intentionally excluded pre-generation preview, so this is a
  deliberate follow-up scope.
- **Acceptance criteria:** The UI shows which configuration is currently
  rendered; while recalculating, the previous chart remains visible with a
  loading state or stale marker.
- **Verification method:** Manual UI check or Playwright test.
- **Evidence location:** To be filled during implementation.

### UX-003: Active-filter and warning display

- **Statement:** Chart Editor must show active filters, warnings, exclusion
  counts, and blocking errors in concise analyst language.
- **Rationale:** Visual convenience must not hide analytical meaning.
- **Acceptance criteria:** The user can see which data was included, excluded,
  transformed, interpolated, inferred, or automatically resolved.
- **Verification method:** Frontend tests and manual checklist.
- **Evidence location:** To be filled during implementation.

## Configuration impact

- New chart instances should save normalized parameters.
- Existing flat SPEC-005 parameters require migration:
  - `drivers` maps into `selection.drivers.drivers` with
    `driver_selection_mode: selected` when non-empty.
  - `lap_range` maps into `selection.laps.range`.
  - `series_colors` maps into `presentation.colors.overrides`.
  - `include_pit_laps` maps into chart-specific `box_lap_policy`.
  - `show_pit_markers` maps into annotation settings.
  - `invert_position_axis` maps into position presentation settings and must
    affect rendering.
- Presets must carry schema version and migration state.

## Error handling

- Invalid dependency: field-specific validation error.
- No drivers after selection/limit: blocking error.
- No laps after filters: blocking error with exclusion counts.
- Missing required reference driver/lap: blocking error.
- Unsupported metric transformation: blocking error.
- Interpolation requested for categorical telemetry: blocking error or disabled
  control.
- Filter removes many records but not all: warning.
- Inferred position events enabled: warning that events are heuristic.
- Cumulative filtered pace delta enabled: warning that it is not actual race
  gap.
- Visually crowded full-field chart: warning.

## Edge cases

- Full-field session loading with fixture data that contains only selected
  drivers.
- Reference driver excluded by selection, limit, or filter.
- Highlighted driver excluded by limit.
- Selected teams with missing team metadata.
- Lapped drivers and laps missing for part of a range.
- Pit-in and pit-out flags on the same lap.
- Deleted qualifying laps versus generated race laps.
- Red flags and restarted sessions.
- Retired drivers with no final recorded position.
- Unknown tyre compounds.
- Missing sector times when sector source is selected.
- Telemetry gaps across pit entry, pit exit, or session discontinuity.
- Existing SPEC-005 presets and charts with flat parameter keys.

## Acceptance criteria

- Built-in templates expose normalized, dependency-aware, versioned parameter
  schemas.
- Basic mode can create useful charts without Advanced controls.
- Advanced mode exposes the analyst controls requested in the review.
- Full-session driver selection is supported.
- Box-lap, lap-validity, track-status, and missing-data policies are explicit.
- Telemetry, lap delta, tyre strategy, and position progression have
  chart-specific parameter contracts and renderer behavior.
- Every analytical or visual parameter either changes output or is blocked.
- Generated metadata includes requested configuration, effective configuration,
  warnings, exclusion counts, and reproducibility information.
- Existing SPEC-005 Analysis files remain loadable through migration or clear
  diagnostics.

## Verification matrix

| Requirement ID | Acceptance criterion | Verification method | Test / command / manual check | Evidence location | PR reference |
| -------------- | -------------------- | ------------------- | ----------------------------- | ----------------- | ------------ |
| REQ-001 | Normalized sections serialize separately | model tests | TBD | TBD | |
| REQ-002 | Basic/Advanced modes work | UI/schema tests | TBD | TBD | |
| REQ-003 | Dependency rules enforced | backend/frontend tests | TBD | TBD | |
| REQ-004 | Driver selection modes validate | unit/API tests | TBD | TBD | |
| REQ-005 | All-session drivers can be loaded/selected | service/UI tests | TBD | TBD | |
| REQ-006 | Driver ordering is separate from selection | unit tests | TBD | TBD | |
| REQ-007 | Lap range is inclusive and validated | unit/API tests | TBD | TBD | |
| REQ-008 | Box-lap policy replaces booleans | unit tests | TBD | TBD | |
| REQ-009 | Lap validity reasons/counts recorded | unit tests | TBD | TBD | |
| REQ-010 | Track-status filtering works | unit/API tests | TBD | TBD | |
| REQ-011 | Missing-data policies are metric-safe | unit tests | TBD | TBD | |
| REQ-012 | Series styles/highlights render | renderer tests | TBD | TBD | |
| REQ-013 | Legend/axis/density/annotations work | renderer/UI tests | TBD | TBD | |
| REQ-014 | Telemetry contract implemented | recipe/schema tests | TBD | TBD | |
| REQ-015 | Lap delta contract implemented | recipe/schema tests | TBD | TBD | |
| REQ-016 | Tyre strategy contract implemented | recipe/renderer tests | TBD | TBD | |
| REQ-017 | Position contract implemented | recipe/renderer tests | TBD | TBD | |
| REQ-018 | ChartSpec renderer primitives support visuals | renderer tests | TBD | TBD | |
| REQ-019 | Active-filter summary shown/exported | UI/metadata tests | TBD | TBD | |
| REQ-020 | Warnings/errors are structured | API/UI tests | TBD | TBD | |
| REQ-021 | Reproducibility metadata complete | metadata tests | TBD | TBD | |
| REQ-022 | Analyst presets available | preset tests | TBD | TBD | |
| REQ-023 | Reset behavior scoped | UI tests | TBD | TBD | |
| NFR-001 | Snapshot reuse during edits | service/benchmark tests | TBD | TBD | |
| NFR-002 | UI scales to full field | screenshot/manual check | TBD | TBD | |
| NFR-003 | Schema version/migration works | migration tests | TBD | TBD | |
| SEC-001 | No code authoring added | API/contract inspection | TBD | TBD | |
| DATA-001 | Normalized configuration persisted | model tests | TBD | TBD | |
| DATA-002 | Effective configuration deterministic | metadata tests | TBD | TBD | |
| API-001 | Rich schema payloads available | API tests | TBD | TBD | |
| API-002 | Validation/diagnostics endpoint works | API tests | TBD | TBD | |
| UX-001 | Dependency-aware form engine works | frontend tests/manual check | TBD | TBD | |
| UX-002 | Preview/apply behavior works | UI tests/manual check | TBD | TBD | |
| UX-003 | Active filters/warnings visible | frontend tests/manual check | TBD | TBD | |

## Test plan

- Unit tests for shared selection, ordering, lap filtering, box-lap policy,
  lap validity, track-status matching, missing-data policy, and migration.
- Recipe tests for all built-in templates with synthetic data targeting edge
  cases from the review.
- Renderer tests for step lines, stint bars, annotations, shaded periods, axis
  inversion, highlights, labels, and overlays.
- API tests for rich schema payloads, validation/diagnostics, create/update,
  preset migration, and LLM inspection.
- Frontend tests or manual checks for Basic/Advanced mode, dependency rules,
  active-filter summary, reset behavior, and full-field driver selection.
- Fixture-backed full Analysis workflow tests proving snapshot reuse and
  reproducible metadata.
- Governance, spec, and drift validation before approval and before completion.

## Rollback plan

- Keep SPEC-005 flat fields loadable and renderable during migration.
- Gate normalized SPEC-006 parameter schemas behind schema version checks.
- If renderer primitives regress, fall back to SPEC-005 line rendering for
  affected templates while preserving saved requested configurations.
- If live preview is too slow, degrade to explicit Apply with stale-state
  marking while preserving validation and diagnostics.

## Approval and implementation decisions

- Approved by Nelson Jeanrenaud on 2026-07-22 after the chart-template review.
- FastF1 implementation target: 3.8.3.
- Implementation slicing: staged slices, starting with shared selection/filter
  semantics, full-session driver loading, effective configuration metadata, and
  renderer primitives used by the current built-in templates.
- First-pass preview behavior: explicit Apply/regenerate is acceptable while
  preserving stale-state and effective-configuration diagnostics.
- Full-session driver loading default: new Analysis sessions should default to
  all available session drivers, with selected-driver subsets remaining
  opt-in.

## Open questions

- [x] Which FastF1 version is the implementation target: installed project
  dependency, latest compatible release, or a pinned release?
- [x] Should SPEC-006 require live preview before generation, or can explicit
  Apply/regenerate satisfy the first implementation slice?
- [x] Should the first implementation target all four built-ins together, or
  ship telemetry/lap-delta first and tyre/position renderer primitives second?
- [ ] What is the canonical full-field fixture for tests?

## Human decisions required

- [x] Approve SPEC-006 scope as a new follow-up spec rather than an amendment
  inside SPEC-005.
- [x] Choose implementation slicing: one large pass or staged slices by shared
  model, renderer primitives, then per-template contracts.
- [x] Decide whether live preview is mandatory for the first implementation
  pass.
- [x] Decide whether full-session driver loading should default to all drivers
  or remain opt-in per Analysis session.

## Conflict check

SPEC-006 depends on SPEC-005 and intentionally supersedes the minimum built-in
parameter model from SPEC-005 for future implementation. It does not conflict
with SPEC-005's compatibility requirements because internal `recipe_id` fields
and legacy Analysis files remain supported. It intentionally changes SPEC-005's
no-preview non-goal for this later scope by introducing live or immediate
preview as a new requirement. This is not a conflict because SPEC-005 scoped out
preview only for its implementation pass.

## Traceability table

| Requirement ID | Design / component | Implementation (file/function) | Test | Status |
| -------------- | ------------------ | ------------------------------ | ---- | ------ |
| REQ-001 | Normalized sections | `src/f1_telemetry_charts/recipes/parameters.py`; `src/f1_telemetry_charts/analysis/workspace.py` | `tests/test_analysis_workspace.py`; `tests/test_core_recipes.py` | Implemented |
| REQ-002 | Basic/Advanced modes | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `src/f1_telemetry_charts/analysis/workspace.py` | frontend typecheck/build; schema tests | Implemented |
| REQ-003 | Dependency rules | `ParameterField.visible_when`; `required_when`; backend validation | `tests/test_analysis_workspace.py::test_schema_exposes_modes_dependencies_and_builtin_presets`; frontend typecheck/build | Implemented |
| REQ-004 | Driver selection | `src/f1_telemetry_charts/recipes/parameters.py`; `src/f1_telemetry_charts/analysis/workspace.py` | `tests/test_analysis_workspace.py`; `tests/test_core_recipes.py` | Implemented |
| REQ-005 | Full-session drivers | `src/f1_telemetry_charts/data/models.py`; gateways; Analysis UI defaults | `tests/test_data_gateway.py`; `tests/test_fastf1_gateway.py`; `tests/test_analysis_workspace.py` | Implemented |
| REQ-006 | Driver ordering | `src/f1_telemetry_charts/recipes/parameters.py`; schema fields | `tests/test_core_recipes.py`; full unittest discovery | Implemented |
| REQ-007 | Lap range | `src/f1_telemetry_charts/recipes/parameters.py`; UI range control | `tests/test_core_recipes.py`; frontend build | Implemented |
| REQ-008 | Box-lap policy | `src/f1_telemetry_charts/recipes/parameters.py`; lap recipes | `tests/test_core_recipes.py` | Implemented |
| REQ-009 | Lap validity | `LapRecord` quality fields; `lap_validity_policy`; filter diagnostics | `tests/test_core_recipes.py::test_lap_validity_track_status_and_active_filter_diagnostics` | Implemented |
| REQ-010 | Track status | `LapRecord.track_status`; `track_status_filter`; FastF1 mapping | `tests/test_core_recipes.py::test_lap_validity_track_status_and_active_filter_diagnostics` | Implemented |
| REQ-011 | Missing data | `missing_series_policy`; `telemetry_gap_policy`; metric safety checks | `tests/test_core_recipes.py::test_telemetry_gap_policy_rejects_categorical_interpolation` | Implemented |
| REQ-012 | Style configuration | color overrides; presentation section; renderer metadata | `tests/test_core_recipes.py`; `tests/test_lap_time_delta_recipe.py` | Implemented |
| REQ-013 | Presentation controls | `ChartSpec` primitives; Basic/Advanced controls; reset/override actions | `tests/test_lap_time_delta_recipe.py`; frontend typecheck/build | Implemented |
| REQ-014 | Telemetry trace | normalized telemetry analysis parameters and gap policy | `tests/test_core_recipes.py`; `tests/test_analysis_workspace.py` | Implemented |
| REQ-015 | Lap-time delta | baseline, reference driver, delta mode, filter diagnostics | `tests/test_core_recipes.py`; `tests/test_lap_time_delta_recipe.py` | Implemented |
| REQ-016 | Tyre strategy | stint bars, compound steps, pit markers, unknown-compound policy | `tests/test_core_recipes.py` | Implemented |
| REQ-017 | Position progression | lap-end position source, axis inversion, line mode, filter diagnostics | `tests/test_core_recipes.py` | Implemented |
| REQ-018 | Renderer primitives | line/step series, vertical markers, shaded regions, horizontal bars, axis inversion | `tests/test_core_recipes.py`; `tests/test_lap_time_delta_recipe.py` | Implemented |
| REQ-019 | Active-filter summary | diagnostics metadata; Chart Editor diagnostics panel | `tests/test_core_recipes.py`; `tests/test_analysis_workspace.py`; frontend build | Implemented |
| REQ-020 | Warnings/errors | structured diagnostics endpoint and metadata warnings/errors | `tests/test_analysis_workspace.py`; full unittest discovery | Implemented |
| REQ-021 | Reproducibility metadata | requested/effective configuration and diagnostics metadata | `tests/test_core_recipes.py`; `tests/test_lap_time_delta_recipe.py` | Implemented |
| REQ-022 | Analyst presets | built-in global preset definitions | `tests/test_analysis_workspace.py::test_schema_exposes_modes_dependencies_and_builtin_presets` | Implemented |
| REQ-023 | Reset behavior | Reset chart/section, restore preset, clear overrides actions | frontend typecheck/build; code inspection | Implemented |
| NFR-001 | Snapshot reuse | diagnostics/generation read snapshots without session reload | `tests/test_analysis_workspace.py`; full unittest discovery | Implemented |
| NFR-002 | UI scalability | searchable driver selector; grouped Basic/Advanced forms | frontend typecheck/build | Implemented |
| NFR-003 | Versioning/migration | flat-to-normalized parameter normalization; legacy flat acceptance | `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented |
| SEC-001 | No code authoring | structured schema/API parameters only | `tests/test_llm_contract.py`; API tests | Implemented |
| DATA-001 | Normalized persistence | `normalize_chart_parameters`; add/update/preset paths | `tests/test_analysis_workspace.py::test_flat_parameters_are_saved_as_normalized_sections_and_diagnostics_resolve` | Implemented |
| DATA-002 | Effective configuration | shared resolver metadata | `tests/test_core_recipes.py`; `tests/test_lap_time_delta_recipe.py` | Implemented |
| API-001 | Rich schema API | field mode/dependency/reset metadata in template schemas | `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented |
| API-002 | Diagnostics API | `/api/analysis/charts/diagnostics`; `ParameterDiagnosticsView` | `tests/test_analysis_workspace.py::test_flat_parameters_are_saved_as_normalized_sections_and_diagnostics_resolve` | Implemented |
| UX-001 | Form engine | dependency-aware Basic/Advanced form renderer | frontend typecheck/build | Implemented |
| UX-002 | Preview/apply UX | debounced diagnostics resolution plus explicit Save/Generate | frontend typecheck/build; API diagnostics tests | Implemented |
| UX-003 | Filters/warnings UX | Chart Editor diagnostics panel and metadata summaries | frontend typecheck/build; diagnostics tests | Implemented |

## Implementation notes

- 2026-07-22: Draft created from attached human review
  `FastF1 Analysis Chart Parameters - Functional and User-Interface Review`.
  The draft records the review's P0/P1/P2 concerns as a follow-up spec because
  the requested changes are broader than SPEC-005's approved minimum parameter
  pass.
- 2026-07-22: Current public package lookup showed FastF1 3.8.3 available while
  the attached review referenced 3.8.1. Implementation must verify exact FastF1
  API semantics against the selected target version before coding.
- 2026-07-23: Implementation completed with normalized parameter persistence,
  Basic/Advanced dependency-aware schema/UI metadata, shared filter and
  diagnostics policies, built-in analyst presets, renderer primitives, and
  full backend/frontend validation.

## Spec amendments

> Required for any behavioral change after the spec is Approved.

### AMEND-001

- **Date:**
- **Reason:**
- **Changed requirements:**
- **Behavioral impact:**
- **Test impact:**
- **Human approval reference:**

## Review checklist

- [x] spec_id is unique and follows the SPEC-XXX format.
- [x] Every requirement has an ID, statement, rationale, acceptance criteria,
      verification method, and evidence location.
- [x] Non-goals are listed.
- [x] Open questions are resolved or explicitly deferred.
- [x] Verification matrix covers every requirement.
- [x] Conflict check completed.
- [x] Human approval recorded before status set to Approved.
