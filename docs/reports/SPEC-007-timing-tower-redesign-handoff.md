# SPEC-007 Timing Tower Redesign Handoff

This is an agent handoff artifact. `docs/specs/approved/SPEC-007-track-map-range-and-race-playback.md` remains the product source of truth. Before implementing the redesign below, add a new SPEC-007 amendment or update the current approved requirement trail according to the repository workflow.

## Handoff

**Current goal**

Redesign the Race Playback timing tower so it reads like an analyst timing screen instead of a debug/status panel. The tower should prioritize live race context, use FastF1 timing data where available, hide data provenance unless debug mode is enabled, and remove chart-application controls from this page for now.

**Implemented**

- Race Playback already exists in `frontend/src/pages/AnalysisWorkbenchPage.tsx`.
- Playback map markers support driver colors, zoom, pan, rotate, fit/reset, marker clicks, readable labels, and compact hitboxes.
- Backend playback exists in `src/f1_telemetry_charts/analysis/playback.py`.
- Session snapshots now include `TimingStreamRecord` in `src/f1_telemetry_charts/data/models.py`.
- FastF1 timing stream extraction is implemented in `src/f1_telemetry_charts/data/gateways/fastf1.py` using `fastf1.api.timing_data()`.
- Playback marker context currently exposes timing position, gap to leader, interval to position ahead, timing status, timing source, and sample age.
- Current timing tower already supports row click and marker click sharing `focusedDriver`.

**Open issues**

- The timing tower still shows debug-like marker state such as `ACTIVE`, `STALE`, `MISSING` in normal UI. User wants this removed unless debug mode is enabled.
- The right-side `Frame`, `Chart Range`, and `Chart` controls are not relevant to Race Playback right now. User wants chart application removed from this page for now. A future explicit workflow can reintroduce it later.
- The current tower only exposes a subset of the desired analyst columns.
- The color indicator should not be a dot. User wants a better style, preferably a thin driver/team color rail near the far-left position area.
- Mini-sector display must not show time values. It should show state only: purple fastest, green faster, yellow slower.

**Required timing tower columns**

Default tower columns requested by the user:

1. Pit state: in pit or not.
2. Position.
3. Driver: 3-letter code only, plus color styling.
4. Interval.
5. Gap to leader.
6. Tyre compound plus tyre age, not stint.
7. Best lap.
8. Last lap.
9. Mini sectors.
10. Last sectors.
11. Best sectors.
12. Optional event indicators if possible from FastF1:
    - Penalties.
    - Race control.
    - Track limits.

**Data source notes**

- `fastf1.api.timing_data().stream_data` provides:
  - `Time`
  - `Driver`
  - `Position`
  - `GapToLeader`
  - `IntervalToPositionAhead`
- `fastf1.api.timing_app_data()` provides:
  - `LapNumber`
  - `LapTime`
  - `Stint`
  - `TotalLaps`
  - `Compound`
  - `New`
  - `TyresNotChanged`
  - `Time`
  - `StartLaps`
- `fastf1.api.timing_data().laps_data` provides:
  - completed lap time
  - number of completed laps
  - number of pit stops
  - pit in/out times
  - sector times
  - sector session times
  - speed traps
- `fastf1.api.race_control_messages()` provides:
  - `Utc`
  - `Category`
  - `Message`
  - optional `Status`, `Flag`, `Scope`, `Sector`, `RacingNumber`, `Lap`
- `Session.race_control_messages` exists when messages are loaded.

FastF1 `api` functions are private/future-unstable. Keep all access wrapped in the FastF1 gateway and persist normalized snapshot records. The playback UI must not perform hidden FastF1 fetches.

**UI requirements**

- Remove `Chart Range` and `Chart` from Race Playback for now.
- Replace the current `Frame` block with a compact cursor chip near the timeline, for example: `Lap 2 · 1:37.3 · 3 cars`. Do not keep it as a right-side card.
- Dedicate the right panel to the timing tower.
- Use a thin vertical color rail at the far left of each row, near the position number. Do not use a standalone color dot.
- Driver column must use only 3-letter driver abbreviations such as `VER`, `PER`, `ALO`.
- Hide marker provenance (`active`, `stale`, `missing`, interpolation method, timing age, timing source) unless a debug mode parameter is enabled.
- Normal mode may show rare race-state badges only when relevant, such as pit, penalty, track limit, or race-control event.
- Rows must remain readable at desktop and mobile sizes. Avoid a wide spreadsheet that overflows.
- Row click and marker click must remain synchronized.
- All map markers should remain visible when a driver is selected. Selection should highlight the row and marker, not filter the field.

**Recommended layout**

Do not try to show every value as a full text column on one line. Use a dense primary row plus compact visual strips.

Primary row proposal:

```text
| P | DRV | INT | GAP | TYRE | AGE | LAST | MINI |
```

Example:

```text
| 1 | VER | -     | Leader | S | 3 | 1:36.112 | ■■■■■■■■■■ |
| 2 | PER | 1.234 | 1.234  | S | 3 | 1:36.804 | ■■■■■■■■■■ |
| 5 | ALO | 2.876 | 4.321  | S | 3 | 1:37.221 | ■■■■■■■■■■ |
```

Important: `MINI` cells are mini-sector status blocks, not time values.

Mini-sector colors:

- Purple: fastest.
- Green: faster.
- Yellow: slower.
- Grey: unavailable.

Sector and mini-sector terminology:

- Sectors are official `S1`, `S2`, `S3`.
- Mini sectors are smaller computed track chunks inside a lap.
- Official sector times can come from lap/timing data.
- Mini-sector states likely require telemetry segmentation by distance and a comparison reference.

**Expanded row / detail behavior**

Use expansion, hover, or a secondary detail surface for values that would make the primary row unreadable:

- Best lap.
- Last sector states.
- Best sector states.
- Full last/best sector times if debug or detail mode later wants them.
- Race-control messages affecting the driver.
- Penalty text.
- Track-limit event text.
- Timing freshness/debug provenance.

**Analyst display rules**

- In normal timing mode, show race context, not data provenance.
- `INT` and `GAP` should come from FastF1 timing stream values.
- `TYRE` should be a compact compound code, for example `S`, `M`, `H`, `I`, `W`.
- `AGE` should be tyre age from FastF1 timing-app data, not stint number.
- `LAST` should be last completed lap time.
- `BEST` can be in expanded row or alternate display mode, not necessarily a primary column if space is tight.
- Pit should be a compact indicator, not a full text column when false.
- Penalties, race control, and track limits should be event badges only when present, not permanent empty columns.

**Known risks**

- Timing-app data is sparse. Compound, age, and lap time values may require as-of aggregation per driver, not exact timestamp matching.
- Mini sectors are computed and need a clearly defined reference:
  - compared to session fastest mini-sector,
  - compared to selected driver,
  - compared to the driver's own best,
  - or compared to previous lap.
  Do not implement mini sectors until the reference rule is approved.
- Penalty and track-limit detection from race-control messages requires text/category parsing. It is feasible but fragile. Keep it as event badges and preserve raw message text/source metadata.
- FastF1 `api` endpoints are private. Wrap and fail softly.

**Rejected or tried already**

- Do not show `ACTIVE`, `STALE`, or `MISSING` in the normal timing tower.
- Do not use a color dot that consumes driver-column space.
- Do not keep chart-application controls in the right-side Race Playback panel.
- Do not show mini-sector time values in the timing tower.
- Do not infer gaps from map distance when FastF1 timing stream data is available.

**Next recommended action**

Create a new SPEC-007 amendment for the timing tower redesign, then implement the smallest complete vertical slice: remove chart apply controls, move frame info to a compact timeline chip, hide provenance in normal mode, and restyle the current timing tower with color rail plus `P / DRV / INT / GAP / TYRE / AGE / LAST / MINI` placeholders. Add timing-app data persistence before populating `AGE` and `LAST`.

## Next Builder Prompt

Continue this task from the current repository state. First inspect the current diff and relevant files to confirm the latest implementation before making changes.

Goal: Redesign the Race Playback timing tower into an analyst-readable timing screen with FastF1-derived race context, compact driver/color styling, and no normal-mode debug provenance.

Current state: Race Playback already has a map, timeline, FastF1 timing stream gap/interval data, marker/row focus sync, and a basic timing tower. The tower still exposes debug-like `ACTIVE` status, uses color dots, and the right panel still includes `Frame`, `Chart Range`, and `Chart` controls that the user wants removed for now.

Constraints: This repository is specification-first. Add a SPEC-007 amendment before behavior/UI changes. Playback UI must use loaded snapshots only, with no hidden FastF1 fetches. FastF1 private API access must remain wrapped in the gateway. Do not show mini-sector time values; mini sectors use state colors only: purple fastest, green faster, yellow slower, grey unavailable.

Risks: Timing-app data is sparse and needs as-of aggregation. Mini-sector comparison needs an approved reference rule before implementation. Penalty/track-limit parsing from race-control messages is feasible but fragile and should be badges, not permanent columns.

Do not repeat: Do not show `ACTIVE/STALE/MISSING` in normal UI. Do not keep chart apply controls in the right panel. Do not use a color dot as the primary color indicator. Do not infer gaps from map position when FastF1 gap/interval data exists.

Next task: Add the SPEC-007 amendment, then implement the first vertical UI/data slice: remove chart apply controls from Race Playback, move frame info to a compact timeline chip, hide provenance unless debug mode is enabled, restyle the tower with a left color rail and 3-letter driver codes, and prepare columns for `P / DRV / INT / GAP / TYRE / AGE / LAST / MINI`.

Keep the response focused on execution, then implement and verify the next step.
