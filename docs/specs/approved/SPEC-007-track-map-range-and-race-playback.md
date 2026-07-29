---
doc_type: spec
spec_id: SPEC-007
title: Visual Track Map Range Selection and Race Playback Explorer
status: In Implementation
owner: Nelson Jeanrenaud
related_issue:
related_prs: []
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
last_verified_at: 2026-07-24
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

### REQ-013: Lap and timestamp playback modes

- **Statement:** The playback explorer must support both lap-based scrubbing
  and session timestamp scrubbing where the underlying snapshot contains enough
  data.
- **Rationale:** Analysts may choose race phases by lap number or by real
  session timeline.
- **Acceptance criteria:** The UI exposes a clear mode switch; lap mode uses
  bounded lap values; timestamp mode uses bounded session-time values; modes
  are disabled with diagnostics when required source data is missing.
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
| REQ-008 | Corner shortcuts resolve ranges | model/UI tests | TBD | TBD | |
| REQ-009 | Missing corners degrade cleanly | API/UI tests | TBD | TBD | |
| REQ-010 | Visual selection syncs to chart params | frontend/API tests | `python -m unittest tests.test_analysis_workspace`; browser smoke check for apply/save/generate/reopen | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py` | |
| REQ-011 | Segment metadata/annotations export | renderer/metadata tests | `python -m unittest tests.test_analysis_workspace`; generated metadata fixture inspection in test | `src/f1_telemetry_charts/recipes/telemetry_trace.py`; `tests/test_analysis_workspace.py` | |
| REQ-012 | Playback explorer renders positions | frontend/API tests | TBD | TBD | |
| REQ-013 | Lap and timestamp modes are bounded | API/frontend tests | TBD | TBD | |
| REQ-014 | Interpolation semantics are explicit | unit tests | TBD | TBD | |
| REQ-015 | Playback context details are available | API/frontend tests | TBD | TBD | |
| REQ-016 | Playback interval applies to chart range | integration tests | TBD | TBD | |
| REQ-017 | Snapshot reuse avoids implicit reloads | service tests/benchmark | `python -m unittest tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py` | |
| REQ-018 | Exported metadata preserves selections | metadata tests | `python -m unittest tests.test_core_recipes tests.test_analysis_workspace`; browser smoke check | Built-in recipe metadata in `src/f1_telemetry_charts/recipes/`; `tests/test_core_recipes.py`; `tests/test_analysis_workspace.py` | |
| REQ-019 | Degraded modes are graceful | API/frontend tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract`; browser degraded-state check | Coverage availability reasons in `src/f1_telemetry_charts/recipes/parameters.py`; track-map unavailable payload in `src/f1_telemetry_charts/analysis/track_map.py`; UI degraded state in `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| REQ-020 | LLM inspection is bounded and safe | LLM contract tests | `python -m unittest tests.test_llm_contract` | `src/f1_telemetry_charts/llm/contract.py`; `tests/test_llm_contract.py` | |
| NFR-001 | Selector/playback interactions are responsive | benchmark/manual check | Browser smoke check for existing numeric-range and track-selector interactions | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/analysis/track_map.py` | |
| NFR-002 | Map/playback payloads are bounded | API tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract` | `src/f1_telemetry_charts/analysis/track_map.py`; `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/llm/contract.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| NFR-003 | UI works on desktop and mobile widths | browser screenshots/manual checks | Browser smoke check at default desktop viewport and 390x844 mobile viewport | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; rebuilt `src/f1_telemetry_charts/ui/static/` assets | |
| SEC-001 | Endpoints stay inside open Analysis | API security tests | `python -m unittest tests.test_analysis_workspace`; code inspection | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/ui/server.py` | |
| SEC-002 | No code authoring surface exists | API/LLM inspection | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract`; code inspection | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/llm/contract.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx` | |
| DATA-001 | Style source metadata is recorded | model/metadata tests | `python -m unittest tests.test_core_recipes tests.test_fastf1_gateway` | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/gateways/fastf1.py`; `tests/test_core_recipes.py`; `tests/test_fastf1_gateway.py` | |
| DATA-002 | Coverage bounds model works | model/API tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract` | `src/f1_telemetry_charts/recipes/parameters.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| DATA-003 | Track geometry model serializes | model/API tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract` | `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/types.ts`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| DATA-004 | Corner marker model works | model tests | TBD | TBD | |
| DATA-005 | Playback frame model works | model/API tests | TBD | TBD | |
| API-001 | Coverage endpoint works | FastAPI tests | `python -m unittest tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py` | |
| API-002 | Track map endpoint works | FastAPI tests | `python -m unittest tests.test_analysis_workspace`; browser smoke check | `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `tests/test_analysis_workspace.py` | |
| API-003 | Range validation endpoint works | FastAPI tests | `python -m unittest tests.test_analysis_workspace tests.test_llm_contract`; browser smoke check | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/ui/server.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | |
| API-004 | Playback endpoint works | FastAPI tests | TBD | TBD | |
| UX-001 | Visual selection is primary for telemetry | browser/manual check | Browser smoke check for Track Selector in Add Chart and existing telemetry chart editing, with synchronized numeric distance controls | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; rebuilt `src/f1_telemetry_charts/ui/static/` assets | |
| UX-002 | Selector markers/segment/corners are clear | browser visual check | Browser smoke check confirmed trace, highlighted segment, start/end markers, reset/apply/cancel, and no mobile overflow | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; rebuilt `src/f1_telemetry_charts/ui/static/` assets | |
| UX-003 | Bounded input feedback is field-level | frontend/API tests | `pnpm --dir frontend typecheck`; `pnpm --dir frontend build`; browser smoke check | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; rebuilt `src/f1_telemetry_charts/ui/static/` assets | |
| UX-004 | Playback layout is work-focused | browser visual check | TBD | TBD | |
| UX-005 | Chart-range handoff preserves edits | frontend integration tests | TBD | TBD | |
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
- Later slice decisions for corner padding and playback default mode are
  explicitly deferred until before Slice 3 and Slice 4 respectively; they do
  not block Slice 1 approval or implementation.

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
      are available? Answer: deferred until before Slice 4, because playback is
      out of scope for earlier slices.
- [ ] What representative FastF1-backed session should be the visual/browser
      verification fixture for track-map work?

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
      available. Answer: deferred until before Slice 4.

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
| REQ-006 | Track geometry extraction | FastF1 position X/Y/Z capture, persisted session-level canonical track geometry, and downsampled projected map payload builder | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/track_geometry.py`; `src/f1_telemetry_charts/data/gateways/fastf1.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `tests/test_track_geometry.py`; `tests/test_fastf1_gateway.py`; `tests/test_analysis_workspace.py` | Implemented in Slice 2 |
| REQ-007 | Visual telemetry range selector | Workbench telemetry Track Selector dialog is available during Add Chart draft creation and existing chart editing, with SVG trace, highlighted segment, start/end markers, sliders, numeric fields, reset/apply/cancel | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `frontend/src/api.ts`; `frontend/src/types.ts`; browser smoke check | Implemented in Slice 2 |
| REQ-008 | Automatic corner selector | FastF1 circuit info capture, projected corner markers, corner list, fixed-meter padding controls, and `corner_selector` selection metadata | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/gateways/fastf1.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_fastf1_gateway.py`; `tests/test_track_geometry.py`; `tests/test_analysis_workspace.py` | Implemented in Slice 3 |
| REQ-009 | Corner fallback behavior | Missing or unprojectable circuit metadata reports corner diagnostics while preserving manual visual distance selection | `src/f1_telemetry_charts/analysis/track_map.py`; `src/f1_telemetry_charts/recipes/parameters.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_track_geometry.py`; `tests/test_analysis_workspace.py` | Implemented in Slice 3 |
| REQ-010 | Range-to-chart synchronization | Selector writes normalized `analysis.distance_range_m` and `selection.track_segment`; saved chart regenerates and selector reopens from saved parameters | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py`; browser smoke check | Implemented in Slice 2 |
| REQ-011 | Track segment chart annotations | Telemetry chart metadata records selected `track_segment`, corner metadata when used, and synchronized `distance_range_m` in generated artifact JSON | `src/f1_telemetry_charts/recipes/telemetry_trace.py`; `tests/test_analysis_workspace.py` | Implemented through Slice 3 |
| REQ-012 | Race playback explorer | TBD | TBD | Deferred to Slice 4 |
| REQ-013 | Lap and timestamp playback modes | TBD | TBD | Deferred to Slice 4 |
| REQ-014 | Position frame interpolation | TBD | TBD | Deferred to Slice 4 |
| REQ-015 | Playback context details | TBD | TBD | Deferred to Slice 4 |
| REQ-016 | Playback-driven chart range selection | TBD | TBD | Deferred to Slice 4 |
| REQ-017 | Snapshot reuse | Bounds/style/map/corner APIs read loaded snapshots only; no selector path reloads FastF1 data | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `tests/test_analysis_workspace.py` | Implemented through Slice 3 |
| REQ-018 | Exported selection metadata | Chart metadata records style sources, coverage bounds, requested/effective ranges, selected track segment metadata, and selected corner metadata | `src/f1_telemetry_charts/recipes/`; `tests/test_core_recipes.py`; `tests/test_analysis_workspace.py` | Implemented through Slice 3 metadata |
| REQ-019 | Graceful degraded modes | Coverage and track-map payloads report unavailable geometry/corners with reasons; UI preserves bounded numeric telemetry controls and manual selector controls | `src/f1_telemetry_charts/recipes/parameters.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py`; browser degraded-state check | Implemented through Slice 3 degraded states |
| REQ-020 | LLM-safe track-map inspection | LLM inspection exposes bounded coverage, corner availability, and track-map summaries without raw point arrays; parameter updates remain backend validated | `src/f1_telemetry_charts/llm/contract.py`; `tests/test_llm_contract.py` | Implemented through Slice 3 summaries |
| NFR-001 | Interactive performance | Existing numeric range diagnostics and track selector use cached snapshot payloads and browser-verified responsive controls | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; `src/f1_telemetry_charts/analysis/track_map.py`; browser smoke check | Implemented for Slice 1 and Slice 2 interactions |
| NFR-002 | Payload bounds | Track map payloads default to 500 points, cap at 1200, preserve endpoint downsampling, expose original sample counts, and include bounded corner marker metadata | `src/f1_telemetry_charts/analysis/track_map.py`; `src/f1_telemetry_charts/ui/server.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented through Slice 3 track maps |
| NFR-003 | Responsive usability | Track selector modal, corner controls, and range controls browser-checked at desktop and 390x844 mobile width without horizontal overflow | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; rebuilt `src/f1_telemetry_charts/ui/static/` assets; browser smoke check | Implemented through Slice 3 selector |
| SEC-001 | Local snapshot boundary | Coverage and validation operate on open Analysis snapshots | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/ui/server.py`; `tests/test_analysis_workspace.py` | Implemented for Slice 1 |
| SEC-002 | No code authoring surface | Structured style, bounds, range, and LLM parameter APIs only | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/llm/contract.py`; `frontend/src/pages/AnalysisWorkbenchPage.tsx` | Implemented for Slice 1 |
| DATA-001 | Style source metadata | `StyleColor` and `SessionStyleMetadata` plus chart metadata `style_sources` | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/recipes/parameters.py`; `tests/test_core_recipes.py`; `tests/test_fastf1_gateway.py` | Implemented in Slice 1 |
| DATA-002 | Coverage bounds model | Structured lap, distance, session-time, and track-map availability bounds | `src/f1_telemetry_charts/recipes/parameters.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented for Slice 1 |
| DATA-003 | Track geometry model | Pydantic session geometry plus track map point, marker, segment, and payload models with deterministic projection and unavailable/invalid states | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/data/track_geometry.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/types.ts`; `tests/test_track_geometry.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented in Slice 2 |
| DATA-004 | Corner marker model | Pydantic circuit corner/session circuit info plus projected track-map corner payload model | `src/f1_telemetry_charts/data/models.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `frontend/src/types.ts`; `tests/test_track_geometry.py`; `tests/test_fastf1_gateway.py` | Implemented in Slice 3 |
| DATA-005 | Playback frame model | TBD | TBD | Deferred to Slice 4 |
| API-001 | Coverage endpoint | `GET /api/analysis/coverage` and LLM inspection coverage payload | `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/llm/contract.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented for Slice 1 |
| API-002 | Track map endpoint | `POST /api/analysis/track-map` returns bounded projected session geometry, corner markers, segment markers, bounds, counts, and diagnostics independent of selected-driver position coverage | `src/f1_telemetry_charts/ui/server.py`; `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/analysis/track_map.py`; `tests/test_analysis_workspace.py` | Implemented through Slice 3 |
| API-003 | Range validation endpoint | Diagnostics/create/update/generate/LLM paths share backend bounds validation and accept corner-derived distance ranges through the same `distance_range_m` contract | `src/f1_telemetry_charts/analysis/workspace.py`; `src/f1_telemetry_charts/ui/server.py`; `tests/test_analysis_workspace.py`; `tests/test_llm_contract.py` | Implemented through Slice 3 ranges |
| API-004 | Playback endpoint | TBD | TBD | Deferred to Slice 4 |
| UX-001 | Primary visual distance selection | Add Chart and telemetry chart editor expose Track Selector action next to chart controls; applying visual selection updates existing numeric distance fields before save/generate | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; browser smoke check | Implemented in Slice 2 |
| UX-002 | Track-map selector ergonomics | SVG trace renders full lap, corner markers, highlighted selected segment, distinct start/end markers, range sliders, numeric fields, corner padding controls, reset/apply/cancel, and unavailable state | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; browser smoke check | Implemented through Slice 3 selector |
| UX-003 | Bounded input feedback | Min/max range fields, field diagnostics, invalid Save/Generate blocking | `frontend/src/pages/AnalysisWorkbenchPage.tsx`; browser smoke check | Implemented in Slice 1 |
| UX-004 | Race playback explorer layout | TBD | TBD | Draft |
| UX-005 | Chart-range handoff | TBD | TBD | Draft |
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

## Review checklist

- [x] spec_id is unique and follows the SPEC-XXX format.
- [x] Every requirement has an ID, statement, rationale, acceptance criteria,
      verification method, and evidence location.
- [x] Non-goals are listed.
- [x] Open questions are resolved or explicitly deferred.
- [x] Verification matrix covers every requirement.
- [x] Conflict check completed.
- [x] Human approval recorded before status set to Approved.
