---
doc_type: spec
spec_id: SPEC-007
title: Visual Track Map Range Selection and Race Playback Explorer
status: Implemented
owner: Nelson Jeanrenaud
related_issue:
related_prs: []
delivery_refs: ["https://github.com/Nelson-Jnrnd/F1_Telemetry_Charts/commit/d070f5e519349d0eae20fc445b45de8926721868"]
affected_components:
  - data_gateway
  - chart_templates
  - parameter_schema
  - chart_generation
  - chart_rendering
  - analysis_workspace
  - local_preview_ui
  - llm_contract
affected_interfaces:
  - Analysis Workbench UI
  - FastAPI local UI API
  - LLM contract
  - Analysis directory format
  - FastF1 session gateway
  - Built-in chart template schemas
  - Renderer-independent ChartSpec
depends_on:
  - SPEC-004
  - SPEC-005
  - SPEC-006
supersedes: []
superseded_by:
conflicts_with: []
last_verified_at: 2026-08-03
---

# SPEC-007: Visual Track Map Range Selection and Race Playback Explorer

## Summary

This spec turns the latest human review into a focused V2 follow-up: charts
must default to FastF1-derived driver/team colors instead of random colors, lap
and telemetry ranges must be bounded by loaded session data, and the Analysis
Workbench must add an interactive track-map experience for visual telemetry
segment selection, corner selection, and race playback exploration.

## Context

SPEC-006 added analyst-grade chart parameters, Basic/Advanced controls,
effective configuration diagnostics, lap validity, track status filters, and
renderer primitives. The follow-up review on 2026-07-23 identified that the
remaining range-selection workflow is still too numeric and error-prone:
drivers should use FastF1 colors by default, lap ranges should not allow values
outside loaded session coverage, and telemetry distance ranges should be
managed through a visual track map with corner-aware shortcuts.

FastF1 3.8.3 remains the implementation target from SPEC-006. The current
FastF1 documentation says its plotting module provides team colors, driver
styles, and tyre compound colors; `Session.get_circuit_info()` returns corner
locations, marshal lights, marshal sectors, and track map rotation when
available; session telemetry exposes GPS/position data and distance-based
telemetry suitable for track maps. The same documentation also states that
circuit information is manually created and may be unavailable, so this spec
requires degraded-but-usable fallback behavior.

Reference material:

- FastF1 visualization guide:
  https://theoehrly-fast-f1.mintlify.app/guides/visualization
- FastF1 session API:
  https://theoehrly-fast-f1.mintlify.app/api/session
- FastF1 package release target:
  https://pypi.org/project/fastf1/

## Problem statement

The current chart configuration flow still makes the user think in raw numeric
ranges. Users can enter lap values outside the loaded session range, telemetry
distance ranges are hard to tune without seeing where they land on the circuit,
and the app does not yet provide a track-map workspace for visually choosing
laps, corners, car positions, gaps, status periods, or tyre context.

## Goals

- Default built-in driver and team chart colors to FastF1/session-provided
  driver/team styling, with deterministic fallbacks and diagnostics.
- Expose session lap and telemetry distance coverage as structured bounds.
- Prevent invalid lap range and distance range input from silently producing
  confusing charts.
- Add a visual track-map range selector for telemetry charts.
- Add automatic corner selection when FastF1 circuit information is available.
- Keep numeric distance controls as advanced fine-tuning controls.
- Add a race playback explorer that shows car positions around the circuit by
  lap or session timestamp.
- Allow the race playback explorer to drive chart lap ranges and chart filters.
- Preserve local-first operation and reuse already loaded Analysis snapshots.

## Non-goals

- This spec does not require live race streaming or real-time broadcast data.
- This spec does not require 3D rendering.
- This spec does not require millimeter-accurate circuit geometry.
- This spec does not replace numeric lap and distance inputs; it makes visual
  selection the primary workflow while keeping numeric controls available.
- This spec does not add hosted services, shared sessions, or remote storage.
- This spec does not require every historic event to have corner metadata.
- This spec does not infer confirmed overtakes from position traces.
- This spec does not add user-authored Python chart logic.

## Users or actors

- Human analyst: selects meaningful laps, corners, and track segments for
  chart generation and review.
- Human writer: uses visual race context to choose chart ranges for reports.
- LLM agent: inspects available track-map metadata and proposes safe parameter
  changes without creating code.
- FastF1 session gateway: loads session, lap, telemetry, position, style, and
  circuit metadata when available.
- Analysis Workbench frontend: renders range controls, track-map selector, and
  race playback explorer.
- FastAPI backend: validates bounds, resolves effective selections, and serves
  normalized map/playback data from local Analysis snapshots.
- Renderer: renders generated chart metadata and optional range/corner
  annotations.

## Terminology

- **Track map:** A normalized 2D circuit trace derived from telemetry position
  samples and optionally rotated/annotated using FastF1 circuit information.
- **Track segment:** A start/end distance interval on one lap, measured in
  meters from lap start.
- **Corner marker:** A named or numbered circuit location from FastF1 circuit
  information, with approximate track distance when the app can project it
  onto the loaded telemetry trace.
- **Race playback frame:** A session-time or lap-relative snapshot containing
  visible car positions and contextual state for the loaded Analysis session.
- **Coverage bounds:** The minimum and maximum valid values available from the
  loaded snapshot for lap number, session time, telemetry distance, and driver
  participation.

## Vertical implementation slices

Each slice must be implemented as production product scope across data models,
backend validation, APIs, frontend behavior, metadata, tests, and documentation
traceability. A slice is not complete if it relies on temporary fallbacks,
disabled controls, hardcoded fixtures, or knowingly incomplete validation. Work
must stop before starting the next slice if the current slice does not satisfy
its own requirements and verification evidence.

### Slice 1: Official styles and bounded numeric ranges

This first slice replaces random built-in chart colors with official
FastF1/session-derived style defaults and makes existing numeric lap and
telemetry distance controls data-bounded. It does not introduce the visual track
map yet; it hardens the current chart configuration workflow so that every
existing numeric range and color default is reliable before visual selection is
added.

Scope:

- Official driver, team, and tyre compound style defaults for built-in charts.
- Deterministic non-random fallback colors with explicit diagnostics.
- Coverage bounds for loaded laps, selected drivers, telemetry distance, and
  range availability.
- Backend validation for out-of-coverage lap and telemetry distance ranges on
  chart create, chart update, diagnostics, LLM parameter updates, and
  generation.
- Frontend numeric controls that use backend bounds, prevent invalid values
  where possible, and display field-level diagnostics where prevention is not
  possible.
- Generated artifact metadata that records style sources, fallback diagnostics,
  requested/effective bounds, and range validation decisions.
- Snapshot reuse for all bounds/style lookup during normal chart editing.
- Regression tests, frontend typecheck/build, browser smoke checks for the
  affected chart configuration surfaces, and governance/spec/drift validation.

Requirements covered:

- REQ-001, REQ-002, REQ-003, REQ-004, REQ-005, REQ-017, REQ-018, REQ-019,
  REQ-020.
- NFR-001 for existing numeric-range interactions only.
- SEC-001, SEC-002.
- DATA-001, DATA-002.
- API-001 and the range-validation portion of API-003.
- UX-003 and the bounded-input portions of UX-006.

Completion gate:

- Built-in charts no longer use random colors by default.
- Invalid lap and telemetry distance ranges are impossible to save silently and
  cannot generate misleading empty charts.
- All relevant API, LLM, and UI paths use the same backend validation and
  return field-specific diagnostics.
- Full test/build/governance validation passes.

### Slice 2: Manual visual telemetry track segment selection

This slice adds the first visual track-map selector for telemetry charts. It is
manual distance selection on a rendered circuit trace, without automatic corner
shortcuts. Numeric distance controls remain synchronized and continue to use
the Slice 1 validation contract.

Scope:

- Track geometry extraction from loaded snapshot telemetry position data.
- Bounded, downsampled track-map API payloads.
- Track-map selector UI with visible start/end markers, highlighted segment,
  numeric synchronization, reset-to-full-lap, apply, and cancel behavior.
- Synchronization from visual segment selection into the existing normalized
  telemetry range parameters.
- Degraded state when geometry is unavailable while preserving numeric
  controls.
- Track segment metadata in chart artifacts and exports.

Requirements covered:

- REQ-006, REQ-007, REQ-010, REQ-011, REQ-017, REQ-018, REQ-019, REQ-020.
- NFR-001, NFR-002, NFR-003 for selector payloads and selector UI.
- DATA-003.
- API-002 and the visual-range portion of API-003.
- UX-001, UX-002, UX-003, UX-006.

Completion gate:

- A user can select a telemetry segment visually, save it, regenerate a chart,
  reopen the selector, and see the same segment reconstructed from saved
  parameters.
- Missing geometry degrades cleanly without disabling numeric telemetry range
  editing.
- Browser checks pass at desktop and mobile widths.

### Slice 3: Automatic corner selection

This slice layers FastF1 circuit information on top of the Slice 2 track
selector. It adds corner markers, corner projection, and corner-focused range
shortcuts with explicit confidence and fallback diagnostics.

Scope:

- FastF1 circuit information capture and persistence where available.
- Corner marker model with projection to telemetry distance.
- Corner list and marker rendering inside the track selector.
- Single-corner focus and configurable pre/post padding.
- Saved corner metadata, projection status, and resolved numeric range.
- Clean unavailable state when circuit information or projection is missing.

Requirements covered:

- REQ-008, REQ-009, REQ-011, REQ-017, REQ-018, REQ-019, REQ-020.
- NFR-002 and NFR-003 for corner payloads and selector UI.
- DATA-004.
- API-002 and API-003 for corner-aware range validation.
- UX-002 and UX-006.

Completion gate:

- A user can focus a supported corner, apply a padded distance range, regenerate
  a telemetry chart, and inspect metadata proving which corner and range were
  used.
- Unsupported sessions hide corner shortcuts without inventing corner labels.

### Slice 4: Race playback explorer and chart lap-range handoff

This slice adds the race map playback surface for loaded race-like sessions and
lets playback selections update chart lap ranges.

Scope:

- Playback frame model and bounded playback API.
- Lap and timestamp playback modes when data supports them.
- Position interpolation with explicit missing/stale marker semantics.
- Track status, tyre, stint, lap, position, pit-state, and gap context where
  available.
- Race playback explorer UI with map, timeline controls, selected driver
  context, and chart-range actions.
- Applying a playback lap or lap interval to chart normalized lap ranges while
  preserving unsaved edits and stale-state semantics.

Requirements covered:

- REQ-012, REQ-013, REQ-014, REQ-015, REQ-016, REQ-017, REQ-018, REQ-019,
  REQ-020.
- NFR-001, NFR-002, NFR-003 for playback.
- DATA-005.
- API-004.
- UX-004, UX-005, UX-006.

Completion gate:

- A loaded race-like session can be scrubbed by lap and/or timestamp where data
  supports it, with bounded payloads and explicit missing-data semantics.
- A selected playback interval can update a chart lap range through backend
  validation and marks only affected generated artifacts stale.

## Functional requirements

### REQ-001: Official style defaults

- **Statement:** Built-in chart templates must default driver, team, and tyre
  colors to FastF1/session-derived style data where available before using any
  generated fallback palette.
- **Rationale:** Random colors reduce F1 readability and break consistency
  between charts.
- **Acceptance criteria:** For FastF1-backed sessions, driver/team series use
  FastF1 plotting/session colors by default; tyre compounds use FastF1 compound
  mappings where available; user color overrides still take precedence.
- **Verification method:** Unit tests and renderer metadata assertions.
- **Evidence location:** To be filled during implementation.

### REQ-002: Deterministic style fallback diagnostics

- **Statement:** When FastF1/session color data is unavailable or invalid, the
  system must use deterministic fallback colors and record a non-blocking
  diagnostic.
- **Rationale:** Charts must remain renderable without silently pretending that
  fallback colors are official.
- **Acceptance criteria:** Fallback colors are stable for the same series
  label; metadata records which series used fallback colors and why; no random
  color generation is used for built-in driver/team/compound series.
- **Verification method:** Unit tests and metadata fixture inspection.
- **Evidence location:** To be filled during implementation.

### REQ-003: Session coverage bounds

- **Statement:** Analysis snapshots must expose loaded coverage bounds for
  laps, session time, drivers, telemetry distance, and track map availability.
- **Rationale:** UI controls and backend validation need the same authoritative
  range limits.
- **Acceptance criteria:** The backend can return per-session bounds including
  minimum/maximum lap number, available laps per driver, session-time coverage,
  telemetry distance range per driver/lap source, and map/corner metadata
  availability.
- **Verification method:** API/model tests with fixture and FastF1-backed
  snapshots.
- **Evidence location:** To be filled during implementation.

### REQ-004: Bounded lap range controls

- **Statement:** Lap range controls must prevent or reject values outside the
  loaded session coverage for the active selection.
- **Rationale:** Entering impossible lap numbers produces confusing validation
  and empty charts.
- **Acceptance criteria:** The UI numeric controls use coverage min/max bounds;
  the backend rejects out-of-coverage `lap_range.start` and `lap_range.end`
  with field-specific errors; partial per-driver coverage is shown as a warning
  rather than silently ignored.
- **Verification method:** Frontend checks and API validation tests.
- **Evidence location:** To be filled during implementation.

### REQ-005: Bounded telemetry distance controls

- **Statement:** Telemetry distance range controls must be bounded by the
  effective telemetry distance coverage of the selected driver/lap basis.
- **Rationale:** Raw distance entry is currently hard to manage and can select
  unavailable data.
- **Acceptance criteria:** Distance range min/max values come from loaded
  telemetry; backend validation rejects negative, reversed, or out-of-coverage
  ranges; valid ranges preserve exact numeric start/end values for fine tuning.
- **Verification method:** Recipe/API tests and frontend checks.
- **Evidence location:** To be filled during implementation.

### REQ-006: Track geometry extraction

- **Statement:** The backend must derive a normalized 2D track geometry from
  loaded telemetry position data and annotate it with FastF1 circuit
  information when available.
- **Rationale:** Visual selection requires a stable circuit trace and distance
  mapping independent of a particular chart render.
- **Acceptance criteria:** Track geometry includes ordered points with x/y
  coordinates, distance, source driver/lap, and projection status; FastF1 track
  rotation is applied when available; geometry generation records whether
  corner/circuit metadata was available.
- **Verification method:** Data model tests with synthetic and fixture
  telemetry.
- **Evidence location:** To be filled during implementation.

### REQ-007: Visual telemetry range selector

- **Statement:** Telemetry chart configuration must provide a track-map selector
  that lets the user choose start and end distance on the circuit trace.
- **Rationale:** Users should see where a distance interval starts and ends
  instead of tuning meter values blindly.
- **Acceptance criteria:** Opening the selector shows the circuit trace,
  currently selected range, draggable start/end handles or equivalent range
  controls, numeric start/end values, reset-to-full-lap action, and apply/cancel
  behavior; dragging and numeric edits stay synchronized.
- **Verification method:** Frontend interaction tests or Playwright/manual UI
  checks plus API validation tests.
- **Evidence location:** To be filled during implementation.

### REQ-008: Automatic corner selector

- **Statement:** When FastF1 circuit corner metadata is available, the track-map
  selector must support selecting one or more corners as a shortcut to a
  telemetry distance range.
- **Rationale:** Analysts usually reason about corners, not only meters from
  lap start.
- **Acceptance criteria:** The selector lists available corners, highlights
  them on the track map, can focus a single corner instantly, can create a
  range around a corner with configurable pre/post padding, and records the
  selected corner label and resolved distance range in metadata.
- **Verification method:** Model tests for projection/padding and frontend
  interaction checks.
- **Evidence location:** To be filled during implementation.

### REQ-009: Corner fallback behavior

- **Statement:** If FastF1 circuit information is unavailable or cannot be
  projected onto telemetry, the track-map selector must still support manual
  visual distance selection and must hide automatic corner shortcuts.
- **Rationale:** The feature must remain usable for sessions without curated
  circuit metadata.
- **Acceptance criteria:** Missing corner metadata never blocks manual range
  selection; diagnostics identify the missing source; no fake corner labels are
  generated.
- **Verification method:** API/UI tests with a no-circuit-info fixture.
- **Evidence location:** To be filled during implementation.

### REQ-010: Range-to-chart synchronization

- **Statement:** Visual track segment selection must write to the same
  normalized telemetry range parameters used by chart generation.
- **Rationale:** The selector should improve the existing telemetry workflow
  without creating a second range model.
- **Acceptance criteria:** Applying a visual range updates telemetry chart
  parameters; saving/generating the chart uses the applied range; re-opening the
  selector reconstructs the same selected segment from saved parameters.
- **Verification method:** Frontend/API integration tests.
- **Evidence location:** To be filled during implementation.

### REQ-011: Track segment chart annotations

- **Statement:** Generated telemetry charts must be able to include metadata
  and optional visual annotations for the selected track segment and corner.
- **Rationale:** Exported charts should remain understandable after the UI
  selection context is gone.
- **Acceptance criteria:** Chart metadata records source range, corner label
  when selected, projection confidence/status, and padding; optional chart
  annotations can mark segment start/end without being required by default.
- **Verification method:** Renderer metadata tests and optional visual artifact
  checks.
- **Evidence location:** To be filled during implementation.

### REQ-012: Race playback explorer

- **Statement:** The Analysis Workbench must provide a race playback explorer
  for loaded race-like sessions that displays car positions around the track
  over a lap or session timestamp timeline.
- **Rationale:** The same track map can help users choose which race phase or
  lap range to analyze.
- **Acceptance criteria:** The explorer shows a track map, visible car markers,
  current lap/session-time cursor, selected driver focus, and controls to scrub
  through the available loaded timeline.
- **Verification method:** Frontend visual/interaction checks and API tests.
- **Evidence location:** To be filled during implementation.

### REQ-013: Time and lap playback modes

- **Statement:** The playback explorer must support both continuous Time
  scrubbing and Lap scrubbing where the underlying snapshot contains enough
  data. Lap scrubbing resolves to the session timestamp where the race leader
  starts the selected lap.
- **Rationale:** Analysts may choose race phases by lap number or by real
  session timeline.
- **Acceptance criteria:** The UI exposes a clear mode switch; Time mode uses
  bounded session-time values; Lap mode uses bounded leader lap values snapped
  to leader lap-start timestamps; modes are disabled with diagnostics when
  required source data is missing.
- **Verification method:** API tests and frontend checks.
- **Evidence location:** To be filled during implementation.

### REQ-014: Position frame interpolation

- **Statement:** The backend must generate race playback frames from loaded
  position/telemetry data with explicit interpolation semantics.
- **Rationale:** Car markers need stable positions even when samples are not
  aligned across drivers.
- **Acceptance criteria:** Frame generation uses nearest-neighbor or linear
  interpolation only where allowed by configuration; missing/stale driver
  positions are marked separately from active positions; metadata records the
  interpolation method and maximum sample gap.
- **Verification method:** Unit tests with sparse synthetic position samples.
- **Evidence location:** To be filled during implementation.

### REQ-015: Playback context details

- **Statement:** The playback explorer must expose race context for displayed
  drivers, including gap/interval data where available, track status, tyre
  compound, stint, lap number, position, and pit state.
- **Rationale:** The map is useful only if it connects positions to the
  analytical context used for chart selection.
- **Acceptance criteria:** Selecting or focusing a driver shows available
  context fields; unavailable values are represented as missing, not guessed;
  inferred gap values are labelled in metadata as derived from local samples.
- **Verification method:** API model tests and frontend checks.
- **Evidence location:** To be filled during implementation.

### REQ-016: Playback-driven chart range selection

- **Statement:** The race playback explorer must let users create or update
  chart lap ranges from the visible playback cursor or selected playback
  interval.
- **Rationale:** Users should be able to move from race context directly into
  chart analysis without manually copying lap numbers.
- **Acceptance criteria:** A selected lap or lap interval can apply to a chart's
  normalized lap range; backend validation still enforces chart/session
  compatibility; applying a playback interval marks affected charts stale until
  regenerated.
- **Verification method:** API/frontend integration tests.
- **Evidence location:** To be filled during implementation.

### REQ-017: Snapshot reuse

- **Statement:** Track geometry, corner metadata, range validation, and race
  playback must use already loaded Analysis snapshots whenever possible and
  must not implicitly reload FastF1 sessions during normal UI interaction.
- **Rationale:** SPEC-004 and SPEC-006 established snapshot-based iteration for
  speed and reproducibility.
- **Acceptance criteria:** Opening the selector or playback explorer does not
  call FastF1 when snapshot data is sufficient; missing data triggers explicit
  diagnostics or an explicit reload action, not hidden network access.
- **Verification method:** Service tests with mocked gateways and benchmark
  checks.
- **Evidence location:** To be filled during implementation.

### REQ-018: Exported selection metadata

- **Statement:** Generated artifacts and Analysis exports must preserve track
  segment, corner, lap-range, and playback-derived selection metadata.
- **Rationale:** Reports need reproducibility and traceability for visually
  selected ranges.
- **Acceptance criteria:** Exported chart metadata includes requested and
  effective range source, visual selector state, corner source when used,
  bounds, warnings, and fallback/degraded-mode diagnostics.
- **Verification method:** Metadata tests and package fixture inspection.
- **Evidence location:** To be filled during implementation.

### REQ-019: Graceful degraded modes

- **Statement:** The UI must clearly degrade when track geometry, corner
  metadata, position data, or timestamp data is unavailable.
- **Rationale:** FastF1 data availability differs across sessions and seasons.
- **Acceptance criteria:** Missing track geometry disables visual selectors but
  keeps numeric controls; missing corner metadata disables only corner
  shortcuts; missing position/timestamp data disables playback mode while
  preserving chart configuration; all degraded states include backend
  diagnostics.
- **Verification method:** API/frontend tests with missing-data fixtures.
- **Evidence location:** To be filled during implementation.

### REQ-020: LLM-safe track-map inspection

- **Statement:** The LLM contract must expose bounded track-map, corner,
  coverage, and playback selection metadata without exposing raw large
  telemetry arrays by default.
- **Rationale:** Agents need enough structured context to suggest ranges and
  corners safely without consuming huge payloads or authoring code.
- **Acceptance criteria:** LLM inspection includes availability, bounds, corner
  labels, selected ranges, and diagnostics; raw point arrays require an
  explicit bounded request or are summarized; LLM parameter updates continue to
  use backend validation.
- **Verification method:** LLM contract tests.
- **Evidence location:** To be filled during implementation.

## Non-functional requirements

### NFR-001: Interactive performance

- **Statement:** Track selector and playback UI interactions should feel
  immediate for a representative race session.
- **Rationale:** Visual scrubbing is unusable if every interaction performs
  expensive backend work.
- **Acceptance criteria:** Opening a prepared track selector or playback view
  returns its initial payload within 1 second from local snapshot data; scrubbing
  an already loaded timeline updates visible state without full chart
  regeneration.
- **Verification method:** API benchmark and browser/manual check.
- **Evidence location:** To be filled during implementation.

### NFR-002: Payload bounds

- **Statement:** Track-map and playback API payloads must be bounded and
  downsampled for UI use.
- **Rationale:** Raw telemetry and position streams can be large and would slow
  the local UI.
- **Acceptance criteria:** API responses expose a bounded point count by
  default, include original sample counts, and can request higher detail only
  through explicit limits.
- **Verification method:** API tests and fixture payload-size inspection.
- **Evidence location:** To be filled during implementation.

### NFR-003: Responsive usability

- **Statement:** The selector and playback explorer must remain usable on
  desktop and mobile-sized viewports supported by the V2 UI.
- **Rationale:** SPEC-006 browser checks established that chart configuration
  must avoid overflow and unusable controls.
- **Acceptance criteria:** Track map, controls, selected range summaries, and
  context panels fit without horizontal overflow at representative desktop and
  mobile widths.
- **Verification method:** Playwright/manual browser screenshots.
- **Evidence location:** To be filled during implementation.

## Security and privacy considerations

### SEC-001: Local snapshot boundary

- **Statement:** Track-map and playback endpoints must serve only data from the
  explicitly opened Analysis snapshot or explicit local package context.
- **Rationale:** The local UI must not expose unrelated filesystem or cache
  data.
- **Acceptance criteria:** API path and session identifiers are validated
  against the open Analysis; callers cannot request arbitrary cache files or
  unrelated FastF1 data through map endpoints.
- **Verification method:** API security tests.
- **Evidence location:** To be filled during implementation.

### SEC-002: No code authoring surface

- **Statement:** Track-map, corner, and playback workflows must remain
  parameter/data selection workflows and must not introduce user-authored code
  execution.
- **Rationale:** SPEC-005 and SPEC-006 preserve the trusted plugin boundary.
- **Acceptance criteria:** UI and LLM APIs accept structured selection
  parameters only; no map workflow accepts executable expressions or Python
  snippets.
- **Verification method:** API/LLM contract inspection and tests.
- **Evidence location:** To be filled during implementation.

## Data model impact

### DATA-001: Style source metadata

- **Statement:** Driver, team, compound, and series style metadata must record
  source and fallback status.
- **Rationale:** Visual consistency decisions need reproducibility.
- **Acceptance criteria:** Metadata distinguishes FastF1 plotting style,
  session-provided color, user override, and deterministic fallback.
- **Verification method:** Model tests and artifact metadata tests.
- **Evidence location:** To be filled during implementation.

### DATA-002: Coverage bounds model

- **Statement:** Analysis snapshots must expose a structured coverage bounds
  model for lap, time, telemetry distance, track geometry, and playback
  availability.
- **Rationale:** Shared validation and UI controls require a common bounds
  source.
- **Acceptance criteria:** The model supports session-level and driver-level
  coverage and can represent missing/partial data with reasons.
- **Verification method:** Model/API tests.
- **Evidence location:** To be filled during implementation.

### DATA-003: Track geometry model

- **Statement:** The data model must represent downsampled track points, source
  sample counts, source driver/lap, orientation/rotation, and projection status.
- **Rationale:** The UI needs enough geometry to draw a stable map without
  loading raw telemetry.
- **Acceptance criteria:** Track geometry can be serialized into Analysis
  metadata or computed deterministically from snapshots; degraded states are
  explicit.
- **Verification method:** Model tests and fixture inspection.
- **Evidence location:** To be filled during implementation.

### DATA-004: Corner marker model

- **Statement:** The data model must represent FastF1 corner markers and their
  projected distance ranges when projection succeeds.
- **Rationale:** Automatic corner selection needs structured metadata separate
  from free-form labels.
- **Acceptance criteria:** Each marker includes label/number, x/y coordinate
  where available, projected distance when available, confidence/status, and
  source.
- **Verification method:** Model tests.
- **Evidence location:** To be filled during implementation.

### DATA-005: Playback frame model

- **Statement:** The data model must represent race playback frames, car
  positions, context fields, interpolation status, and selected playback
  intervals.
- **Rationale:** Race map exploration and chart range application need a
  reproducible model.
- **Acceptance criteria:** Frames include cursor mode/value, driver markers,
  optional gaps, tyre/stint/status context, missing-data reasons, and source
  sample metadata.
- **Verification method:** Model/API tests.
- **Evidence location:** To be filled during implementation.

## API impact

### API-001: Coverage endpoint

- **Statement:** The local UI API must expose session coverage bounds for the
  active Analysis.
- **Rationale:** The frontend should not derive authoritative bounds from
  chart-specific payloads.
- **Acceptance criteria:** Endpoint returns bounds for loaded sessions, selected
  charts, drivers, laps, telemetry distance, track geometry, circuit info, and
  playback availability.
- **Verification method:** FastAPI tests.
- **Evidence location:** To be filled during implementation.

### API-002: Track map endpoint

- **Statement:** The local UI API must expose a bounded track-map payload for a
  selected Analysis session and telemetry basis.
- **Rationale:** The track selector and race explorer need a shared map source.
- **Acceptance criteria:** Endpoint returns downsampled geometry, corner
  markers, bounds, diagnostics, and style metadata without raw unbounded
  telemetry.
- **Verification method:** FastAPI tests and payload-size inspection.
- **Evidence location:** To be filled during implementation.

### API-003: Range validation endpoint

- **Statement:** The backend must validate visual or numeric lap/distance range
  changes before chart save/generate.
- **Rationale:** UI controls and LLM updates must receive the same field-level
  diagnostics.
- **Acceptance criteria:** Endpoint returns field-specific errors, warnings,
  effective range, corner projection status, and chart staleness impact.
- **Verification method:** FastAPI tests.
- **Evidence location:** To be filled during implementation.

### API-004: Playback endpoint

- **Statement:** The local UI API must expose bounded playback frames or frame
  windows for race-like sessions.
- **Rationale:** Scrubbing requires backend-prepared, bounded position/context
  data.
- **Acceptance criteria:** Endpoint supports lap and timestamp cursor modes,
  bounded driver selection, downsampling/window limits, and missing-data
  diagnostics.
- **Verification method:** FastAPI tests and performance checks.
- **Evidence location:** To be filled during implementation.

## UI or UX impact

### UX-001: Primary visual distance selection

- **Statement:** Telemetry distance selection must be primarily visual through
  the track-map selector, with numeric fields retained as advanced fine tuning.
- **Rationale:** The user review identifies numeric distance entry as the wrong
  primary interaction for corner-focused analysis.
- **Acceptance criteria:** The telemetry chart editor exposes an obvious track
  selector action near distance range controls; numeric start/end fields remain
  available and synchronized.
- **Verification method:** Browser/manual UI check.
- **Evidence location:** To be filled during implementation.

### UX-002: Track-map selector ergonomics

- **Statement:** The selector must make start, end, selected segment, and corner
  focus visually clear.
- **Rationale:** Users must know exactly which part of the lap will be charted.
- **Acceptance criteria:** Start/end markers are distinct, the selected segment
  is highlighted, corner labels do not obscure the trace, and reset/apply/cancel
  actions are available without explanatory filler text.
- **Verification method:** Browser visual checks.
- **Evidence location:** To be filled during implementation.

### UX-003: Bounded input feedback

- **Statement:** Out-of-range lap or distance values must be prevented where
  possible and explained with concise field-level feedback where not.
- **Rationale:** Range errors should be corrected at the point of input.
- **Acceptance criteria:** Numeric controls include min/max affordances, invalid
  values show field-level diagnostics, and chart generation remains blocked
  until invalid ranges are corrected.
- **Verification method:** Frontend/API tests.
- **Evidence location:** To be filled during implementation.

### UX-004: Race playback explorer layout

- **Statement:** The race playback explorer must be a work-focused analysis
  surface, not a decorative landing page.
- **Rationale:** The component is for repeated lap/race inspection.
- **Acceptance criteria:** First screen shows the map, timeline/lap slider,
  selected driver context, and chart-range actions; controls are dense and
  scannable; there are no marketing-style hero sections.
- **Verification method:** Browser visual inspection.
- **Evidence location:** To be filled during implementation.

### UX-005: Chart-range handoff

- **Statement:** Users must be able to apply a selected lap/race interval to
  existing chart instances without losing unsaved chart edits.
- **Rationale:** The map explorer should improve the Analysis workflow rather
  than create a disconnected visualization.
- **Acceptance criteria:** Applying an interval previews affected chart
  changes, preserves unsaved local edits, and marks only affected generated
  artifacts stale after save.
- **Verification method:** Frontend integration tests or manual checks.
- **Evidence location:** To be filled during implementation.

### UX-006: Degraded data states

- **Statement:** Missing map, corner, position, or timestamp data must produce
  concise unavailable states that keep other chart controls usable.
- **Rationale:** FastF1 data coverage is not uniform across all sessions.
- **Acceptance criteria:** Each unavailable state names the missing capability,
  leaves compatible controls enabled, and avoids suggesting fake precision.
- **Verification method:** Frontend tests with missing-data fixtures.
- **Evidence location:** To be filled during implementation.

## Configuration impact

- Existing SPEC-006 normalized chart parameters remain valid.
- Telemetry chart parameters gain optional `selection.track_segment` metadata
  that records visual selection source, selected corner, padding, projection
  status, and synchronized distance range.
- Existing `analysis.telemetry_range` or equivalent distance fields continue to
  be honored and are used to reconstruct the visual selector state.
- Analysis snapshots may store or cache derived track geometry/playback summary
  data to avoid recomputation, but raw unbounded telemetry should remain in the
  snapshot model rather than the UI payload.
- Global presets that contain distance ranges remain valid; presets created
  from a corner selection should include the resolved numeric range plus
  corner metadata when available.

## Error handling

- Out-of-coverage lap range: blocking field-level validation error.
- Reversed lap or distance range: blocking field-level validation error.
- Negative distance range: blocking field-level validation error.
- Selected corner cannot be projected: warning plus manual distance range
  fallback.
- Circuit info unavailable: warning/degraded state; manual selector remains
  available if geometry exists.
- Track geometry unavailable: visual selector disabled; numeric controls remain
  available.
- Playback position data unavailable: playback explorer disabled; chart range
  controls remain available.
- Sparse playback samples exceed configured interpolation gap: marker shown as
  missing/stale for that driver/frame.
- Official color lookup fails: deterministic fallback with metadata warning.
- Applying playback range to incompatible chart/session: blocking validation
  error.

## Edge cases

- Sessions with laps but no telemetry.
- Telemetry with distance but no X/Y position.
- X/Y position data without useful distance.
- Driver selected for telemetry range has no representative lap.
- Fastest lap source changes after filters.
- Circuit info exists but corner coordinates do not project cleanly to the
  telemetry trace.
- Tracks with start/finish offset where distance zero is not visually close to
  the desired selected corner.
- Street circuits or temporary tracks with manually curated corner metadata.
- Sprint, qualifying, practice, red-flagged, and restarted sessions.
- Drivers with partial race participation, retirement, or missing position
  samples.
- Safety Car/VSC/red-flag periods during selected playback intervals.
- Lapped cars when calculating displayed gaps.
- Multiple loaded sessions with different track layouts.
- Existing chart presets that store only numeric ranges.

## Acceptance criteria

- Built-in charts no longer use random driver/team/compound colors by default.
- Lap range controls and backend validation are bounded by loaded session
  coverage.
- Telemetry distance range controls are bounded and remain available for fine
  tuning.
- Telemetry charts can use a visual track-map selector to set start/end
  distance.
- FastF1 corner metadata, when available, provides automatic corner-focused
  range selection.
- Missing circuit/corner/position data produces degraded states instead of
  broken controls or fabricated metadata.
- Race-like sessions can be inspected through a track-map playback explorer
  using lap and/or timestamp controls where data allows.
- Playback context can be used to apply lap ranges to charts while preserving
  backend validation and stale-state semantics.
- Generated artifacts preserve selection, corner, bounds, and fallback
  diagnostics for reproducibility.

## Verification matrix

| Requirement ID | Acceptance criterion | Verification method | Test / command / manual check | Evidence location | PR reference |
| -------------- | -------------------- | ------------------- | ----------------------------- | ----------------- | ------------ |
| REQ-001 | Official style sources are default | unit/metadata tests | `python -m unittest tests.test_core_recipes tests.test_fastf1_gateway`; `python -m unittest discover -s tests` | `src/f1_telemetry_charts/data/gateways/fastf1.py`; `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_core_recipes.py`; `tests/test_fastf1_gateway.py` | |
| REQ-002 | Fallback colors are deterministic and diagnosed | unit/metadata tests | `python -m unittest tests.test_core_recipes`; `python -m unittest discover -s tests` | `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_core_recipes.py` | |
| REQ-003 | Coverage bounds are available | API/model tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract`; browser smoke check | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/recipes/parameters.py`; `src/f1_telemetry_charts/ui/server.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| REQ-004 | Lap ranges are bounded | frontend/API tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract`; browser smoke check | `src/f1_telemetry_charts/analysis/workspace.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| REQ-005 | Distance ranges are bounded | recipe/API tests | `python -m unittest tests.test_core_recipes tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/recipes/telemetry_trace.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_core_recipes.py`; `tests/test_analysis_workspace.py` | |
| REQ-006 | Track geometry derives from loaded data | model/API tests | `python -m unittest tests.test_fastf1_gateway tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/gateways/fastf1.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `tests/test_fastf1_gateway.py`; `tests/test_analysis_workspace.py` | |
| REQ-007 | Visual range selector works | UI/API tests | `pnpm --dir frontend typecheck`; `pnpm --dir frontend build`; browser smoke check at desktop and mobile widths, including Add Chart draft access | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `frontend/src/api.ts`; `frontend/src/types.ts`; rebuilt `src/f1_telemetry_charts/ui/static/` assets | |
| REQ-008 | Corner shortcuts resolve ranges | model/UI tests | `python -m unittest tests.test_track_geometry tests.test_fastf1_gateway tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/gateways/fastf1.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_track_geometry.py`; `tests/test_fastf1_gateway.py`; `tests/test_analysis_workspace.py` | |
| REQ-009 | Missing corners degrade cleanly | API/UI tests | `python -m unittest tests.test_track_geometry tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/analysis/track_map.py`; `src/f1_telemetry_charts/recipes/parameters.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_track_geometry.py`; `tests/test_analysis_workspace.py` | |
| REQ-010 | Visual selection syncs to chart params | frontend/API tests | `python -m unittest tests.test_analysis_workspace`; browser smoke check for apply/save/generate/reopen | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py` | |
| REQ-011 | Segment metadata/annotations export | renderer/metadata tests | `python -m unittest tests.test_analysis_workspace`; generated metadata fixture inspection in test | `src/f1_telemetry_charts/recipes/telemetry_trace.py`; `tests/test_analysis_workspace.py` | |
| REQ-012 | Playback explorer renders positions | frontend/API tests | `python -m unittest tests.test_analysis_workspace`; `pnpm --dir frontend typecheck`; `pnpm --dir frontend build`; browser smoke check | `src/f1_telemetry_charts/analysis/playback.py`; `src/f1_telemetry_charts/ui/server.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py` | |
| REQ-013 | Time and lap modes are bounded | API/frontend tests | `python -m unittest tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/analysis/playback.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py` | |
| REQ-014 | Interpolation semantics are explicit | unit tests | `python -m unittest tests.test_analysis_workspace` | `src/f1_telemetry_charts/analysis/playback.py`; `tests/test_analysis_workspace.py` | |
| REQ-015 | Playback context details are available | API/frontend tests | `python -m unittest tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/analysis/playback.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py` | |
| REQ-016 | Playback interval applies to chart range | integration tests | `python -m unittest tests.test_analysis_workspace`; browser smoke check | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_analysis_workspace.py` | |
| REQ-017 | Snapshot reuse avoids implicit reloads | service tests/benchmark | `python -m unittest tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/analysis/playback.py`; `tests/test_analysis_workspace.py` | |
| REQ-018 | Exported metadata preserves selections | metadata tests | `python -m unittest tests.test_core_recipes tests.test_analysis_workspace`; browser smoke check | Built-in recipe metadata in `src/f1_telemetry_charts/recipes/`; `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_core_recipes.py`; `tests/test_analysis_workspace.py` | |
| REQ-019 | Degraded modes are graceful | API/frontend tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract`; browser degraded-state check | Coverage availability reasons in `src/f1_telemetry_charts/recipes/parameters.py`; track-map unavailable payload in `src/f1_telemetry_charts/analysis/track_map.py`; playback unavailable payload in `src/f1_telemetry_charts/analysis/playback.py`; UI degraded state in `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| REQ-020 | LLM inspection is bounded and safe | LLM contract tests | `python -m unittest tests.test_llm_contract` | `src/f1_telemetry_charts/llm/contract.py`; `tests/test_llm_contract.py` | |
| NFR-001 | Selector/playback interactions are responsive | benchmark/manual check | Browser smoke check for numeric-range, track-selector, and race-playback interactions | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `src/f1_telemetry_charts/analysis/playback.py` | |
| NFR-002 | Map/playback payloads are bounded | API tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract` | `src/f1_telemetry_charts/analysis/track_map.py`; `src/f1_telemetry_charts/analysis/playback.py`; `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/llm/contract.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| NFR-003 | UI works on desktop and mobile widths | browser screenshots/manual checks | Browser smoke check at default desktop viewport and 390x844 mobile viewport | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; rebuilt `src/f1_telemetry_charts/ui/static/` assets | |
| SEC-001 | Endpoints stay inside open Analysis | API security tests | `python -m unittest tests.test_analysis_workspace`; code inspection | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/ui/server.py` | |
| SEC-002 | No code authoring surface exists | API/LLM inspection | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract`; code inspection | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/llm/contract.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx` | |
| DATA-001 | Style source metadata is recorded | model/metadata tests | `python -m unittest tests.test_core_recipes tests.test_fastf1_gateway` | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/gateways/fastf1.py`; `tests/test_core_recipes.py`; `tests/test_fastf1_gateway.py` | |
| DATA-002 | Coverage bounds model works | model/API tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract` | `src/f1_telemetry_charts/recipes/parameters.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| DATA-003 | Track geometry model serializes | model/API tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract` | `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/types.ts`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| DATA-004 | Corner marker model works | model tests | `python -m unittest tests.test_track_geometry tests.test_fastf1_gateway` | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/types.ts`; `tests/test_track_geometry.py`; `tests/test_fastf1_gateway.py` | |
| DATA-005 | Playback frame model works | model/API tests | `python -m unittest tests.test_analysis_workspace` | `src/f1_telemetry_charts/analysis/playback.py`; `frontend/src/types.ts`; `tests/test_analysis_workspace.py` | |
| API-001 | Coverage endpoint works | FastAPI tests | `python -m unittest tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py` | |
| API-002 | Track map endpoint works | FastAPI tests | `python -m unittest tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `tests/test_analysis_workspace.py` | |
| API-003 | Range validation endpoint works | FastAPI tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract`; browser smoke check | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/ui/server.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| API-004 | Playback endpoint works | FastAPI tests | `python -m unittest tests.test_analysis_workspace` | `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py` | |
| UX-001 | Visual selection is primary for telemetry | browser/manual check | Browser smoke check for Track Selector in Add Chart and existing telemetry chart editing, with synchronized numeric distance controls | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; rebuilt `src/f1_telemetry_charts/ui/static/` assets | |
| UX-002 | Selector markers/segment/corners are clear | browser visual check | Browser smoke check confirmed trace, highlighted segment, start/end markers, reset/apply/cancel, and no mobile overflow | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; rebuilt `src/f1_telemetry_charts/ui/static/` assets | |
| UX-003 | Bounded input feedback is field-level | frontend/API tests | `pnpm --dir frontend typecheck`; `pnpm --dir frontend build`; browser smoke check | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; rebuilt `src/f1_telemetry_charts/ui/static/` assets | |
| UX-004 | Playback layout is work-focused | browser visual check | `pnpm --dir frontend typecheck`; `pnpm --dir frontend build`; browser smoke check | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; rebuilt `src/f1_telemetry_charts/ui/static/` assets | |
| UX-005 | Chart-range handoff preserves edits | frontend integration tests | `python -m unittest tests.test_analysis_workspace`; browser smoke check | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_analysis_workspace.py` | |
| UX-006 | Missing data states are concise | frontend fixture tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract`; browser smoke check | `src/f1_telemetry_charts/recipes/parameters.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |

## Test plan

- Unit tests for FastF1/session style resolution, deterministic style
  fallback, coverage-bound calculation, range validation, geometry extraction,
  corner projection, and playback interpolation.
- FastAPI tests for coverage, track map, range validation, playback, and LLM
  inspection endpoints.
- Recipe/rendering tests proving selected track segments affect telemetry
  chart data and exported metadata.
- Fixture tests for full geometry, missing circuit info, missing telemetry X/Y,
  missing position playback, sparse position samples, and partial-driver race
  coverage.
- Frontend tests or Playwright/manual checks for the track selector modal,
  corner selection, numeric synchronization, lap bounds, playback explorer,
  chart-range application, stale-state behavior, and responsive layouts.
- Payload-size and local-snapshot reuse checks for representative race sessions.
- Governance, spec, and drift validation before approval and before completion.

## Rollback plan

- Keep existing SPEC-006 numeric lap and distance controls as the fallback.
- If track-map geometry causes issues, disable the visual selector while
  preserving numeric range validation.
- If corner projection is unreliable, hide automatic corner shortcuts and keep
  manual visual selection.
- If playback is too slow or data-heavy, gate the playback explorer behind
  snapshot availability and keep bounded lap-range controls active.
- Preserve existing generated chart and preset compatibility by saving resolved
  numeric ranges even when the range originated from a visual selector.

## Approval and implementation decisions

- Approved by Nelson Jeanrenaud on 2026-07-23 in Codex task conversation with
  the note "I validate the specification as is."
- Implementation must proceed as full vertical production slices, not
  prototypes.
- Slice 1 is official styles and bounded numeric ranges.
- Slice 1 implementation started on 2026-07-23.
- Later slice decisions for corner padding and playback default mode were
  resolved before their implementation slices. Playback defaults to lap mode
  when lap and timestamp data are both available.

## Open questions

- [x] Should the first implementation slice include the race playback explorer,
      or should it ship official colors, bounded ranges, and telemetry
      track-segment selection first? Answer: split into vertical production
      slices. Slice 1 is official styles and bounded numeric ranges. Track-map
      selection, corner shortcuts, and race playback follow as separate
      vertical slices.
- [x] Should corner padding default to fixed meters, percentage of lap length,
      or a per-corner preset when available? Answer: fixed meters with
      editable before/after values, defaulting to 100 m each, because the
      telemetry range model is already distance-based and this remains
      predictable across sessions.
- [x] Should playback default to lap mode or session timestamp mode when both
      are available? Answer: lap mode by default, with timestamp mode exposed
      through an explicit switch only when the loaded snapshot has sufficient
      time-indexed position coverage.
- [x] What representative FastF1-backed session should be the visual/browser
      verification fixture for track-map work? Answer: the cached, normalized
      2023 Bahrain Grand Prix Race session. It is the shared browser and
      full-field baseline for SPEC-007 and SPEC-006. Synthetic fixtures remain
      responsible for unavailable geometry, sparse telemetry, and other
      degraded-state checks. The current 20-driver normalized dataset is
      `analyses/race-analysis/sessions/session-6129e831b8/dataset.json`.

## Human decisions required

- [x] Approve SPEC-007 scope as a new follow-up spec depending on SPEC-006.
      Answer: approved by Nelson Jeanrenaud on 2026-07-23.
- [x] Choose implementation slicing for track selector versus race playback.
      Answer: implement production vertical slices in this order: official
      styles and bounded numeric ranges; manual visual telemetry track segment
      selection; automatic corner selection; race playback explorer and chart
      lap-range handoff.
- [x] Choose default corner padding behavior. Answer: fixed-meter before/after
      padding with a 100 m default for each side and per-selection adjustment
      in the track selector.
- [x] Choose default playback mode when lap and timestamp data are both
      available. Answer: lap-first default; timestamp is an explicit available
      mode when snapshot coverage supports it.
- [x] Choose the representative FastF1-backed visual/browser fixture. Answer:
      the cached, normalized 2023 Bahrain Grand Prix Race session, approved by
      Nelson Jeanrenaud on 2026-08-03 in the Codex task conversation.

## Conflict check

SPEC-007 depends on SPEC-004, SPEC-005, and SPEC-006. It does not conflict with
SPEC-006's normalized parameter model because visual selection writes back to
the same chart range fields and records additional selector metadata. It
refines SPEC-006 style behavior by making FastF1/session-derived colors the
default source for built-in F1 series and forbidding random fallback colors.
It extends SPEC-006 preview behavior into a richer track-map analysis surface
without changing plugin trust boundaries or allowing code authoring.

## Traceability table

| Requirement ID | Design / component | Implementation (file/function) | Test | Status |
| -------------- | ------------------ | ------------------------------ | ---- | ------ |
| REQ-001 | Official style defaults | FastF1/session style metadata and recipe style resolver | `src/f1_telemetry_charts/data/gateways/fastf1.py`; `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_core_recipes.py`; `tests/test_fastf1_gateway.py` | Implemented in Slice 1 |
| REQ-002 | Style fallback diagnostics | Deterministic fallback palette with diagnostics metadata | `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_core_recipes.py` | Implemented in Slice 1 |
| REQ-003 | Session coverage bounds | Snapshot-derived lap/distance/time/map availability bounds | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented for Slice 1 bounds |
| REQ-004 | Bounded lap range controls | Backend bounds validation plus frontend min/max and diagnostics | `src/f1_telemetry_charts/analysis/workspace.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented in Slice 1 |
| REQ-005 | Bounded telemetry distance controls | Telemetry distance bounds validation plus frontend min/max and diagnostics | `src/f1_telemetry_charts/recipes/telemetry_trace.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_core_recipes.py`; `tests/test_analysis_workspace.py` | Implemented in Slice 1 |
| REQ-006 | Track geometry extraction | FastF1 position X/Y/Z capture, versioned equal-driver session median geometry with normalized-progress resampling and smooth seam closure, legacy snapshot rebuild, and downsampled projected map payload builder | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/track_geometry.py`; `src/f1_telemetry_charts/data/gateways/fastf1.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `tests/test_track_geometry.py`; `tests/test_fastf1_gateway.py`; `tests/test_analysis_workspace.py` | Implemented through AMEND-024 |
| REQ-007 | Visual telemetry range selector | Workbench telemetry Track Selector dialog is available during Add Chart draft creation and existing chart editing, with SVG trace, highlighted segment, start/end markers, sliders, numeric fields, reset/apply/cancel | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `frontend/src/api.ts`; `frontend/src/types.ts`; browser smoke check | Implemented in Slice 2 |
| REQ-008 | Automatic corner selector | FastF1 circuit info capture, projected corner markers, corner list, fixed-meter padding controls, and `corner_selector` selection metadata | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/gateways/fastf1.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_fastf1_gateway.py`; `tests/test_track_geometry.py`; `tests/test_analysis_workspace.py` | Implemented in Slice 3 |
| REQ-009 | Corner fallback behavior | Missing or unprojectable circuit metadata reports corner diagnostics while preserving manual visual distance selection | `src/f1_telemetry_charts/analysis/track_map.py`; `src/f1_telemetry_charts/recipes/parameters.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_track_geometry.py`; `tests/test_analysis_workspace.py` | Implemented in Slice 3 |
| REQ-010 | Range-to-chart synchronization | Selector writes normalized `analysis.distance_range_m` and `selection.track_segment`; saved chart regenerates and selector reopens from saved parameters | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py`; browser smoke check | Implemented in Slice 2 |
| REQ-011 | Track segment chart annotations | Telemetry chart metadata records selected `track_segment`, corner metadata when used, and synchronized `distance_range_m` in generated artifact JSON | `src/f1_telemetry_charts/recipes/telemetry_trace.py`; `tests/test_analysis_workspace.py` | Implemented through Slice 3 |
| REQ-012 | Race playback explorer | Snapshot-derived playback payload and Workbench Race Playback surface render canonical track map, car markers, current lap cursor, selected driver focus, and scrub controls | `src/f1_telemetry_charts/analysis/playback.py`; `src/f1_telemetry_charts/ui/server.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py` | Implemented in Slice 4 |
| REQ-013 | Time and lap playback modes | Time mode uses bounded session-time values; Lap mode uses bounded leader lap values snapped to leader lap-start timestamps; both modes render markers from shared session-time interpolation and remain manually scrubbed because automatic cursor advancement cannot keep pace with playback-frame generation | `src/f1_telemetry_charts/analysis/playback.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py`; browser smoke check | Implemented through AMEND-018 |
| REQ-014 | Position frame interpolation | Playback markers record exact/linear/nearest/missing interpolation status, maximum timestamp sample gap, sample gap seconds, and active/stale/missing marker state | `src/f1_telemetry_charts/analysis/playback.py`; `tests/test_analysis_workspace.py` | Implemented in Slice 4 |
| REQ-015 | Playback context details | Marker context includes FastF1 seconds/lap timing relations, pit/position context, persisted timing-app compound and tyre age with loaded-lap current-stint fallback, last/best lap, official last/best sectors, and inferred equal-distance minisector states anchored to official lap boundaries when sampled telemetry omits exact endpoints. With no selection, timing remains absolute; one selected driver preserves the shared-reference relative mode; two or more selected drivers preserve absolute values and highlight the fastest selected comparable cell in Race LAST, Laps LAST/BEST, Last Sectors S1/S2/S3/LAP, and Best Sectors S1/S2/S3/THEO, including all exact ties. Non-comparable position, interval, gap, and tyre-age columns are not ranked. Last-lap and minisector values distinguish slower, personal-best, and visible session-best states while normal UI hides provenance unless debug mode is enabled. A single selected driver colors equal-distance minisector intervals on the map; multiple selected drivers color official track sectors using the loaded color of the driver with the fastest selected last-sector time | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/gateways/fastf1.py`; `src/f1_telemetry_charts/analysis/playback.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_fastf1_gateway.py`; `tests/test_analysis_workspace.py`; browser smoke check | Implemented through AMEND-022 |
| REQ-016 | Playback-driven chart range selection | Normalized playback-interval parameter support remains in the backend, but AMEND-010 removes chart-range application controls from the Race Playback surface pending a future explicit workflow | `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_analysis_workspace.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; browser smoke check | UI workflow deferred by AMEND-010 |
| REQ-017 | Snapshot reuse | Bounds/style/map/corner/playback APIs read loaded snapshots only; no selector or playback path reloads FastF1 data | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `src/f1_telemetry_charts/analysis/playback.py`; `tests/test_analysis_workspace.py` | Implemented through Slice 4 |
| REQ-018 | Exported selection metadata | Chart metadata records style sources, coverage bounds, requested/effective ranges, selected track segment/corner metadata, and playback-derived interval metadata | `src/f1_telemetry_charts/recipes/`; `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_core_recipes.py`; `tests/test_analysis_workspace.py` | Implemented through Slice 4 metadata |
| REQ-019 | Graceful degraded modes | Coverage, track-map, and playback payloads report unavailable geometry/corners/timestamp/position states with reasons; UI preserves compatible controls | `src/f1_telemetry_charts/recipes/parameters.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `src/f1_telemetry_charts/analysis/playback.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py`; browser degraded-state check | Implemented through Slice 4 degraded states |
| REQ-020 | LLM-safe track-map inspection | LLM inspection exposes bounded coverage, corner availability, track-map summaries, and playback summaries without raw point/frame arrays; parameter updates remain backend validated | `src/f1_telemetry_charts/llm/contract.py`; `tests/test_llm_contract.py` | Implemented through Slice 4 summaries |
| NFR-001 | Interactive performance | Existing numeric range diagnostics and track selector remain responsive; playback now caches parsed snapshots and prepared indexes by immutable dataset hash, precomputes minisector inputs once, uses indexed timestamp lookup, and retains a bounded frame cache | `scripts/benchmark_playback.py`; `tests/test_playback_cache.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/analysis/playback.py`; benchmark against the canonical full-field Bahrain snapshot | Implemented through the 2026-09-02 performance remediation |
| NFR-002 | Payload bounds | Track map and playback payloads default to 500 map points, cap requested point/frame/marker counts, expose source counts/metadata, and omit raw unbounded telemetry from LLM summaries | `src/f1_telemetry_charts/analysis/track_map.py`; `src/f1_telemetry_charts/analysis/playback.py`; `src/f1_telemetry_charts/ui/server.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented through Slice 4 payloads |
| NFR-003 | Responsive usability | Race Playback browser-checked at 1280x720 with no document-level horizontal or vertical overflow, a 430 px desktop timing console, a 20-row timing field using one exact row height across all views, and compact direct comparison tabs without internal horizontal overflow; the 390x844 stacked surface retains no horizontal overflow | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; rebuilt `src/f1_telemetry_charts/ui/static/` assets; browser smoke check | Implemented through AMEND-015 |
| SEC-001 | Local snapshot boundary | Coverage and validation operate on open Analysis snapshots | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/ui/server.py`; `tests/test_analysis_workspace.py` | Implemented for Slice 1 |
| SEC-002 | No code authoring surface | Structured style, bounds, range, and LLM parameter APIs only | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/llm/contract.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx` | Implemented for Slice 1 |
| DATA-001 | Style source metadata | `StyleColor` and `SessionStyleMetadata` plus chart metadata `style_sources` | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_core_recipes.py`; `tests/test_fastf1_gateway.py` | Implemented in Slice 1 |
| DATA-002 | Coverage bounds model | Structured lap, distance, session-time, and track-map availability bounds | `src/f1_telemetry_charts/recipes/parameters.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented for Slice 1 |
| DATA-003 | Track geometry model | Backward-compatible Pydantic geometry with algorithm/aggregation/closure metadata plus bounded track map point, marker, segment, and payload models with deterministic projection and unavailable/invalid states | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/track_geometry.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/types.ts`; `tests/test_track_geometry.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented through AMEND-024 |
| DATA-004 | Corner marker model | Pydantic circuit corner/session circuit info plus projected track-map corner payload model | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/types.ts`; `tests/test_track_geometry.py`; `tests/test_fastf1_gateway.py` | Implemented in Slice 3 |
| DATA-005 | Playback frame model | Pydantic playback payload/frame/marker/context models plus persisted timing stream, explicit official lap relations, sparse timing-app records with deterministic current-stint tyre-age fallback, and track-length-derived minisector groups/states with official lap-boundary anchoring for normally sparse telemetry endpoints and matching frontend TypeScript types | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/gateways/fastf1.py`; `src/f1_telemetry_charts/analysis/playback.py`; `frontend/src/types.ts`; `tests/test_fastf1_gateway.py`; `tests/test_analysis_workspace.py` | Implemented through AMEND-019 |
| API-001 | Coverage endpoint | `GET /api/analysis/coverage` and LLM inspection coverage payload | `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/llm/contract.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented for Slice 1 |
| API-002 | Track map endpoint | `POST /api/analysis/track-map` returns bounded projected session geometry, corner markers, segment markers, bounds, counts, and diagnostics independent of selected-driver position coverage | `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `tests/test_analysis_workspace.py` | Implemented through Slice 3 |
| API-003 | Range validation endpoint | Diagnostics/create/update/generate/LLM paths share backend bounds validation and accept corner-derived distance ranges through the same `distance_range_m` contract | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/ui/server.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented through Slice 3 ranges |
| API-004 | Playback endpoint | `POST /api/analysis/playback` returns bounded lap playback payloads, mode availability, diagnostics, map points, frames, markers, and context through a snapshot-hash-invalidated prepared-data cache | `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/analysis/playback.py`; `tests/test_analysis_workspace.py`; `tests/test_playback_cache.py` | Implemented in Slice 4 and performance-remediated on 2026-09-02 |
| UX-001 | Primary visual distance selection | Add Chart and telemetry chart editor expose Track Selector action next to chart controls; applying visual selection updates existing numeric distance fields before save/generate | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; browser smoke check | Implemented in Slice 2 |
| UX-002 | Track-map selector ergonomics | SVG trace renders full lap, corner markers, highlighted selected segment, distinct start/end markers, range sliders, numeric fields, corner padding controls, reset/apply/cancel, and unavailable state | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; browser smoke check | Implemented through Slice 3 selector |
| UX-003 | Bounded input feedback | Min/max range fields, field diagnostics, invalid Save/Generate blocking | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; browser smoke check | Implemented in Slice 1 |
| UX-004 | Race playback explorer layout | Workbench Race Playback uses a viewport-bound map with a narrow 430 px floating timing console, 11px table typography, larger tyre icons, and exact 19px rows across Race, Laps, Last Sec, Best Sec, and Minis. Timing rows and map markers toggle membership in one shared multi-driver selection. Zero selections retain absolute mode, one selection uses relative mode, and multiple selections use absolute comparison mode with selected-fastest cells highlighted. Session-fastest, personal-fastest, and slower timing states use the centralized `#bd29c1`, `#31ce34`, and `#ddcd35` palette respectively. A single selected driver paints equal-distance Minis around the circuit; multiple selections divide the track by inferred official-sector boundaries and color S1/S2/S3 with each selected last-sector winner's driver/team color. Clicking any selected row or marker removes only that driver. Race uses explicit column widths, the cursor chip shares the title line, map controls occupy the canvas lower-left, and no separate All action is required. Session selection remains in the panel header and Time/Lap remains in the desktop vertical timeline rail; automatic playback controls are omitted because frame generation cannot support useful continuous playback | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `frontend/public/tyres/`; `src/f1_telemetry_charts/ui/server.py`; rebuilt `src/f1_telemetry_charts/ui/static/` assets; browser smoke check | Implemented through AMEND-023 |
| UX-005 | Chart-range handoff | AMEND-010 removes Chart Range, Chart, and Apply Range controls from Race Playback; existing normalized backend parameter support is retained for a future explicit workflow | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_analysis_workspace.py`; browser smoke check | UI workflow deferred by AMEND-010 |
| UX-006 | Degraded data states | Numeric/manual controls remain usable while unavailable map/corner/time states are explicit in coverage and selector payloads | `src/f1_telemetry_charts/recipes/parameters.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py`; browser smoke check | Implemented through Slice 3 |

## Implementation notes

- 2026-07-23: Draft created from human review requesting FastF1-defined
  driver/team colors, bounded lap ranges, a visual telemetry distance selector,
  automatic corner selection, and a future race map playback component.
- 2026-07-23: Public FastF1 documentation check confirms relevant sources:
  plotting helpers expose team/driver/compound styling; session API exposes
  `get_circuit_info()` with corner locations and track map rotation when
  available; telemetry and position data can provide GPS/X/Y coordinates.
- 2026-07-23: Recommended implementation slicing is:
  1. official style defaults and bounded lap/distance validation;
  2. track geometry, visual telemetry range selector, and corner shortcuts;
  3. race playback explorer and playback-driven chart range application.
- 2026-07-23: Human clarified that slices must be vertical production scopes,
  not prototypes. The spec now defines four slices with explicit completion
  gates. Slice 1 is official styles and bounded numeric ranges; manual visual
  track selection, automatic corner selection, and race playback are separate
  later slices.
- 2026-07-23: Slice 1 implementation is complete. Built-in charts now resolve
  FastF1/session style colors before deterministic fallbacks, expose
  snapshot-derived lap and telemetry distance coverage bounds, reject
  out-of-coverage numeric ranges across API/LLM/generation paths, show bounded
  field feedback in the Workbench, and persist style/bounds metadata in chart
  specs. Validation passed with full unittest discovery, frontend
  typecheck/build, browser smoke checks, governance validation, spec
  validation, and drift validation.
- 2026-07-23: Slice 2 implementation is complete. Telemetry snapshots now
  preserve FastF1 position X/Y/Z fields where available, the Analysis API
  exposes bounded downsampled track-map payloads, the Workbench telemetry chart
  editor includes a visual track-segment selector with markers, highlighted
  range, sliders, numeric synchronization, reset/apply/cancel, and unavailable
  geometry state, generated telemetry chart metadata records
  `selection.track_segment`, and LLM inspection includes bounded track-map
  summaries without raw point arrays. Validation passed with full unittest
  discovery, frontend typecheck/build, desktop and mobile browser checks,
  degraded no-geometry browser check, governance validation, spec validation,
  and drift validation.
- 2026-07-29: Slice 4 implementation is complete. The Analysis backend now
  builds bounded snapshot-derived playback payloads with lap-first mode
  selection, explicit timestamp degraded diagnostics, canonical track map
  points, frame/marker context, active/stale/missing interpolation semantics,
  and inferred local gap metadata. The Workbench now includes a Race Playback
  surface with map markers, lap scrubber, selected-driver focus, context
  panel, and chart lap-range handoff through normalized `selection.laps.range`
  plus `selection.playback_interval` metadata. LLM inspection includes bounded
  playback summaries without raw point or frame arrays.
- 2026-07-23: Slice 2 follow-up made the Track Selector available from the Add
  Chart form as soon as the selected template is Telemetry Trace and the target
  session is loaded. Browser smoke confirmed the selector opens before chart
  creation and writes the selected 50-150 m distance range into the draft
  numeric controls.
- 2026-07-23: Slice 2 follow-up changed the track-map base trace to persisted
  session-level canonical geometry. The selector no longer depends on the
  currently selected driver's positioned telemetry; it remains unavailable only
  when the loaded snapshot has no usable positioned lap from any loaded driver.
- 2026-07-23: Follow-up correction derives canonical geometry before session
  driver filtering for FastF1 and fixture loads. A session loaded for a driver
  without positioned telemetry can still use a canonical map from another
  loaded session driver while keeping chart telemetry scoped to the requested
  driver list.
- 2026-07-24: Slice 3 implementation is complete. FastF1 circuit corner
  metadata is persisted in loaded session snapshots, projected onto the
  canonical track map with explicit projection status, exposed through bounded
  track-map and coverage payloads, rendered as selectable markers in the Track
  Selector, and saved as `corner_selector` track segment metadata with editable
  fixed-meter before/after padding.
- 2026-08-03: AMEND-024 implementation replaces single-best-lap geometry with
  a two-stage coordinate median across clean full-coverage laps and equally
  weighted drivers. Geometry version 2 records aggregation and seam metadata,
  rebuilds legacy snapshots from stored telemetry, and applies a cubic
  smoothstep correction over the first/last 5% of the lap. Cached 2023 Bahrain
  Race verification used 889 laps from 20 drivers, produced a 200-point
  5,339.651 m trace, closed a 207.241-coordinate-unit raw endpoint gap exactly,
  and retained a 0.401-degree direction change at the seam. Both Track Selector
  and Race Playback rendered identical first/last coordinates; playback showed
  20 car markers with no browser console warnings or errors. Full unittest
  discovery passed with 101 tests, frontend typecheck passed, and governance,
  specification, and drift validation passed.
- 2026-08-03: The remaining verification-fixture question was resolved. The
  cached, normalized 2023 Bahrain Grand Prix Race session is the canonical
  visual/browser and full-field baseline shared with SPEC-006. Synthetic
  fixtures continue to cover unavailable geometry, sparse telemetry, and other
  degraded states. This verification-only decision does not change product
  behavior and requires no spec amendment.

## First slice implementation plan

This plan applies only after SPEC-007 is approved. No product code should be
changed while the spec remains Draft.

### Slice 1 target

Implement official style defaults and bounded numeric lap/distance ranges as a
complete vertical slice across the FastF1 gateway, normalized data model,
Analysis backend, diagnostics, LLM update path, frontend chart controls,
artifact metadata, and tests.

### Implementation steps

1. Inspect current style and range behavior in built-in recipes, parameter
   schema resolution, Analysis diagnostics, LLM update functions, FastF1
   gateway normalization, frontend `ParameterControl`, and generated artifact
   metadata.
2. Add style source modeling for driver/team/compound colors, including user
   override, FastF1/session source, and deterministic fallback source.
3. Update FastF1-backed data loading or style resolution so session-derived
   team/driver colors and compound colors are available without hidden reloads.
4. Replace any built-in random or implicit color defaults with official
   style-resolution calls and deterministic fallback diagnostics.
5. Add coverage bounds modeling for loaded lap range, driver-specific lap
   coverage, telemetry distance range, and missing/partial coverage reasons.
6. Expose coverage bounds through the local Analysis API and LLM inspection
   summary using bounded payloads.
7. Apply backend range validation consistently on diagnostics, chart create,
   chart update, LLM parameter updates, and generation; invalid ranges must
   return field-specific blocking errors.
8. Update frontend lap and numeric distance range controls to consume backend
   bounds, set min/max attributes, preserve exact numeric fine-tuning, and show
   field-level diagnostics.
9. Persist requested/effective style and range metadata in generated chart
   artifacts and Analysis export output.
10. Add tests for style source priority, deterministic fallbacks, coverage
    bounds, validation failures, partial per-driver coverage warnings,
    artifact metadata, API payloads, and LLM update rejection paths.
11. Run full relevant verification: targeted tests, full unittest discovery,
    frontend typecheck/build, browser smoke checks for chart controls,
    governance validation, spec validation, and drift validation.

### Files and areas expected to change

- `src/f1_telemetry_charts/data/models.py`
- `src/f1_telemetry_charts/data/gateways/fastf1.py`
- `src/f1_telemetry_charts/recipes/parameters.py`
- Built-in recipe modules under `src/f1_telemetry_charts/recipes/`
- Analysis workspace and API modules under `src/f1_telemetry_charts/analysis/`
  and `src/f1_telemetry_charts/ui/server.py`
- LLM contract module under `src/f1_telemetry_charts/llm/`
- Frontend chart configuration page/components under `frontend/src/`
- Tests under `tests/`

### Verification required before slice 1 is complete

- Unit/API tests prove official style priority and deterministic fallback
  diagnostics.
- Unit/API tests prove lap and distance range bounds reject invalid values in
  every save/update/generate/LLM path.
- Frontend build/typecheck passes.
- Browser smoke checks show bounded controls and no layout regression.
- Full unittest discovery passes.
- `python scripts\validate_governance.py`, `python scripts\validate_specs.py`,
  and `python scripts\validate_drift.py` pass.

## Spec amendments

> Required for any behavioral change after the spec is Approved.

### AMEND-001

- **Date:** 2026-07-28
- **Reason:** Second beta follow-up Group 2 found that Telemetry Trace Basic
  mode still exposes range-first controls and Track Selector remains separated
  from the distance range it edits. The driver selector also needs a distinct
  clear-all editing state rather than overloading an empty list as all drivers.
- **Changed requirements:** Refines UX-001, UX-002, UX-003, REQ-004,
  REQ-005, REQ-007, and API-003. Telemetry Trace Basic mode must expose a
  single lap selector that persists through the existing normalized lap range
  contract. Advanced mode keeps the full lap range. Track Selector entry points
  must sit next to distance range controls in Add Chart and chart edit flows.
  Track Selector visible UI must not show geometry provenance. Selected-driver
  controls must provide both all-select and clear-all actions, with explicit
  selected-mode empty lists validated as no selected drivers.
- **Behavioral impact:** Users configure the common Telemetry Trace case by
  choosing one lap in Basic mode, while advanced users can still edit a lap
  range. Empty selected-driver lists now mean no selected drivers in explicit
  selected mode instead of silently resolving to all drivers.
- **Test impact:** Add schema/normalization coverage for Telemetry single-lap
  Basic mode, selected-driver empty-list diagnostics, and existing chart
  generation with single-lap parameters. Add frontend typecheck/build and
  browser smoke coverage for Track Selector placement and no visible geometry
  provenance.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-28 with "Continue with Group 2".

### AMEND-002

- **Date:** 2026-07-29
- **Reason:** Second beta follow-up Group 3 found that async operations still
  lack consistent motion feedback, the chart editor layout gives parameter
  controls too much primary space, and the generated-chart summary cards
  duplicate information already present in controls and diagnostics.
- **Changed requirements:** Refines UX-001, UX-002, UX-003, and NFR-007.
  Async Workbench actions must show visible loading animation and prevent
  duplicate submission while their request is in flight. Existing chart
  editing must prioritize the rendered chart or empty preview in the primary
  content area and move chart options into a right-hand inspector/drawer on
  desktop, with a full-width stacked equivalent on mobile. The duplicate
  generated-chart summary card section must be removed; warnings and errors
  remain in diagnostics and generation state remains compact near chart
  actions.
- **Behavioral impact:** Users see deterministic busy feedback during
  create/open/save/load/add/generate/remove/review/export/plugin/history
  operations, and chart configuration no longer competes with the chart preview
  as the primary editing surface.
- **Test impact:** Add frontend typecheck/build and browser smoke coverage for
  loading affordances, chart options drawer placement, mobile stacked layout,
  and absence of the redundant summary labels.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-29 with "Perfect move on to group 3".

### AMEND-003

- **Date:** 2026-07-29
- **Reason:** Follow-up feedback on Group 3 clarified that the chart options
  right-hand inspector must be explicitly collapsible and resizable, not only
  moved into a fixed-width inspector.
- **Changed requirements:** Refines AMEND-002. The existing chart editor
  options inspector must support collapse/expand and bounded desktop resizing,
  while preserving the stacked mobile layout and stable Save/Generate/Remove
  action placement.
- **Behavioral impact:** Users can recover chart preview space by collapsing
  the options inspector or tune the inspector width for dense parameter
  editing on desktop.
- **Test impact:** Add frontend typecheck/build and browser smoke coverage for
  collapse/expand, bounded resize behavior, and no mobile overflow.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-29 with "make the chart option right-hand inspector collabsible and
  resizable".

### AMEND-004

- **Date:** 2026-07-29
- **Reason:** Follow-up feedback on AMEND-003 found redundant controls between
  the chart title line and the chart options inspector line, especially the
  generation-state chip and collapse control.
- **Changed requirements:** Refines AMEND-002 and AMEND-003. The existing
  chart editor must keep generation state near the chart title, expose a single
  top-level icon-only collapse/expand control for the options drawer, and avoid
  repeating generation state or collapse controls inside the options inspector.
  The right-hand options drawer remains side by side with the title-and-image
  primary column on desktop and stacked on mobile.
- **Behavioral impact:** The chart editor has one control location for drawer
  visibility and one visible generation-state chip near the chart name.
- **Test impact:** Add frontend typecheck/build and browser smoke coverage for
  the single title-level drawer toggle, absence of repeated drawer controls,
  retained generated chip near the title, and no mobile overflow.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-29 with feedback beginning "Remove the explicit icon controls."

### AMEND-005

- **Date:** 2026-07-29
- **Reason:** The previously deferred Slice 4 decision for default playback
  mode needed resolution before implementation.
- **Changed requirements:** Refines REQ-013 and UX-004. When lap and timestamp
  playback data are both available, the Race Playback explorer defaults to lap
  mode. Timestamp playback remains available through an explicit mode switch
  only when backend diagnostics report sufficient time-indexed position
  coverage in the loaded snapshot. AMEND-006 renames this UI mode to `Time` and
  clarifies the shared-timestamp marker semantics.
- **Behavioral impact:** Playback opens in the mode that directly matches the
  existing chart lap-range handoff model while preserving timestamp playback as
  an explicit supported mode for future snapshots with adequate time coverage.
- **Test impact:** Add API/frontend coverage for lap-first default, timestamp
  availability diagnostics, and chart range handoff from lap playback.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-29 with "Yes I agree with your recommentation for slice 4. You can
  make the plan" and "I approve, Implement it".

### AMEND-006

- **Date:** 2026-07-29
- **Reason:** Follow-up review clarified that lap-number playback is not a
  shared race moment. Displayed car positions must be resolved from session
  timestamps; otherwise all drivers can appear at the start line for the same
  lap number even when they are not physically there.
- **Changed requirements:** Refines REQ-013, REQ-014, DATA-005, API-004, and
  UX-004. The Race Playback explorer exposes `Time` and `Lap` modes. Time mode
  scrubs a bounded session-time cursor continuously. Lap mode snaps to the
  timestamp where the race leader starts the selected lap. Both modes generate
  car markers from the same timestamp-based interpolation path. The timeline
  shows leader lap-start indicators and provides zoom controls for finer
  timestamp selection.
- **Behavioral impact:** Lap mode remains the default, but it no longer means
  "show each driver on the same lap number." It means "show all selected
  drivers at the shared session timestamp corresponding to the leader starting
  this lap." Time mode is available when the snapshot contains time-indexed
  position samples.
- **Test impact:** Update playback API, LLM, frontend build, and browser smoke
  coverage for `Time`/`Lap` modes, leader lap-start markers, timestamp
  interpolation, no-time degraded states, and zoomable timeline controls.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-29 with feedback beginning "I think we should have timestamp based
  play back" and "Go forward with implementing this".

### AMEND-007

- **Date:** 2026-07-29
- **Reason:** Follow-up review of the Slice 4 playback map found that driver
  markers were not visually using the intended driver/team colors and that the
  map needed basic inspection controls before adding timing-table and overlay
  slices.
- **Changed requirements:** Refines REQ-012, REQ-015, UX-004, and NFR-003. Race
  Playback map markers must use loaded snapshot style colors in this order:
  FastF1/session driver style, session team color, FastF1/session team style,
  deterministic fallback. The map viewport must support zoom in/out, pan,
  rotate left/right, fit, and reset as presentation-only state. Driver markers
  must remain clickable after transforms, and clicking a marker sets the same
  focused-driver selection used by the panel.
- **Behavioral impact:** Playback data and cursor semantics do not change.
  Users can inspect the same playback frame with a transformed map view and can
  visually focus a driver directly from the map.
- **Test impact:** Add API coverage for playback marker color resolution and
  browser smoke coverage for non-black marker fills, zoom/pan/rotate/fit/reset
  controls, marker click focus, and mobile no-overflow behavior.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-29 with "Let's go" after the detailed "Playback Map Controls And
  Driver Colors" plan.

### AMEND-008

- **Date:** 2026-07-29
- **Reason:** Follow-up review of rotated playback maps found that driver
  labels became upside down at 180-degree rotation and that selected-driver
  emphasis could visually dominate the map at low zoom levels.
- **Changed requirements:** Refines UX-004 and NFR-003. Race Playback map
  driver labels must remain screen-readable while staying anchored to their
  transformed marker positions. Visible marker, label, stroke, and selection
  emphasis sizing must clamp inverse zoom compensation so low-zoom views do not
  create oversized dots or rings. Marker clickability must use a separate
  invisible hit target so the visible marker can stay compact without making
  selection difficult. When expanded marker hit targets overlap, the clicked
  position must resolve to the nearest visible marker in transformed map
  coordinates.
- **Behavioral impact:** Playback data, cursor semantics, driver focus, and map
  transforms do not change. The amendment only changes presentation and
  interaction hit testing for existing playback map markers and labels.
- **Test impact:** Add frontend/browser coverage for counter-rotated labels,
  compact selected-driver emphasis at low zoom, and marker click behavior
  through invisible hit targets.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-29 with "counter-rotate labels only and clamp the inverse scale and
  split visible marker size from click hitbox".

### AMEND-009

- **Date:** 2026-07-29
- **Reason:** Follow-up planning for the Race Playback timing tower clarified
  that FastF1 exposes race timing stream values for `GapToLeader` and
  `IntervalToPositionAhead` through `fastf1.api.timing_data()`. The playback
  timing tower should use these loaded timing values instead of deriving gaps
  from map marker distances.
- **Changed requirements:** Refines DATA-005, API-004, REQ-015, UX-004, and
  NFR-003. Loaded session snapshots gain optional normalized timing stream
  records containing session time, driver, position, gap to leader, interval to
  position ahead, source, and parse status metadata. Race Playback frames align
  timing stream records to the playback cursor using as-of timestamp semantics
  with an explicit maximum timing sample age. The playback payload exposes
  timing tower rows ordered by timing position first, with map/driver order as a
  deterministic fallback. The Workbench Race Playback surface replaces the
  selected-driver metric card with a timing tower whose row clicks and map
  marker clicks share focused-driver selection. With no focused driver, rows
  show FastF1 leader gaps and intervals to the car ahead. With a focused
  driver, rows additionally expose display-relative deltas computed from
  FastF1 leader-gap values when both drivers have fresh timing samples.
- **Behavioral impact:** Playback cursor and marker positioning semantics do
  not change. Timing data is loaded with the session and persisted in snapshots;
  opening or scrubbing Race Playback does not perform a hidden FastF1 fetch.
  Missing or stale timing stream samples degrade timing cells only; a marker can
  still be visible on the map while timing values are unavailable.
- **Test impact:** Add gateway coverage for FastF1 timing stream extraction,
  fixture coverage for persisted timing records, playback API tests for as-of
  timing alignment and focused-driver relative deltas, frontend build/typecheck,
  and browser smoke for timing-row/marker selection sync and degraded timing
  cells.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-29 with "Go ahead with implementation" after correcting the plan to
  use FastF1 timing stream gap and interval data.

### AMEND-010

- **Date:** 2026-07-30
- **Reason:** Human review of the initial Race Playback timing tower found that
  it still read as a debug/status panel instead of an analyst timing screen.
  The right-side chart application controls also competed with the timing
  context even though Race Playback does not currently own a chart-application
  workflow.
- **Changed requirements:** Refines DATA-005, REQ-015, REQ-016, UX-004, and
  NFR-003. The Race Playback right panel is dedicated to a compact timing tower
  and no longer exposes chart range, chart selection, or Apply Range controls.
  Frame context moves beside the playback timeline as a compact cursor chip.
  Normal timing rows use a thin driver/team color rail and three-letter driver
  abbreviation, and prioritize pit state, position, interval, gap to leader,
  tyre compound, tyre age, last lap, best lap, official last/best sector
  context, and mini-sector state placeholders. Marker/timing provenance such as
  active, stale, missing, interpolation method, sample age, and timing source is
  hidden unless the page is opened with the `debug` URL parameter enabled.
  Mini-sector cells expose state only and may use purple, green, yellow, or grey;
  until a comparison reference is approved they remain grey/unavailable and no
  mini-sector time values are shown. Driver and row selection remain
  synchronized and never filter other map markers.
- **Behavioral impact:** Race Playback becomes a focused inspection surface.
  Existing chart parameters and generated charts are unchanged; the prior
  range-application helper remains outside this surface for a future explicit
  workflow. Missing timing, lap, tyre, or sector data degrades only the
  corresponding cells. Rare pit badges may appear in normal mode; debug-only
  provenance is available through `?debug`, `?debug=1`, or `?debug=true`.
- **Test impact:** Add playback payload coverage for as-of lap, tyre-age,
  last/best lap, and official sector context; frontend typecheck/build; browser
  smoke for the cursor chip, compact timing rows, color rail, normal/debug
  provenance behavior, row/marker focus synchronization, and desktop/mobile
  overflow.
- **Deferred:** Computed mini-sector comparisons require a separately approved
  reference rule. Race-control, penalty, and track-limit text parsing remains
  optional follow-up work because the source is private and message parsing is
  fragile.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-30 with "Implement the live timing tower column redesign task. You
  have leeway in implementation but it must respect the original needs," using
  `docs/reports/SPEC-007-timing-tower-redesign-handoff.md` as the design
  handoff.

### AMEND-011

- **Date:** 2026-07-30
- **Reason:** Human review of AMEND-010 found that unavailable mini-sector
  placeholders made every race row too tall, tyre codes lacked the supplied
  compound artwork, leader-relative comparison failed at normal start/finish
  transitions, and lap/sector comparison required tiresome per-driver
  expansion.
- **Changed requirements:** Refines DATA-005, REQ-015, UX-004, and NFR-003.
  Race Playback uses the map as the primary desktop canvas with a collapsible
  timing console floating above it; mobile uses the same console as a
  full-width stacked surface. The console provides field-wide `Race`, `Lap
  Times`, `Sectors`, and `Mini Sectors` views. Race rows are single-line and
  compact. Lap Times shows every driver's last and best completed laps plus
  deltas to the fastest visible values. Sectors provides `Last` and `Best`
  sub-views for all drivers; Best includes theoretical best from the sum of
  each driver's best three official sectors. Driver selection remains
  map/tower focus only and does not gate comparison data.
- **Relative timing correction:** Cars on adjacent displayed lap numbers at a
  shared cursor remain seconds-comparable when official timing gaps are
  available. The known cursor/timing leader is a valid zero-gap anchor even
  when FastF1 has not recently repeated its sparse leader row. A lap-number
  difference caused only by straddling start/finish must never display as a
  lap deficit. Signed lap deficits may be shown only when the official timing
  source explicitly reports a lap relationship; map distance is never used to
  invent timing.
- **Mini-sector inference:** Mini sectors are computed from loaded snapshot
  telemetry with no hidden FastF1 fetch. The circuit lap distance determines a
  target count using approximately 200 metres per mini sector, clamped to a
  bounded 15–40 segments; the final boundaries divide the full lap into exactly
  equal-distance bins. Official S1/S2 grouping boundaries are inferred by
  aligning completed-lap official sector timing to distance-indexed telemetry.
  The UI does not number mini sectors; it renders slim vertical state lines
  with slightly larger gaps only at the S1/S2 group boundaries. For each
  driver's latest completed lap at the cursor, purple means fastest visible
  segment, green means that driver's personal-best segment, yellow means slower
  than personal best, and grey means unavailable.
- **Tyre artwork:** The timing console uses the human-provided SVG compound
  icons for Soft, Medium, Hard, Intermediate, and Wet, with tyre age adjacent
  and accessible compound labels retained.
- **Test impact:** Add analytics tests for equal-distance boundaries, inferred
  official-sector groups, state classification, and sparse-leader relative
  timing; add frontend checks for all comparison schemas, supplied tyre icons,
  overlay collapse/focus behavior, and desktop/mobile overflow.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-30 with "You can implement everything we talked about I validate it,"
  plus the explicit instruction that mini sectors be equal-distance,
  track-length-derived, grouped by official sectors, unnumbered, and rendered
  as slightly grouped colored vertical lines.

### AMEND-012

- **Date:** 2026-07-30
- **Reason:** Human review of the floating timing console found that the
  horizontal timeline and duplicated focus/session controls still consumed too
  much vertical space, while timing rows remained too tall to inspect enough of
  the field at once.
- **Changed requirements:** Refines UX-004 and NFR-003. On desktop, Race
  Playback places a compact vertical timeline rail to the right of the
  map/timing canvas. The `Time`/`Lap` mode actions and timeline zoom/fit actions
  live with that rail. On smaller screens the timeline remains horizontal and
  stacked to preserve touch usability. Session selection moves into the Race
  Playback panel header. The separate Driver focus selector is removed because
  map markers, timing rows, and the timing console `All` action fully own focus.
  Map height expands into the reclaimed space, and all timing comparison rows
  use tighter vertical sizing while retaining readable values and click
  targets.
- **Behavioral impact:** Playback cursor, timing, comparison, and selection
  semantics do not change. This amendment only consolidates controls and
  reallocates page space so more timing rows and more of the map remain visible.
- **Test impact:** Update frontend typecheck/build and browser smoke coverage
  for header session selection, absent Driver focus control, desktop vertical
  timeline placement and mode actions, compact timing rows, expanded map
  canvas, mobile horizontal timeline, and desktop/mobile overflow.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-30 with the explicit request to move the timeline to a right-side
  vertical rail, colocate Time/Lap with it, remove Driver focus, place Session
  beside the Race Playback title, and reduce row padding.

### AMEND-013

- **Date:** 2026-07-30
- **Reason:** Human review of AMEND-012 found that the minimum-height map made
  the whole page scroll, timing typography was still undersized despite unused
  row space, view schemas did not align consistently, the sector sub-mode row
  consumed vertical space, and the fastest-lap label was abbreviated.
- **Changed requirements:** Refines UX-004 and NFR-003. Desktop Race Playback
  sizes the map/timeline canvas from the available viewport without imposing a
  page-height overflow. The cursor chip floats inside the canvas rather than
  adding document height. Standard timing rows become shorter while their
  primary typography becomes larger. Every timing view uses a consistent
  color-rail, position, and driver prefix; PIT state is shown inside the driver
  cell rather than shifting Race columns. `Last Sectors` and `Best Sectors`
  become separate entries in the main timing-view navigation, eliminating the
  sector sub-mode row. Fastest lap comparison copy reads `FASTEST`.
- **Behavioral impact:** Timing values, sector references, focus, and playback
  cursor semantics do not change. The update only improves density,
  consistency, naming, and viewport fit.
- **Test impact:** Update frontend typecheck/build and browser checks for no
  desktop page-height overflow at the standard viewport, larger timing text,
  full 20-car fit, aligned view prefixes, direct Last/Best Sectors tabs,
  `FASTEST` copy, and retained mobile no-overflow behavior.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-30 with the explicit requests to replace `FAST` with `FASTEST`,
  prevent vertical page overflow, increase timing typography while reducing
  row height, align timing-table layouts, and remove the separate sector
  sub-mode row.

### AMEND-014

- **Date:** 2026-07-30
- **Reason:** Human review of AMEND-013 found that timing values still needed
  more visual weight, Race columns distributed horizontal space poorly,
  selection clearing required a separate action, tyre age could disappear
  when live timing-app rows omitted `TotalLaps`, and last-lap performance state
  was not visually encoded.
- **Changed requirements:** Refines DATA-005, REQ-015, UX-004, and NFR-003.
  Timing rows use larger typography and one exact shared height across Race,
  Lap Times, Last Sectors, Best Sectors, and Mini Sectors. Race column widths
  are explicit so unused flexible width does not accumulate between driver and
  interval. Tyre icons become larger. Tyre age prefers live timing-app
  `TotalLaps` and otherwise infers a bounded current-stint age from loaded lap
  and stint data. Last-lap values use yellow when slower than the driver's
  personal best, orange when equal to personal best, and purple when equal to
  the visible session best. Clicking the already-focused driver in either the
  map or tower clears focus, replacing the timing-console `All` action. Map
  controls move to the lower-left of the canvas and the cursor information chip
  moves onto the Race Playback title line.
- **Behavioral impact:** Driver focus becomes a toggle but remains a single
  shared selection across map and tower. Tyre-age inference is a display
  fallback only and does not mutate snapshot source data. Timing comparisons
  and playback cursor semantics remain unchanged.
- **Test impact:** Add backend coverage for timing-app tyre age and inferred
  current-stint fallback; update frontend typecheck/build and browser checks for
  exact cross-view row height, larger typography/icons, last-lap color states,
  compact Race column distribution, title-line cursor chip, bottom-left map
  controls, absent `All` action, and map/tower focus toggling.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-30 through the explicit implementation request for these timing-tower
  refinements.

### AMEND-015

- **Date:** 2026-07-31
- **Reason:** Human review of AMEND-014 found that the floating console still
  obscured too much of the map and that selecting a driver only made race gap
  relative while the rest of the timing views retained absolute values.
- **Changed requirements:** Refines REQ-015, UX-004, and NFR-003. The desktop
  timing console becomes materially narrower and uses shorter comparison-tab
  labels plus compact per-view column schemas. With no selected driver, views
  retain their field-wide absolute and fastest-visible comparison behavior.
  With a selected driver, that driver becomes the shared reference across all
  comparable values: Race interval, race gap, tyre age, and last lap; Lap
  Times last and best lap; Last Sectors S1/S2/S3 and last lap; and Best Sectors
  S1/S2/S3 and theoretical best. The reference row renders `REF`; other rows
  render signed deltas where positive means a greater value (slower for times,
  older for tyre age) and negative means a smaller value. Tyre compound icons,
  position, driver identity, pit state, and unavailable values remain absolute
  because they have no meaningful numeric relative form. Mini-sector state
  lines remain their already-relative qualitative comparison view.
- **Behavioral impact:** Relative mode is now console-wide rather than limited
  to race gap. Clearing focus restores the previous absolute/global comparison
  presentation without changing the playback cursor or source data.
- **Test impact:** Update frontend typecheck/build and browser checks for the
  reduced desktop width, compact tabs and schemas, reference-row `REF` values,
  signed deltas across Race/Lap Times/Last Sectors/Best Sectors, focus clearing
  back to absolute values, exact row-height retention, and desktop/mobile
  overflow.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-07-31 through the explicit implementation request to reduce timing-tower
  width and make all timing values relative to the selected driver.

### AMEND-016

- **Date:** 2026-08-03
- **Reason:** Human review found the unfocused Laps deltas redundant with
  selecting the comparison driver and found the equal-age focused tyre state
  visually over-emphasized.
- **Changed requirements:** Refines REQ-015 and UX-004. In unfocused mode, the
  Laps view shows only each driver's absolute last lap and best lap; it no
  longer adds field-fastest delta columns. Focused mode continues to replace
  those values with signed selected-driver deltas. In focused Race view, a
  zero-lap tyre-age delta uses the neutral/default text tone instead of the
  purple equal-time comparison tone. The selected reference row remains
  visually distinct as `REF`.
- **Behavioral impact:** The Laps view is less repetitive and narrower in its
  information density. Equal tyre ages read as neutral rather than exceptional.
- **Test impact:** Update frontend typecheck/build and browser checks for the
  five-column unfocused Laps schema and neutral focused `0L` tyre-age state.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-08-03 through the explicit request to remove unfocused Laps deltas and
  neutralize equal focused tyre ages.

### AMEND-017

- **Date:** 2026-08-03
- **Reason:** Human review rejected relative interval subtraction and requested
  automatic playback with shared speed control.
- **Changed requirements:** Refines REQ-013, REQ-015, and UX-004. Focused Race
  mode retains the `INT` column but renders `—` for every driver because local
  intervals to different cars ahead are not comparable to the selected driver.
  Race Playback adds a title-line play/pause action beside the cursor status
  chip and a shared `1×`, `2×`, `4×`, `8×`, `16×` speed selector. Lap mode
  advances one lap every five seconds at `1×`, divided by the selected speed.
  Time mode advances by elapsed real time multiplied by the selected speed.
  Playback stops at the available range end; starting again at the end restarts
  from the range minimum. Session or mode changes pause playback.
- **Behavioral impact:** Analysts can watch the race progress without manual
  scrubbing while focused interval values no longer imply a false comparison.
- **Test impact:** Update frontend typecheck/build and browser checks for
  focused `INT` placeholders, play/pause state, Lap and Time cursor advancement,
  speed selection, end-of-range behavior, and viewport containment.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-08-03 through the explicit focused-INT and playback-control request.

### AMEND-018

- **Date:** 2026-08-03
- **Reason:** Human evaluation found automatic playback unusable because each
  cursor step requires a playback-frame regeneration that cannot keep pace
  with continuous Lap or Time advancement.
- **Changed requirements:** Supersedes only the automatic-player portion of
  AMEND-017. Remove the title-line play/pause action, speed selector, playback
  timers, and automatic cursor advancement. Preserve manual Lap/Time timeline
  scrubbing, the title-line cursor status chip, and focused `INT` placeholders.
- **Behavioral impact:** Race Playback returns to explicit analyst-controlled
  cursor changes and avoids generating a backlog of playback requests.
- **Test impact:** Update frontend typecheck/build and browser checks to confirm
  the player/speed controls are absent, manual timeline controls remain, and
  the page retains desktop/mobile containment.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-08-03 through the explicit request to scrap automatic playback because
  generation speed made it unusable.

### AMEND-019

- **Date:** 2026-08-03
- **Reason:** Human requested completion of the Minis tab. Real-session
  verification found that FastF1 lap telemetry commonly starts after 0 m and
  ends before the inferred full track length, causing otherwise valid completed
  laps to be rejected and the tab to remain empty.
- **Changed requirements:** Refines DATA-005, REQ-015, and UX-004. Equal-distance
  minisectors continue to derive from inferred track length and remain grouped
  by official sectors 1/2/3. When telemetry samples do not reach exact lap
  endpoints, use the official lap start/end times as virtual 0 m/full-length
  anchors before interpolating minisector durations. The Minis tab renders the
  latest completed lap as unnumbered colored vertical lines: purple for visible
  session best, green for personal best, orange for slower, and grey only when
  data is genuinely unavailable. Sector groups are separated by a larger gap.
- **Behavioral impact:** Valid real-session telemetry now produces useful
  minisector strips instead of being discarded for normal sampling gaps.
- **Test impact:** Add endpoint-anchoring regression coverage, rerun playback
  tests, frontend typecheck/build, and browser checks on a later real race lap
  for populated states, sector grouping, row height, and overflow.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-08-03 through the explicit request to implement the minisector tab.

### AMEND-020

- **Date:** 2026-08-03
- **Reason:** Human review requested that selecting a driver connect the Minis
  comparison directly to circuit geography instead of limiting it to the
  timing row.
- **Changed requirements:** Refines REQ-015 and UX-004. While a driver is
  focused, split the displayed circuit into the same equal-distance intervals
  as that driver's latest completed-lap minisector states. Interpolate each
  interval boundary against track-map distance and color the corresponding
  circuit portion purple for visible session best, green for personal best,
  orange for slower, and grey for unavailable. With no focused driver, retain
  the neutral track trace.
- **Behavioral impact:** Selecting a timing row or map marker immediately shows
  where the focused driver's latest lap gained or lost performance around the
  circuit; clearing the driver restores the uncluttered map.
- **Test impact:** Run frontend typecheck/build and browser checks for selected
  driver map overlays, equal interval boundaries, state/color parity, focus
  clearing, map controls, and desktop/mobile containment.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-08-03 through the explicit request to color the selected driver's track
  portions from the last minisector states.

### AMEND-021

- **Date:** 2026-08-03
- **Reason:** Human review supplied the exact performance-state palette and
  requested consistent use wherever those semantic timing colors appear.
- **Changed requirements:** Refines REQ-015 and UX-004. Use `#bd29c1` for a
  visible session-fastest lap, sector, or minisector; use `#31ce34` for a
  personal-fastest lap, sector, or minisector; and use `#ecf34e` for a slower
  lap, sector, or minisector. Apply the same centralized palette to the timing
  table, Minis strips, and selected-driver circuit overlay. Do not recolor
  unrelated UI accents, warnings, relative-reference deltas, or track-selector
  corner highlights that do not carry these meanings.
- **Behavioral impact:** Performance colors remain identical across textual
  timing values, compact Minis lines, and geographic track-map segments.
- **Test impact:** Run frontend typecheck/build and browser checks that inspect
  computed colors for session-fastest, personal-fastest, and slower states.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-08-03 through the explicit exact-color request.

### AMEND-022

- **Date:** 2026-08-03
- **Reason:** Human requested simultaneous driver comparison in the Live timing
  tower and a geographic summary of which selected driver owns each official
  sector on the latest completed lap.
- **Changed requirements:** Refines REQ-015 and UX-004. Timing rows and map
  markers toggle membership in a shared driver selection. Zero selected drivers
  retain absolute/global timing, one selected driver retains existing relative
  semantics, and two or more selected drivers activate absolute comparison
  mode. Highlight the fastest selected comparable values for Race `LAST`, Laps
  `LAST`/`BEST`, Last Sectors `S1`/`S2`/`S3`/`LAP`, and Best Sectors
  `S1`/`S2`/`S3`/`THEO`; highlight all ties within timing tolerance. Do not rank
  position, interval, gap, or tyre age. In multi-select mode, infer official
  S1/S2/S3 distance boundaries from the existing equal-distance minisector
  groups, falling back to equal thirds only when grouping is unavailable, and
  color each track sector using the loaded color of the selected driver with
  the fastest last-sector time for that sector. Single selection keeps the
  existing minisector-state circuit overlay.
- **Behavioral impact:** Analysts can compare a subset without hiding the rest
  of the field, see the selected winner in every meaningful timing column, and
  immediately identify sector ownership on the circuit.
- **Test impact:** Run frontend typecheck/build and browser interaction checks
  for additive row/map selection, single-relative and multi-absolute mode
  transitions, cell winners, ties, three sector owners/colors, deselection,
  map controls, and desktop/mobile containment.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-08-03 through the explicit multi-selection and sector-map request.

### AMEND-023

- **Date:** 2026-08-03
- **Reason:** Human visual review requested a darker, less fluorescent yellow
  for slower timing states.
- **Changed requirements:** Refines UX-004 and supersedes only the slower-color
  value in AMEND-021. Replace `#ecf34e` with `#ddcd35` everywhere the semantic
  timing palette represents a slower lap, sector, minisector, or focused map
  interval. Session-fastest remains `#bd29c1` and personal-fastest remains
  `#31ce34`.
- **Behavioral impact:** Only slower-state presentation changes; timing,
  comparison, selection, and map-segmentation semantics remain unchanged.
- **Test impact:** Frontend typecheck/build, compiled palette inspection, and
  browser visual/console verification.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-08-03 through the explicit instruction to change yellow to `#ddcd35`.

### AMEND-024

- **Date:** 2026-08-03
- **Reason:** Human review found that canonical geometry derived from one GPS
  lap leaves a visible start/finish offset and preserves one driver's racing
  line as the session map. The requested map favors a stable neutral circuit
  trace over exact reproduction of one positioned lap.
- **Changed requirements:** Refines REQ-006 and DATA-003. Canonical session
  geometry must prefer a deterministic two-stage coordinate median built from
  clean, full-coverage positioned laps: first across each driver's accepted
  laps and then across drivers with equal driver weight. Accepted laps are
  resampled by normalized lap progress before aggregation. The resulting trace
  must use median accepted lap span for distance and must close its
  start/finish seam with a local smooth correction. Geometry metadata must
  identify its algorithm version, aggregation method, contributing
  driver/lap counts, original closure gap, and closure-correction status.
  Legacy single-lap geometry must be rebuilt from telemetry already present in
  a loaded snapshot when possible, without fetching FastF1 data.
- **Behavioral impact:** Track Selector and Race Playback share a smoother,
  driver-neutral, closed circuit trace. Position samples and analytical
  telemetry distances remain unchanged; only derived canonical map geometry
  and its source metadata change.
- **Test impact:** Add deterministic model coverage for input filtering,
  normalized resampling, per-driver/session medians, equal driver weighting,
  seam closure, fallback behavior, metadata, and legacy rebuild. Re-run track
  map, playback, FastF1 gateway, full repository, governance, specification,
  drift, and cached Bahrain browser verification.
- **Human approval reference:** Approved by Nelson Jeanrenaud in Codex on
  2026-08-03 through the explicit request to implement the Median Session
  Track Geometry plan.

## 2026-09-02 Performance remediation evidence

The approved NFR-001 behavior was restored without changing playback semantics.
The local API now opens only workspace metadata for a playback request, caches
the validated `SessionDataset` by immutable snapshot hash, prepares sorted
driver/lap/timing indexes and equal-distance minisector inputs once per
snapshot, performs binary position/timing lookups, and retains up to 128 bounded
payloads across up to four prepared snapshots.

On the canonical 2023 Bahrain Race snapshot with 20 drivers, 1,056 laps, 56,998
telemetry samples, and 28,475 timing records, the benchmark measured a 0.6260
second cold initial request, a 0.0166 second median across subsequent distinct
lap requests, and a 0.0097 second repeated-frame request. The pre-change
diagnostic measured 3.758 seconds median for in-process workspace open plus
playback and 4.673 seconds through FastAPI TestClient on the same machine.

Evidence commands:

- `python scripts/benchmark_playback.py analyses/race-analysis --session-id session-6129e831b8 --laps 1,2,10,30,57,30`
- `python -m unittest tests.test_playback_cache`

## Review checklist

- [x] spec_id is unique and follows the SPEC-XXX format.
- [x] Every requirement has an ID, statement, rationale, acceptance criteria,
      verification method, and evidence location.
- [x] Non-goals are listed.
- [x] Open questions are resolved or explicitly deferred.
- [x] Verification matrix covers every requirement.
- [x] Conflict check completed.
- [x] Human approval recorded before status set to Approved.
