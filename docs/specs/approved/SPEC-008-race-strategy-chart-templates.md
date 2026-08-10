---
doc_type: spec
spec_id: SPEC-008
title: Race Strategy and Pace Chart Templates
status: In Implementation
owner: Nelson Jeanrenaud
related_issue:
related_prs: []
delivery_refs: []
affected_components:
  - analysis workspace
  - recipe registry
  - chart recipes
  - chart renderer
  - normalized session data
  - frontend chart editor
  - LLM contract
affected_interfaces:
  - Analysis Workbench Add Chart and chart editor
  - analysis recipe and template APIs
  - generated chart metadata
  - exported analysis packages
supersedes: []
superseded_by:
depends_on:
  - SPEC-001
  - SPEC-004
  - SPEC-005
  - SPEC-006
  - SPEC-007
conflicts_with: []
last_verified_at: 2026-08-05
---

# SPEC-008: Race Strategy and Pace Chart Templates

## Summary

Add a coherent family of reusable race-strategy chart templates to the
existing Analysis Workbench: Strategy Timeline, Stint Pace, Pace Evolution,
Compound Comparison, Race-Time Delta Evolution, Pit-Cycle Comparison, and
Driver Battle. The templates
must share one explicit representative-lap and stint-analysis contract so that
their results agree, expose exclusions and uncertainty, and remain suitable as
building blocks for a later linked Strategy Analysis workspace. This spec does
not add that workspace or make predictive strategy recommendations.

## Context

SPEC-001 through SPEC-007 provide normalized FastF1 session data, deterministic
chart recipes, schema-driven parameters, persisted chart instances, review and
export, track context, and race playback. The current built-in catalog contains
lap-time delta, telemetry trace, tyre strategy, and position progression.

The existing foundation already carries lap timing, sectors, compound, stint,
pit-in and pit-out state, timing gaps, positions, track status, weather,
telemetry, and timing-app tyre context where the source provides them. It can
therefore support a materially stronger retrospective strategy analysis layer
without introducing a second application shell.

This spec is the chart-primitive step identified by the 2026-08-04 product and
analyst review. A later spec may compose these primitives into a synchronized
Strategy Analysis workspace and one-click strategy report.

## Problem statement

Users currently have to combine general lap-time, tyre, position, and playback
views mentally. The app cannot consistently answer which laps are
representative, how stint pace evolved, whether compound comparisons are
defensible, or what changed through a pit cycle. Independent additions would
also risk applying different exclusion and calculation rules to related
charts. The project needs reusable strategy templates backed by one explicit,
versioned analytical contract.

## Goals

- Add seven reusable retrospective race-strategy templates.
- Establish one shared representative-lap, stint, tyre-age, and comparison
  contract used by every strategy template.
- Make exclusions, effective sample sizes, source coverage, and analytical
  limitations visible and exportable.
- Distinguish measured values from estimates and observed pace evolution from
  causal tyre degradation.
- Integrate the templates with current chart instances, presets, diagnostics,
  generation, export, plugins, and LLM inspection.
- Preserve deterministic, local-first generation from saved session snapshots.
- Prepare stable primitives for a later linked Strategy Analysis workspace.

## Non-goals

- A new Strategy Analysis page, linked dashboard, or top-level navigation item.
- One-click generation of a complete strategy report.
- Live timing or live strategy support.
- Optimal-stop prediction, race simulation, Monte Carlo modelling, or strategy
  recommendations.
- Exact fuel-corrected tyre degradation or causal attribution of lap-time
  changes to tyres.
- Inferring team intent or judging what a team or driver should have done.
- Automatic natural-language strategy observations or cross-chart synthesis.
- Adding new external data providers or race-control-message ingestion.
- A full-field Pace Heatmap. It is a high-value follow-up candidate but needs a
  separate density, categorical-state, benchmark, color-scale, accessibility,
  and interaction contract.
- A standalone track-evolution chart. Track and conditions context is a
  reusable aligned panel or overlay within the relevant strategy templates.
- Replacing the existing tyre-strategy template before the compatibility
  decision in this draft is resolved.
- Implementing every possible renderer layout for the new analytical models.

## Users or actors

- **F1 analyst:** configures and generates strategy charts, checks exclusions,
  compares drivers or stints, and exports evidence.
- **Report author:** uses generated charts and metadata in a reviewed report.
- **LLM agent:** inspects available templates, parameter schemas, effective
  configuration, results, and limitations without executing arbitrary code.
- **Plugin author:** can rely on stable shared strategy-analysis models while
  providing additional recipes.
- **Analysis service:** validates configuration, derives shared analytical
  results, renders artifacts, persists metadata, and reports diagnostics.

## Terminology and analytical interpretation

- **Strategy lap:** a normalized lap record enriched with effective stint,
  compound, tyre age when available, contextual classifications, and pace
  eligibility.
- **Representative lap:** a lap included by the effective exclusion policy for
  pace calculations. It does not mean the lap was free of every external
  influence.
- **Observed pace evolution:** the fitted change in representative lap time as
  tyre age or stint progress increases. It is not labelled pure tyre
  degradation because fuel load, traffic, track evolution, weather, damage,
  management, and deployment may contribute.
- **Comparable sample:** a template-specific pair or collection of samples
  satisfying the exact driver, compound, race-lap, tyre-age, and minimum-count
  rules defined below. No generic compound-offset estimand exists.
- **Pit cycle:** the configured window beginning before a pit-in lap and ending
  after the first eligible post-stop lap or a bounded number of laps.
- **Measured value:** directly present in normalized source data.
- **Derived value:** deterministically calculated from measured values.
- **Estimated value:** calculated using an explicit baseline or counterfactual
  assumption and always labelled as an estimate.
- **Analytical result:** a structured, versioned result used by one or more
  templates and persisted in artifact metadata.

## Normative analytical rules

### Pace eligibility versus contextual visibility

Every strategy lap must carry these independent fields:

- `is_representative_for_pace`: whether it enters pace statistics or fits.
- `pace_exclusion_reasons`: all reasons preventing pace inclusion, in stable
  code order.
- `is_visible_in_context`: whether a renderer may show the lap or event.
- `context_classifications`: all applicable context such as pit-in, pit-out,
  neutralized, red-flag boundary, compound change, or missing data.

The common analytical inclusion policy does not impose a common display
policy. Pit and neutralized laps are excluded from default pace calculations
but remain visible in Strategy Timeline, Pit-Cycle Comparison, and Driver
Battle when they provide context.

“First lap” means race lap 1 only, not the first timed lap of every stint. A
lap may have multiple classifications and exclusion reasons; no mutually
exclusive primary classification is created. Explicit `is_accurate=false`,
deleted, or generated state always excludes a lap from pace. Missing sectors
do not exclude an otherwise valid lap-time sample unless the user enables the
complete-sector rule. When track-status coverage is missing, otherwise valid
laps remain eligible and the result carries a coverage warning. When a status
contains multiple codes, any code excluded by the effective policy excludes
the lap. Conflicting stint or compound evidence makes stint-dependent analysis
unavailable for that lap but does not hide its source context.

### Descriptive statistics

- The analytical unit for stint results is one driver plus one effective
  stint. Stints are never pooled merely because their compound matches.
- Median and quantiles use the sorted finite representative values and the
  Hyndman-Fan type 7 linear-interpolation method. IQR is Q3 minus Q1.
- The trimmed mean uses a 10% symmetric trim. For sample count `n`, exactly
  `floor(0.10 * n)` sorted observations are removed from each tail. Therefore
  samples of five through nine are not trimmed. The effective count and trim
  count are recorded.
- Minimum and maximum use representative samples only.
- Calculations retain full available precision. Lap-time, delta, slope, and
  dispersion values display to three decimal places without changing stored
  values. Equal values retain stable source order; missing and non-finite
  values are excluded with explicit reasons.

### Observed pace-evolution fit

- One fit is calculated per driver-stint; fits never cross stint boundaries.
- The y variable is representative lap time in seconds.
- The preferred x variable is reliable source tyre age expressed as completed
  laps on the set, using the source convention without resetting its origin.
  Otherwise the result is a distinct `stint_progress` fit whose x value is the
  1-based chronological lap index from the effective stint start, including
  gaps created by excluded laps.
- Source tyre age must be non-decreasing. Equal x values are retained as
  samples but do not form pairwise slopes. A decrease or unexplained jump that
  conflicts with the stint boundary makes tyre-age fit unavailable and permits
  a separately labelled stint-progress fallback.
- The estimator is deterministic Theil-Sen: calculate `(yj-yi)/(xj-xi)` for
  every ordered pair with `xj > xi`, then take the type-7 median. The intercept
  is the type-7 median of `yi - slope*xi`.
- Residual dispersion is residual MAD in seconds: median of
  `abs(residual - median(residual))`, using the same type-7 median rule.
- Availability requires at least five representative samples and five
  distinct x values. Negative slopes are stored and displayed unchanged.
- Quality grades are evaluated in this order: `high` requires at least 12
  samples, at least 85% representative coverage, and residual MAD at most
  0.350 s; `medium` requires at least eight samples, 75% coverage, and MAD at
  most 0.750 s; `low` covers other available fits with at least eight samples;
  `provisional` covers available five-to-seven-sample fits; otherwise the fit
  is `unavailable`.
- Tyre-age and stint-progress slopes are different result types and may not be
  ranked or aggregated together. Slope units are seconds per tyre-age lap or
  seconds per stint-progress lap respectively.

### Compound-comparison modes

The template has exactly three initial modes and never emits a generic
“compound offset”:

1. `within_driver`: exactly one driver and two compound-stint samples. The
   primary result is the second sample’s median representative lap time minus
   the reference sample’s median. The user must apply either a tyre-age range
   to both samples or an explicit race-lap range containing both stints. The
   result kind is `descriptive_within_driver_difference`.
2. `matched_driver`: every eligible driver must contribute one within-driver
   median difference for the same ordered compound pair and control rule.
   Driver differences are aggregated with equal driver weight using their
   median; raw laps are never pooled across drivers. At least three eligible
   drivers and five representative laps per driver-compound sample are
   required. The result kind is `matched_driver_descriptive_difference`.
3. `unrestricted_distribution`: show representative distributions for
   selected compounds and drivers. It emits no scalar compound difference or
   pace-evolution comparison. The result kind is
   `unrestricted_descriptive_distribution`.

Within-driver mode requires five representative laps per compound sample by
default. A slope difference is optional secondary output only when both fits
use the same x-result type and are individually available. Different stints
remain independent samples. Sample count, control rule, driver weighting, and
result kind are mandatory metadata.

### Pit-cycle measurement contract

- The focal driver and exactly one rival define the comparison.
- The selected focal stop identifies pit-in and pit-out boundaries. The
  pre-stop reference is the last point at or before the focal pit-in lap start
  where both drivers have numeric gap-to-leader timing values. The post-stop
  reference is the first point at the end of the focal driver’s first
  representative post-stop lap where both numeric values are available.
- The default post-stop search window is three race laps after pit-out and the
  configurable maximum is five.
- Direct focal-to-rival gap is `focal_gap_to_leader - rival_gap_to_leader`.
  Positive means the focal driver is behind; negative means ahead. Measured gap
  change is `post_direct_gap - pre_direct_gap`; negative means the focal driver
  gained time relative to the rival.
- A position reversal is represented by the sign crossing zero and retained
  position fields. Lap-valued gaps or mixed lap/time gaps make direct time-gap
  change unavailable; position change remains a separate result and is never
  converted into seconds.
- If the rival pits within the comparison window, or the window includes SC,
  VSC, or red-flag running, measured values remain visible but the comparison
  is marked `confounded` and no unqualified summary is emitted.
- The displayed focal pit-lane interval begins at source
  `pit_in_time_seconds` and ends at `pit_out_time_seconds`. If either timestamp
  is unavailable, the renderer may show only the bounded pit-in/pit-out lap
  interval and must label it lap-bounded rather than exact. A rival stop is
  detected from the rival’s pit timestamps or pit-in/pit-out lap flags inside
  the pre/post comparison window. Neutralized running is detected from any
  effective SC, VSC, or red-flag track-status code intersecting that window.
  These are calculation diagnostics, not permanent rows in the chart summary.
- Derived elapsed-time components may include source-backed pit-lane time and
  in/out-lap timing. Counterfactual no-stop estimates are out of scope for the
  initial template. There is no generic `estimated_net_change` field.

### Race-time delta evolution contract

The template has two explicitly different modes which never share the same
result label:

1. `measured_gap_change`: uses a reliable direct timing stream. At every
   comparable timestamp, direct focal-to-reference gap is
   `focal_gap_to_leader - reference_gap_to_leader`. The plotted value is the
   current direct gap minus the direct gap at the selected start point.
   Positive means the focal driver lost time relative to the reference since
   the start; negative means gained time. No summation is performed. This is
   titled “Direct-Gap Change” and labelled “Measured direct-gap change (s).”
2. `derived_cumulative_pace_delta`: sums paired representative-lap differences
   `focal_lap_time - comparator_lap_time` after the first comparable point,
   which is the zero baseline. The comparator is exactly one explicitly
   selected driver. Positive means cumulative representative pace loss;
   negative means gain. The rendered mode is called “Cumulative pace
   difference” and is not presented as measured race gap.

Pit, neutralized, missing, or otherwise ineligible paired laps do not
contribute a derived delta. The line breaks across unavailable coverage and
resumes from the retained cumulative value after a labelled `not observed`
gap; no connector or zero delta is imputed. Measured mode retains pit-stop and
neutralized effects present in the timing stream. Derived mode excludes pit
and neutralized laps under the common pace policy, so its chart subtitle must
state that those effects are not included. Compound changes, pit events, and
SC/VSC/red-flag intervals are contextual annotations.

Measured overall change is the final available direct gap minus the selected
start direct gap. A measured stint change is the last minus first comparable
direct gap inside the focal driver’s effective stint and therefore follows the
focal driver’s stint boundaries, not the reference driver’s. Optional
`green_running_change` sums consecutive observed direct-gap movements only
when both samples and the interval between them are green, within the same
focal stint, and outside pit or coverage gaps. SC restarts begin a new segment.
If stint or green-running summaries do not reconcile to overall measured
change, the chart must show the omitted/non-comparable remainder rather than
imply reconciliation.

Measured coverage uses one expected reference point per selected race lap for
which both drivers are classified running. Coverage is paired numeric direct-
gap points divided by those expected points. Lap-valued gaps, missing points,
and stopped/retired states remain explicit. Derived coverage is paired eligible
representative laps divided by expected laps where both focal and benchmark
samples are required by the selected benchmark. All modes record start lap,
end lap, benchmark, paired sample count, excluded laps, coverage numerator and
denominator, percentage, and sign convention.

## Canonical visual contracts

### Strategy Timeline

- X-axis: race lap only. Elapsed-time mode is not part of this spec.
- Y grouping: one row per driver; all effective stints for that driver occupy
  that row. Default driver order is final recorded classification, followed by
  stable driver code for unavailable or tied classification.
- Primary marks: compound-colored stint bars and a small pit-event marker
  confined to the affected driver row. Pit events never create full-height
  lines; one shared triangle key labelled `Pit stop` explains the marker in the
  legend. Unknown compound uses a neutral grey hatched bar labelled `UNKNOWN`.
- A compound change without a pit event is shown as a bar boundary without a
  pit marker. A red-flag boundary uses a full-height red double line and is not
  rendered as a pit event. Conflicting stint evidence uses a hatched warning
  segment and corresponding legend entry.
- Default context contains stint bars and row-local pit markers with subtle
  full-height SC and VSC background bands shared by all driver rows. Contiguous
  intervals are coalesced and each context type receives at most one compact
  legend entry. Red-flag context remains visually distinct. Advanced controls
  may add tyre-age labels and may replace the default context with one alternative
  shared layer: Conditions, position, or gap. The Conditions layer aligns
  median representative field pace, track temperature, air temperature,
  rainfall, and track-status coverage by race lap. Position and gap use a
  separate aligned lower panel rather than background shading.
- Default maximum is 20 drivers. Stable driver and compound identity follows
  existing SPEC-007 style metadata with accessible labels in addition to color.
- The legend orders visible dry compounds as Soft, Medium, Hard, followed by
  other compounds, the shared pit-stop key, Safety Car, and VSC when present.
  It does not contain driver-stint or individual pit-in/pit-out entries. Missing
  active-stint data remains an unfilled gap; it is not represented by the same
  grey encoding as unknown compound. A source-backed retirement or stopped
  result uses a separately labelled hatch and `RET` endpoint after the driver's
  last recorded lap. Hard uses a darker neutral fill and outline so it remains
  visible against the chart background. VSC bands carry a direct `VSC` label at
  the top of the shaded interval.
- The default view remains the strategy timeline plus race-neutralization
  context only. Position, gap, Conditions/weather, and tyre-age overlays require
  an explicit non-default presentation choice.
- Canonical references:
  `docs/specs/assets/SPEC-008-strategy-timeline-default.svg` and
  `docs/specs/assets/SPEC-008-strategy-timeline-context.svg`.

### Stint Pace

- Default x-axis is stint lap (`stint_progress`). Tyre age is an optional
  alternative when source coverage is available. Race lap remains an explicit
  context mode. Every view limits its domain to the selected driver-stints;
  context events outside that window never expand the chart. Y-axis is
  representative lap time in seconds.
- Optional presentation: same-lap delta to exactly one selected reference
  driver, calculated only where both drivers have representative samples.
- Grouping: driver plus effective stint. Summary statistics are independent
  per driver-stint.
- Representative samples use connected marks with a distinct line style and
  point marker per driver-stint. Lines break across excluded laps. Excluded
  laps appear in a narrow strip above the pace plot, use each driver's marker
  shape with a hollow neutral-grey treatment, share one
  `Hollow marker = excluded lap` legend entry, are never connected, never
  affect the representative y-axis scale, and never enter summaries.
- SC and VSC intervals appear only in race-lap context mode and only when they
  intersect a selected stint. Red-flag boundaries follow the same intersection
  rule and use the shared red encoding.
- Exactly two selected driver-stints produce the default head-to-head summary:
  one metric per row and one driver-stint per column. Lower median, trimmed
  mean, minimum, and maximum lap time and lower IQR are highlighted as the
  better value; representative sample count is neutral and never receives a
  performance highlight. Ties use a shared neutral highlight.
- A compact in-chart annotation box reports representative lap count, median,
  and IQR for each selected stint. For exactly two stints it states the faster
  driver's absolute median advantage, for example
  `VER median advantage: 0.663 s`. Legend labels use compact driver-stint
  identifiers such as `VER S1` and `PER S1`; compound identity appears once in
  the subtitle. Each representative trace is labelled directly at its final
  point.
- Exported charts retain both compact legend entries and direct trace labels.
  Exclusion reasons remain available in artifact metadata and interactive
  application detail; the static chart does not enumerate them. The default
  progression template adds no median lines, trend lines, delta panels, or
  further analytical annotations.
- Two driver-stints is the recommended comparison. Up to four may share one
  plot and compact comparison table. More than four requires separate chart
  instances; no series is silently dropped. Y scaling is shared.
- Advanced presentation mode `consistency_summary` is titled “Stint Pace
  Summary” because it compares both pace level and spread rather than only
  consistency. It uses one explicitly labelled horizontal row per driver-stint,
  sorted by median with the faster stint first. Median is the visual anchor,
  IQR is the darker primary interval, and min/max is a lighter secondary range;
  the chart also carries representative count and may optionally carry a
  10th-to-90th-percentile interval. The numeric x-axis is labelled
  “Representative lap time (s)” and must not be confused with tyre age or stint
  progress.
- Driver identity uses the established driver color and accessible line/mark
  style; compound is a separate labelled chip on each row. A graphical legend
  identifies the median point, IQR bar, min/max whisker, and optional percentile
  interval. The optional observed-pace-evolution slope column always shows its
  result basis (`tyre_age` or `stint_progress`), units (`s/tyre-age lap` or
  `s/stint-progress lap`), and quality grade. Slope is never ranked across
  different bases.
- The mode supports up to 20 rows and may sort by median, IQR, or compatible
  slope, with stable driver/stint order as a neutral default. When row count
  exceeds the available vertical space, desktop scrolls the table body and
  export paginates or creates additional chart instances; labels and rows are
  never silently removed. It consumes the same stint summary and does not
  create a separate analytical model.
- Canonical reference: `docs/specs/assets/SPEC-008-stint-pace.svg`.
  Consistency-mode reference:
  `docs/specs/assets/SPEC-008-stint-consistency.svg`.

### Pace Evolution

- X-axis: source tyre age or stint progress, never an unlabeled mixture.
- Y-axis: representative lap time in seconds. One fit is retained per
  driver-stint.
- Points, Theil-Sen line, slope, sample count, residual MAD, and quality grade
  are visible. Excluded laps may appear as hollow unconnected marks.
- SC and VSC intervals may be shown only when x is race-lap aligned; they are
  not projected onto tyre-age or stint-progress axes. Neutralized laps remain
  visible as excluded marks with their reason.
- Exactly two driver-stints using the same x-result type overlay their points
  and fit lines on one shared plot and use the same side-by-side comparison
  table pattern as Stint Pace. The table compares slope, residual MAD, sample
  count, coverage, and quality; lower MAD is highlighted, while slope is not
  labelled better or worse because its interpretation is contextual.
- Up to four driver-stints of the same x-result type may overlay on shared
  axes. Different x-result types are separated into labelled facets and are not
  compared. More than four requires separate chart instances.
- Advanced `sector_evolution` mode requires complete sector timing and renders
  one labelled panel for each of sectors 1, 2, and 3. Comparable selected
  driver-stints appear together inside every sector panel; it does not create
  one panel per driver. Each panel shows raw representative sector samples plus
  the independently fitted Theil-Sen line.
- The x-axis is numeric source tyre age or stint progress and follows the same
  result-type separation as the lap-time fit. The y-axis is sector-time delta
  in seconds relative to that driver-stint sector fit's value at its first
  valid x sample, so zero is the declared per-driver-stint baseline and
  positive means the sector became slower. Raw sector times remain in metadata.
- Each sector reports slope with its exact x basis and units, residual MAD,
  sample count, coverage, and quality grade independently. The mode supports
  up to four comparable driver-stints; more requires additional chart
  instances. Labels must say “observed sector-time evolution” and must not
  infer balance, fuel, degradation, or vehicle cause.
- Canonical reference: `docs/specs/assets/SPEC-008-pace-evolution.svg`.
  Sector-mode reference:
  `docs/specs/assets/SPEC-008-sector-pace-evolution.svg`.

### Compound Comparison

- X-axis is categorical compound name, such as `Hard`, `Medium`, and `Soft`;
  internal numeric category positions are never displayed. Y-axis is
  representative lap time in seconds.
- Each representative analytical sample is a lightly jittered point in its
  compound-standard colour. Driver/stint identity stays in metadata or
  interactive details and never becomes a static legend entry.
- Every compound displays its sample count, median, and IQR directly. The
  point density and `n` values must make unequal evidential weight visible;
  categories are evenly spaced and use the useful horizontal plotting area.
- Within-driver and eligible matched-driver modes may show a compound headline
  only when the comparable-window result supplies a scalar difference.
  Unrestricted or unavailable comparisons are explicitly labelled
  `Descriptive only` and emit no compound delta.
- Matched-driver headline wording identifies its equal-driver median basis;
  pooled points remain descriptive distributions. Raw result-kind identifiers,
  driver-stint keys, and implementation diagnostics never appear in the chart.
- Default maximum is two compounds for difference modes and five compounds for
  unrestricted mode. A missing compound is explicitly labelled `n=0 ·
  unavailable`, not rendered as a zero distribution. Driver and lap weighting
  remain in metadata and accessible details.
- Canonical reference: `docs/specs/assets/SPEC-008-compound-comparison.svg`.

### Pit-Cycle Comparison

- Generation requires an explicit focal driver, distinct rival, and focal
  pit-in lap. The title names the session, focal stop ordinal, and rival, for
  example `2023 Bahrain GP Race Pit Cycle: VER Stop 1 vs PER`.
- X-axis: race lap across the explicit pit-cycle window.
- Primary panel: direct focal-to-rival time gap when available, with the sign
  convention in the axis label. Its default domain fits the measured endpoints;
  a zero reference appears only when zero is inside that domain. Position is a separate fallback panel
  and never shares a numeric axis with time gap. Missing required timing must
  produce a visible typed partial/unavailable state with exact reasons or block
  generation; a silently empty primary panel is invalid.
- The pre-stop reference lap, pit-in lap, pit-out lap, and first eligible
  post-stop reference lap are each explicitly labelled. The focal pit-lane
  interval is one labelled shaded region from pit entry to pit exit.
- Secondary strip: exactly two driver-labelled rows showing compound state in
  the same focal window. It uses one compact compound legend and never creates
  stint-series legend entries. Neutralized or red-flag context appears only
  when it intersects the focal comparison window.
- Summary shows pre-gap, post-gap, and measured gap change. A clean comparison
  has a single “Measured comparison” badge. Rival-stop or neutralized-window
  diagnostics appear only when true, as a visible warning explaining why the
  result is confounded. Source timestamps and calculation fields remain in
  chart details and metadata rather than the primary graphic.
- Counterfactual availability or absence is not mentioned in the chart. Such a
  method is outside the initial template and therefore has no UI affordance.
- Optional `rejoin_context` uses the first valid timing sample at or after
  source `pit_out_time_seconds` as the rejoin reference. If exact timestamps
  are unavailable, it uses the first valid sample on the pit-out lap after the
  source marks the car out and visibly labels the reference `lap-bounded`.
  Running order and intervals are sampled at that same reference moment.
- The panel lists the focal driver, up to two cars immediately ahead, and up to
  two immediately behind. Every interval is focal-relative and written as
  “STR 1.8 s ahead of PER” or “BOT 0.9 s behind PER”; lap-valued or unavailable
  intervals remain explicit. Compound and tyre age are shown, and tyre age is
  tagged `source`, `derived`, or `unavailable` in metadata and accessible
  details.
- Post-stop evolution is a structured table, not an abstract trajectory plot.
  It separates “Next observed event” from “Relative position after 3 laps.” A
  later stop may appear only retrospectively as “pitted within N laps”; the
  chart must never predict a stop. `clean_air` means no car ahead within 3.0 s,
  `single_car` means exactly one, `traffic_group` means two or more, and
  `unavailable` means the numeric focal-relative intervals cannot support the
  classification. The threshold and method version are recorded in metadata.
- Optional `execution_breakdown` is titled “Measured Pit-Lane Duration” and
  exposes only source-supported measured components. The primary value is the
  duration from pit-in to pit-out; raw timestamps are details/metadata rather
  than headline values. Entry transit, stationary time, exit transit, or total
  pit-lap loss appear only when the snapshot has an explicit source field or a
  separately versioned derived method. Stationary time must never be inferred
  from lap time.
- Comparisons may use the focal driver’s other measured stops, a selected
  teammate, or eligible field stops and always show the signed duration delta.
  A stop may be ranked as faster/better only when both measurements have exact
  timestamps, green running, the same pit-lane configuration, and no known
  queue or double-stack condition. Otherwise the comparison remains
  descriptive and shows the incompatible context flags beside the delta.
- Canonical reference:
  `docs/specs/assets/SPEC-008-pit-cycle-comparison.svg`.
  Rejoin/execution reference:
  `docs/specs/assets/SPEC-008-pit-rejoin-execution.svg`.

### Race-Time Delta Evolution

- Generation requires one explicit focal driver and one distinct explicit
  comparator driver. No teammate, field median, fastest driver, or selected-
  driver-order fallback is permitted when the comparator is absent.
- X-axis: race lap. The title identifies the pair, for example
  `2023 Bahrain GP Race-Time Delta: VER vs PER`. The y-axis states the exact
  subtraction, for example `VER − PER race-time delta (s)`, and visible copy
  states `negative = VER ahead`.
- The default derived mode is visibly named “Cumulative pace difference” and
  is normalized to zero at its first comparable point. Measured mode remains a
  separate explicit “Measured race-time gap change” selection and is also
  normalized to zero. Coverage gaps are empty horizontal spans; the line stops
  before the gap and restarts after it with no connector or implied
  interpolation. All segments share one pair identity and one legend entry;
  internal segment numbers never appear in chart copy.
- A thin neutral horizontal zero reference makes the normalization visible.
  The subtitle names the actual start lap, for example
  `Cumulative pace difference · normalized to zero at lap 3 · negative = VER ahead`.
- Driver-specific pit-stop markers and SC/VSC/red-flag intervals use shared
  contextual annotations. Pit markers remain small, neutral, and secondary to
  the comparison line. Optional measured summaries distinguish overall change,
  focal-stint change, green-running change, and omitted/non-comparable
  remainder. Each summary places its label, numeric value, and interpretation
  on separate lines or columns so they cannot overlap. Derived summaries retain
  cumulative representative-pace semantics and cannot reuse measured labels.
- Exactly one focal/comparator driver pair is supported per chart in both
  modes.
- Canonical reference:
  `docs/specs/assets/SPEC-008-cumulative-race-time-delta.svg`.

### Driver Battle

- The title identifies the session and pair, for example
  `2023 Bahrain GP Driver Battle: VER vs PER`.
- Exactly three aligned panels: (1) representative lap time with direct driver
  labels, (2) absolute direct focal-minus-rival timing gap as the primary battle
  metric, and (3) driver-labelled compound, stint, and tyre-age context.
- Position is not a fallback for direct gap. Missing numeric paired timing
  produces a typed unavailable middle panel with its reason.
- Shared annotations show pit-in, pit-out, and neutralized periods. The summary
  reports start direct gap, end direct gap, and observed relative change when
  available. Pit-stop markers are explicit and aligned across all three panels.
- The lower panel uses one row per driver, one compact legend key per compound,
  and visible stint/tyre-age labels. Stint identifiers never become legend
  series.
- The chart consumes shared stint, pace, and pit-cycle analytical results and
  must not recalculate them independently.
- Exactly two drivers and one shared race-lap interval are allowed. Axes and
  units are fixed per panel; missing panels retain their location with an
  explicit unavailable state.
- Canonical reference: `docs/specs/assets/SPEC-008-driver-battle.svg`.

### Shared export and presentation rules

- Canonical export is 16:9 at the analysis theme’s configured DPI; desktop
  preview must preserve the same information hierarchy. Mobile may stack
  panels but must not change analytical content.
- Annotation priority is data-quality/error, selected pit event, neutralized
  region, pit markers, then optional contextual labels. Lower-priority labels
  may be suppressed only with a presentation diagnostic.
- Legends list analytical status, drivers, compounds, context, then exclusion
  encodings in that order. No semantic distinction relies on color alone.
- Presentation-only series or label reduction must be explicit and must never
  alter analytical calculations or exported metadata.

### Driver-count behavior

| Template | Normal use | Maximum in one chart | Behavior beyond the maximum |
| -------- | ---------- | -------------------- | --------------------------- |
| Strategy Timeline | Full-field overview | 20 drivers | Require driver filtering |
| Stint Pace | Two driver-stints head to head | 4 driver-stints | Create separate chart instances |
| Pace Evolution | Two comparable driver-stints | 4 driver-stints of one x-result type | Separate by x type, then create additional charts |
| Compound Comparison | One driver, matched eligible drivers, or descriptive distributions depending on mode | Mode-specific: 1 driver in within-driver mode; matched-driver aggregate; 5 compounds unrestricted | Block invalid mode selections with diagnostics |
| Race-Time Delta Evolution | One focal/reference pair or focal drivers against one derived field benchmark | 2 drivers measured; 4 focal drivers derived | Create separate chart instances |
| Pit-Cycle Comparison | One focal driver and one rival | Exactly 2 drivers | Not supported |
| Driver Battle | One selected battle | Exactly 2 drivers | Not supported; use another battle chart |

## Proposed vertical delivery slices

### Slice 1: Shared strategy-lap and stint contract

- Derive deterministic strategy-lap classification and exclusion reasons.
- Resolve stint boundaries, compound, tyre age, and source coverage.
- Expose shared parameter schemas and diagnostics.
- Add fixed expected-result fixtures before rendering new charts.

### Slice 2: Timeline and stint pace

- Add Strategy Timeline and Stint Pace templates.
- Render included and excluded laps, compounds, stops, and contextual regions.
- Persist summary statistics and sample coverage.

### Slice 3: Cumulative delta, pace evolution, and compound comparison

- Add Race-Time Delta Evolution, Pace Evolution, and Compound Comparison
  templates.
- Add robust trend estimates, comparable-window rules, quality grades, and
  explicit unavailable states.

### Slice 4: Pit cycle and driver battle

- Add Pit-Cycle Comparison and Driver Battle templates.
- Separate measured timing components from derived elapsed-time components.
- Persist the exact rival, baseline, and window used.

### Slice 5: Workbench, export, and inspection completion

- Complete chart-editor controls, presets, warnings, export packaging, LLM
  inspection, responsive checks, performance checks, and traceability.

## Functional requirements

### REQ-001: Shared strategy-lap classification

- **Statement:** The system must derive a strategy-lap record for every loaded
  lap and independently assign pace eligibility and contextual visibility as
  defined by the normative contract. It must retain all applicable pace
  exclusion reasons and context classifications rather than choose one primary
  classification.
- **Rationale:** All strategy charts must agree on which laps support their
  calculations and must not hide filtering.
- **Acceptance criteria:** Given the same session snapshot and exclusion
  configuration, every strategy template receives the same ordered
  strategy-lap records; pace and display fields are independent; first race
  lap, pit, neutralized, inaccurate, incomplete-sector, missing-status, and
  conflicting-stint cases follow the normative precedence rules.
- **Verification method:** Automated unit and integration tests with synthetic
  boundary fixtures and the canonical Bahrain fixture.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-002: Shared exclusion policy

- **Statement:** The strategy templates must use a shared configurable
  exclusion policy. The default must exclude race lap 1, pit-in laps, pit-out
  laps, deleted laps, generated laps, laps explicitly marked inaccurate, and
  non-green track-status laps when status coverage is available. Missing
  status must keep otherwise valid laps eligible with a warning. Missing
  sectors alone must not exclude a valid lap time unless complete sectors are
  requested. Users must be able to inspect requested and effective policies.
- **Rationale:** Representative pace is only useful when exclusions are
  consistent, visible, and reproducible.
- **Acceptance criteria:** Defaults are identical across all seven templates;
  changing a shared policy changes every dependent calculation; metadata lists
  included and excluded lap numbers grouped by reason; unavailable fields are
  reported; context renderers may still display analytically excluded laps.
- **Verification method:** Parameter normalization tests, recipe tests, API
  diagnostics tests, and metadata inspection.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-003: Deterministic stint and tyre-age resolution

- **Statement:** The system must derive effective stint boundaries, compound,
  and tyre age using normalized lap and timing-app data. Source-provided tyre
  age must take precedence; otherwise age may be derived only from a continuous
  known stint and must be marked derived. Unknown starting age must remain
  unavailable and must not be presented as new-tyre age zero.
- **Rationale:** Used-tyre starts and incomplete timing-app coverage can make
  naive stint-age calculations materially wrong.
- **Acceptance criteria:** Each stint records its data source and coverage;
  source and derived ages are distinguishable; used-tyre or discontinuous
  cases never silently reset to zero; charts requiring tyre age degrade
  explicitly when coverage is insufficient.
- **Verification method:** Unit tests for source, derived, conflicting,
  discontinuous, and unavailable tyre-age cases.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-004: Strategy Timeline template

- **Statement:** The built-in registry must provide a Strategy Timeline
  template implementing the canonical Strategy Timeline visual contract,
  including race-lap x-axis, one row per driver, compound stint bars, distinct
  pit and red-flag semantics, stable ordering, unknown/conflicting encodings,
  and progressively disclosed context.
- **Rationale:** Analysts need a full-race entry view showing where strategic
  phases and comparisons exist.
- **Acceptance criteria:** The template generates valid PNG and JSON artifacts
  for a 20-driver race; stint boundaries and compounds match analytical
  metadata; missing optional context produces a warning without failing the
  core timeline; no more than one common context layer is active; output
  conforms to both canonical reference renderings.
- **Verification method:** Recipe and renderer tests, fixture snapshot checks,
  and desktop/mobile visual inspection.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-005: Stint Pace template

- **Statement:** The built-in registry must provide a Stint Pace template that
  implements the canonical Stint Pace contract: race-lap x-axis, representative
  lap-time y-axis, independent driver-stint grouping, optional same-lap delta
  to one reference driver, and the normative count, median, IQR, trimmed mean,
  minimum, and maximum. It must also provide the canonical
  `consistency_summary` presentation using the same stint results. Excluded
  laps may be shown only as unconnected excluded marks.
- **Rationale:** Analysts need both the pace pattern and robust summary values,
  not only a fastest lap or unfiltered average.
- **Acceptance criteria:** Statistics match fixed expected fixture values;
  type-7 quantiles, 10% symmetric trimming, full-precision storage, and
  three-decimal display rules are followed; five-to-nine-lap samples remove no
  observations from the trimmed mean; fewer than the template minimum produces
  an insufficient-sample state; more than four progression series requires
  separate chart instances and is never silently reduced; Stint Pace Summary
  matches the same stored median, IQR, min/max, sample count, percentile, and
  slope values; its x-axis, graphical legend, compound chips, slope basis,
  slope units, quality, sorting, and 20-row overflow behavior follow the
  canonical visual contract.
- **Verification method:** Statistical unit tests, recipe integration tests,
  generated metadata inspection, and visual inspection.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-006: Pace Evolution template

- **Statement:** The built-in registry must provide a Pace Evolution template
  implementing the normative per-driver-stint Theil-Sen fit and canonical Pace
  Evolution visual contract. Tyre-age and stint-progress fits must be different
  result types, with their exact x basis, slope units, residual MAD, coverage,
  sample count, and quality grade exposed. User-facing labels and metadata must
  use “observed pace evolution” and must not call the result fuel-corrected or
  pure tyre degradation. Advanced `sector_evolution` mode must apply the same
  fit independently to complete sector 1, 2, and 3 samples and display
  comparable driver-stints together inside each sector panel using declared
  baseline-relative deltas.
- **Rationale:** Analysts need to compare how stints developed without
  overstating causal certainty.
- **Acceptance criteria:** The slope method and version are recorded; fixed
  samples produce deterministic type-7 slopes, intercepts, and residual MAD;
  five distinct x values and five representative samples are required;
  five-to-seven-sample fits are provisional; negative slopes remain unchanged;
  non-monotonic tyre age falls back only as specified; different x-result types
  cannot be ranked together; no excluded lap affects the fit; sector mode
  returns three separately versioned fit results and never attributes a vehicle
  or balance cause; raw samples remain visible, zero is the first-valid-sample
  fit baseline, positive means slower, and each sector exposes its independent
  basis, units, MAD, coverage, sample count, and quality.
- **Verification method:** Statistical unit tests, terminology inspection,
  recipe tests, and generated metadata checks.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-007: Compound Comparison template

- **Statement:** The built-in registry must provide a Compound Comparison
  template implementing exactly the normative `within_driver`,
  `matched_driver`, and `unrestricted_distribution` modes and the canonical
  visual contract. It must emit only the mode-specific descriptive result kind
  and must never emit a generic or causal compound-offset estimate.
- **Rationale:** Whole-race compound averages commonly confound fuel load,
  track evolution, driver, and race context.
- **Acceptance criteria:** Within-driver mode uses exactly one driver, two
  compound-stint samples, one control rule, and five representative laps per
  sample; matched-driver mode aggregates per-driver differences with equal
  driver weight and requires three eligible drivers; unrestricted mode emits
  no scalar difference; unavailable comparisons report exact reasons;
  metadata records result kind, weighting, samples, and control rule.
- **Verification method:** Comparison-window unit tests, insufficient-overlap
  fixtures, recipe tests, and UI inspection.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-008: Pit-Cycle Comparison template

- **Statement:** The built-in registry must provide a Pit-Cycle Comparison
  template for one focal driver and exactly one rival implementing the
  normative pre/post reference points, direct-gap formula and sign convention,
  three-lap default and five-lap maximum search window, confounding rules, and
  canonical visual contract. The initial template must expose measured gap
  change and source-backed derived elapsed components but no counterfactual
  estimate or generic estimated-net-change field.
  Optional `rejoin_context` and `execution_breakdown` panels must follow their
  canonical source, naming, retrospective, and availability contracts.
- **Rationale:** Analysts need to understand the whole stop cycle rather than
  equating one slow lap with pit loss.
- **Acceptance criteria:** The focal stop and rival are explicit parameters;
  pre/post points, formula, sources, sign, and window are persisted; position
  reversal crosses the direct-gap zero line; lap-valued gaps never become
  seconds; rival stops and neutralized periods mark the result confounded;
  missing gap or pit data produces a partial or unavailable result instead of
  fabricated values and never a silent empty primary panel; the session title
  identifies the focal stop ordinal and rival; the pre reference, pit-in,
  pit-out, and first eligible post reference are visibly labelled; the lower
  strip uses focal/rival row labels and a compound-only legend within the same
  comparison window; unrelated race-control context is omitted; rejoin context
  uses the exact-or-labelled-lap-bounded
  reference rule, lists at most two cars ahead and behind with focal-relative
  intervals, separates next observed event from relative position after three
  laps, applies the versioned 3.0-second traffic rule, and never predicts
  future stops; execution breakdown is headed by measured pit-lane duration,
  never infers stationary time from lap timing, shows signed comparison deltas,
  and suppresses performance ranking when comparison context is incompatible.
- **Verification method:** Calculation unit tests, partial-data fixtures,
  recipe tests, metadata inspection, and visual inspection.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-009: Driver Battle template

- **Statement:** The built-in registry must provide a Driver Battle template
  that consumes shared analytical results and implements the fixed three-panel
  canonical composition for exactly two drivers: representative pace, direct
  time gap with separate position fallback, and compound/tyre-age ribbons. It
  must not independently recalculate stint or pit-cycle results.
- **Rationale:** A single evidence artifact is useful for comparing a chosen
  battle while automatic strategic verdicts require a later analytical layer.
- **Acceptance criteria:** Exactly two drivers are required; every panel uses
  the same lap window and exclusion policy; partial context panels degrade
  independently; the summary uses direct time-gap change when available and
  otherwise reports a typed unavailable timing state; gap-to-leader, direct gap, and
  position are never treated as interchangeable; no causal strategy verdict is
  emitted; the title names the pair; pace lines have direct endpoint labels;
  pit markers align across all panels; the context panel uses driver row labels,
  compact compound-only legend entries, and visible stint/tyre-age information.
- **Verification method:** Validation tests, recipe and renderer tests,
  partial-data tests, and desktop/mobile visual inspection.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-010: Shared strategy parameter contract

- **Statement:** All seven templates must use normalized SPEC-006 parameter
  sections and shared fields for driver selection, ordering, lap range, stint
  selection, compound selection, exclusion policy, template-specific sample
  thresholds, comparison mode, reference, presentation, and diagnostics.
  Fields must declare Basic or Advanced mode and dependency conditions.
- **Rationale:** The templates must behave as one analytical family and remain
  manageable in the existing schema-driven editor.
- **Acceptance criteria:** Shared fields have identical names and semantics;
  the parameter structure is shared while conservative thresholds remain
  template-specific; template-specific fields are additive; invalid
  dependencies are blocked by diagnostics; requested and effective
  configuration is persisted.
- **Verification method:** Schema contract tests, normalization tests, API
  diagnostics tests, and frontend form tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-011: Versioned analytical methods

- **Statement:** Every generated strategy artifact must record a strategy
  analysis schema version, method identifiers and versions, requested and
  effective parameters, source coverage, included and excluded samples,
  result kind, measured/derived/reserved-estimated classification, warnings,
  and limitations.
- **Rationale:** Strategy outputs must remain reproducible and auditable as
  analytical methods evolve.
- **Acceptance criteria:** Re-generating from the same snapshot and effective
  configuration produces semantically identical analytical metadata; method
  changes require a version change; the LLM contract exposes bounded summaries
  of these fields.
- **Verification method:** Determinism tests, metadata schema tests, regeneration
  tests, and LLM contract tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-012: Fixed analyst presets

- **Statement:** The system must provide at least one versioned built-in preset
  per new template using conservative default exclusions and minimum-sample
  rules. Preset names must describe the analysis without claiming causal tyre
  degradation or optimal strategy.
- **Rationale:** Users need useful starting points without reconfiguring every
  advanced analytical field.
- **Acceptance criteria:** Presets validate against their template schema,
  remain editable after application, persist effective configuration, and pass
  migration tests across the strategy schema version.
- **Verification method:** Preset registry, schema, migration, and Workbench
  interaction tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### REQ-013: Race-Time Delta Evolution template

- **Statement:** The built-in registry must provide a Race-Time Delta Evolution
  template implementing the normative `measured_gap_change` and
  `derived_cumulative_pace_delta` modes, distinct titles and units, explicit
  comparator selection, positive-is-loss sign convention, coverage breaks,
  contextual annotations, and canonical visual contract.
- **Rationale:** Existing charts do not show where advantage or deficit
  accumulated across the complete selected race interval.
- **Acceptance criteria:** Measured mode uses only direct timing-stream gaps and
  normalizes the selected start point to zero; derived mode sums only paired
  representative-lap differences after a zero-valued first comparable point
  against exactly one explicitly declared comparator; missing focal or
  comparator selection blocks generation and never defaults to another driver;
  pit/neutralized/missing laps never become zero deltas; coverage gaps are empty
  spans with no connector and share one comparison legend identity; the title,
  y-axis, and visible sign copy name both drivers; pit markers explain stop-
  related discontinuities while neutralization bands remain visible; measured overall, focal-stint,
  green-running, and omitted-remainder summaries follow their declared
  semantics; measured gap and derived pace outputs cannot share result labels
  or metadata kinds; fixed tests cover driver reference, per-lap median, fastest-
  eligible benchmark, missing coverage, pit events, and lapped-driver gaps.
- **Verification method:** Calculation unit tests, timing and lap-data
  integration tests, recipe and renderer tests, metadata inspection, and
  desktop/mobile visual inspection.
- **Evidence location:** See the implementation evidence and requirement traceability below.

## Non-functional requirements

### NFR-001: Deterministic local-first analysis

- **Statement:** Strategy calculations and chart generation must operate from
  the saved local session snapshot and must not fetch network data during
  regeneration.
- **Rationale:** Saved analyses must remain reproducible and usable offline.
- **Acceptance criteria:** Cache-only regeneration succeeds after network
  access is disabled; repeated results are semantically identical; provenance
  remains attached.
- **Verification method:** Integration test and cache-only generation script.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### NFR-002: Interactive generation performance

- **Statement:** After a session snapshot is loaded, each individual strategy
  template must complete analytical calculation and default PNG/JSON generation
  within 3 seconds at the 95th percentile on the canonical 20-driver Bahrain
  fixture using the supported local runtime.
- **Rationale:** Templates are intended for iterative configuration in the
  Workbench.
- **Acceptance criteria:** A reproducible benchmark performs at least 20 warm
  runs per template and reports p50 and p95; every template satisfies the p95
  threshold or implementation stops for an approved amendment.
- **Verification method:** Dedicated benchmark script.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### NFR-003: Bounded scalability and readability

- **Statement:** Default charts must remain readable for a 20-driver race and
  must bound series, labels, tables, and metadata payloads without silently
  dropping analytical samples.
- **Rationale:** Full-field races can overwhelm both rendering and inspection.
- **Acceptance criteria:** Full-field fixtures generate without overlap that
  prevents interpretation; any presentation-only reduction is diagnosed and
  does not change calculations; metadata payload bounds are tested.
- **Verification method:** Renderer tests, payload tests, and visual inspection.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### NFR-004: Stable strategy extension boundary

- **Statement:** Shared strategy-lap and analytical-result models must be
  separated from built-in renderer code and made available to registered
  recipes without requiring plugin authors to import private UI modules.
- **Rationale:** The project’s plugin model should extend strategy analysis
  without duplicating internal calculations.
- **Acceptance criteria:** Dependency-boundary tests enforce the public
  boundary; one test plugin consumes the shared model; built-in and plugin
  recipes use the same versioned contract.
- **Verification method:** Dependency-boundary and plugin integration tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

## Security and privacy considerations

### SEC-001: Local snapshot boundary

- **Statement:** Strategy templates must read only the analysis’s loaded local
  snapshot and configured local plugin code; they must not transmit session,
  telemetry, timing, or analytical results to external services.
- **Rationale:** The application is local-first and analytical data must not be
  uploaded implicitly.
- **Acceptance criteria:** No strategy calculation path introduces an outbound
  client; dependency inspection confirms local-only behavior; plugins retain
  existing explicit enablement and validation boundaries.
- **Verification method:** Dependency inspection and boundary tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### SEC-002: Data-only configuration

- **Statement:** New strategy parameters, presets, and comparison expressions
  must remain validated data and must not accept executable Python, JavaScript,
  template code, or arbitrary file paths.
- **Rationale:** Analytical flexibility must not become a code-execution
  surface.
- **Acceptance criteria:** Schemas reject unknown executable fields and unsafe
  paths; frontend controls expose only typed values; API tests cover malicious
  strings as inert or invalid data.
- **Verification method:** Schema, API security, and UI inspection tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

## Data model impact

### DATA-001: Strategy lap model

- **Statement:** Add a versioned strategy-lap model containing driver, lap,
  effective stint, compound, tyre age value and source, lap time and sectors,
  position and timing context when available, `is_representative_for_pace`,
  `pace_exclusion_reasons`, `is_visible_in_context`, and
  `context_classifications`.
- **Rationale:** One normalized derived model prevents recipe-specific
  disagreement.
- **Acceptance criteria:** The model is serializable, deterministic, and
  validated; it does not mutate source snapshots; missing values remain
  explicit; fixtures cover full and partial records.
- **Verification method:** Model and derivation unit tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### DATA-002: Stint analytical summary

- **Statement:** Add a versioned stint-summary model containing stint bounds,
  compound, tyre-age coverage, measured and representative sample counts,
  summary statistics, observed pace-evolution result, source coverage,
  warnings, and limitations.
- **Rationale:** Multiple templates need the same stint-level calculations.
- **Acceptance criteria:** Summary values match fixed fixtures; insufficient
  samples use typed unavailable states; every statistic records units and
  sample basis.
- **Verification method:** Model, statistical, and serialization tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### DATA-003: Comparison and pit-cycle result models

- **Statement:** Add versioned comparison-result and pit-cycle-result models
  containing result kind, participants, interval, control rule, source fields,
  measured values, derived values, reserved versioned estimate fields, quality
  or status, warnings, and limitations. Initial pit-cycle results must not
  populate counterfactual estimate fields. Add typed cumulative-delta segment,
  rejoin-context, traffic-snapshot, and measured stop-execution results without
  conflating measured gap, derived pace, position, and pit timing.
- **Rationale:** Comparisons must be auditable and reusable beyond one chart.
- **Acceptance criteria:** Measured, derived, descriptive, and reserved
  estimated fields are typed and cannot be conflated; unrestricted compound
  distributions cannot carry scalar-difference fields; partial, confounded,
  and unavailable results are serializable; test results remain deterministic.
- **Verification method:** Model and calculation tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### DATA-004: Artifact metadata extension

- **Statement:** Strategy artifacts must embed or reference bounded analytical
  results while preserving existing artifact, manifest, review, and export
  compatibility.
- **Rationale:** Export and inspection need analytical evidence without
  breaking current consumers.
- **Acceptance criteria:** Existing artifact readers still load packages;
  strategy metadata is versioned; large per-lap evidence is bounded or stored
  in a referenced local JSON artifact with integrity checks.
- **Verification method:** Backward-compatibility, package integrity, and scale
  tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

## API impact

### API-001: Template and schema discovery

- **Statement:** Existing analysis template and recipe-schema discovery must
  expose all approved strategy templates, source labels, availability,
  supported session counts, required fields, normalized parameters, defaults,
  and dependency rules.
- **Rationale:** The existing Workbench and LLM tools must discover templates
  without hard-coded parallel configuration.
- **Acceptance criteria:** Discovery endpoints return all templates in stable
  order; missing required dataset fields produce availability diagnostics;
  schemas round-trip through frontend types.
- **Verification method:** API contract and frontend type tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### API-002: Strategy diagnostics

- **Statement:** Existing chart diagnostics and generation APIs must validate
  strategy parameters and return bounded diagnostics covering source coverage,
  effective exclusions, sample counts, comparison availability, and expected
  degraded states before generation.
- **Rationale:** Users should discover invalid or weak comparisons before
  waiting for a rendered artifact.
- **Acceptance criteria:** Diagnostics and generation apply identical effective
  rules; blocking errors prevent generation; warnings permit generation and
  appear in artifact metadata; tests prevent diagnostic/generation drift.
- **Verification method:** API and workspace integration tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### API-003: LLM-safe analytical inspection

- **Statement:** LLM inspection must expose template descriptions, parameter
  bounds, effective configuration, headline analytical results, quality grade,
  warnings, and limitations in bounded data-only payloads.
- **Rationale:** Agents need enough evidence to explain charts without reading
  unbounded raw telemetry or inventing unsupported claims.
- **Acceptance criteria:** Payloads contain no executable content or unbounded
  per-sample streams; measured, derived, descriptive, and reserved estimated
  values are distinguishable;
  truncation is explicit and deterministic.
- **Verification method:** LLM contract and payload-bound tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

## UI or UX impact

### UX-001: Existing Add Chart integration

- **Statement:** Strategy templates must appear in the existing Add Chart flow
  and use the existing chart editor, Basic/Advanced modes, parameter
  diagnostics, preview-first layout, Save, Generate, presets, stale state,
  Review, and Export behavior.
- **Rationale:** The first step is reusable chart primitives, not a parallel
  strategy application.
- **Acceptance criteria:** A user can add, configure, save, generate, reopen,
  edit, regenerate, remove, review, and export each strategy template through
  current Workbench patterns; no separate top-level page is introduced.
- **Verification method:** Frontend interaction tests and browser smoke checks.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### UX-002: Visible analytical basis

- **Statement:** Every strategy chart editor and generated result must expose a
  concise analytical-basis summary including active interval, drivers, stints
  or compounds, representative and excluded sample counts, comparison mode,
  and any quality or unavailable state.
- **Rationale:** Users must be able to judge what the chart actually measures.
- **Acceptance criteria:** The summary updates after parameter changes; warning
  details are accessible without editing raw JSON; exported metadata contains
  the same effective basis.
- **Verification method:** UI component tests, browser checks, and metadata
  comparison tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### UX-003: Analytical value-category presentation

- **Statement:** Pit-cycle and comparison charts must use labels, legends, and
  detail text that distinguish measured, derived, descriptive, confounded,
  unavailable, and any future versioned estimated values without relying on
  color alone. The initial pit-cycle chart must not display a counterfactual
  estimate.
- **Rationale:** Strategy estimates can otherwise appear more authoritative
  than their evidence supports.
- **Acceptance criteria:** Text or symbol semantics accompany color; raw values
  expose their category; accessibility inspection confirms the distinction;
  screenshots cover complete and partial-data states.
- **Verification method:** Component, accessibility, and visual tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### UX-004: Progressive parameter disclosure

- **Statement:** Basic mode must contain the minimum controls needed to produce
  a defensible chart, while sample thresholds, comparison-window rules,
  exclusion overrides, fit controls, diagnostics, and presentation tuning must
  remain in Advanced mode unless a dependency makes one immediately required.
- **Rationale:** Analytical rigor should not make normal chart creation
  unusably complex.
- **Acceptance criteria:** Each template has a reviewed Basic control set;
  dependency-required fields surface when needed; reset restores conservative
  defaults; desktop and mobile forms have no horizontal overflow.
- **Verification method:** Schema inspection, frontend tests, and responsive
  browser checks.
- **Evidence location:** See the implementation evidence and requirement traceability below.

### UX-005: Degraded and unavailable states

- **Statement:** When source coverage or comparable samples are insufficient,
  the UI must show a concise unavailable or partial state with the missing
  evidence and a safe next action such as widening the interval, selecting
  another driver, or inspecting source coverage.
- **Rationale:** Empty or misleading charts are worse than an explicit limit.
- **Acceptance criteria:** Each template has tested missing-data, insufficient-
  sample, and partial-data states; no state recommends changing filters in a
  way that would misrepresent the analysis; available chart functions remain
  usable.
- **Verification method:** Fixture-backed component and browser tests.
- **Evidence location:** See the implementation evidence and requirement traceability below.

## Configuration impact

- Add normalized shared `strategy` configuration fields under the existing
  parameter-section model rather than a new top-level configuration format.
- Proposed Basic shared fields: drivers, lap range, stint or compound selector,
  comparison reference where applicable, and conservative exclusion preset.
- Proposed Advanced shared fields: individual exclusion overrides, minimum
  representative samples using template-specific defaults, comparison control
  mode, pit-cycle window, optional context overlays, and diagnostics detail.
  The initial pace-evolution method is fixed rather than user-selectable.
- Existing flat parameter migration rules remain in force only where an
  existing field has an exact semantic equivalent.
- No new environment variables or external configuration files are required.

## Error handling

- Unknown template IDs or parameters are blocking validation errors.
- A driver, stint, compound, or pit stop not present in the loaded snapshot is
  a blocking configuration error.
- Fewer than the required representative samples is a typed unavailable result,
  not a zero, empty successful estimate, or renderer exception.
- Missing optional timing, weather, track-status, or tyre-age context yields a
  warning and a partial chart when the core chart remains defensible.
- Missing data required for the chart’s primary metric yields an unavailable
  result before rendering.
- Conflicting stint or compound records retain source evidence and produce a
  deterministic diagnostic; they are not silently reconciled by arbitrary
  source order.
- Failed analytical calculations must not overwrite the last successful chart
  artifact and must leave the chart stale with an actionable error.
- Export must report integrity failure if referenced strategy metadata or image
  artifacts are missing.

## Edge cases

- Drivers who start on used tyres or have unknown initial tyre age.
- Compound changes without a reliable stint number, and stint changes without
  a compound change.
- One-lap or two-lap stints, aborted stints, formation or first laps, and
  retirements.
- Pit stops under Safety Car, VSC, red flag, or missing timing-stream coverage.
- Drivers lapped by the leader and gap values represented in laps rather than
  seconds.
- Missing or unparseable gap-to-leader and interval-to-ahead values.
- Wet or mixed sessions with compound labels and weather changes.
- Track-status strings containing multiple status codes.
- Sparse sector data, deleted laps, generated laps, inaccurate laps, and
  telemetry or timing sampling gaps.
- Two compound samples that do not satisfy the selected control rule.
- A comparison dominated by one driver, team, or a very small sample.
- A full-field timeline with more labels than can be rendered legibly.
- Legacy analyses and packages created before the strategy schema exists.

## Acceptance criteria

This spec is satisfied when:

1. The approved set of seven strategy templates is registered and available
   through existing template discovery and Add Chart workflows.
2. All templates consume the same versioned strategy-lap, stint, exclusion,
   and comparison contracts.
3. Complete, partial, insufficient-sample, and unavailable states are verified
   with fixed fixtures.
4. Pace evolution is labelled and implemented as observed pace evolution, not
   fuel-corrected or causal tyre degradation.
5. Pit-cycle outputs distinguish measured and derived values, implement the
   normative gap contract, and omit counterfactual estimates.
6. Requested and effective configuration, samples, exclusions, methods,
   quality, warnings, and limitations are persisted and inspectable.
7. Existing chart, preset, diagnostics, plugin, review, export, and LLM
   contracts remain compatible.
8. Each template meets the approved performance and full-field readability
   checks.
9. Python tests, frontend checks, strategy benchmarks, governance validation,
   spec validation, and drift validation pass.

## Verification matrix

| Requirement ID | Acceptance criterion | Verification method | Test / command / manual check | Evidence location | PR reference |
| -------------- | -------------------- | ------------------- | ----------------------------- | ----------------- | ------------ |
| REQ-001 | Shared lap classifications and reasons are deterministic | Automated tests | Strategy derivation fixture tests | `tests/test_strategy_analysis.py` | Local worktree |
| REQ-002 | Defaults, overrides, and metadata exclusions agree | Automated tests | Parameter and recipe tests | `tests/test_strategy_analysis.py`; full unit suite | Local worktree |
| REQ-003 | Stint and tyre age never silently reset or conflict | Automated tests | Tyre-age boundary fixtures | `tests/test_strategy_analysis.py` | Local worktree |
| REQ-004 | Strategy Timeline renders full and partial races | Automated and manual | Recipe, renderer, responsive checks | Strategy recipe lifecycle test; desktop/mobile browser smoke | Local worktree |
| REQ-005 | Stint statistics match fixed values | Automated tests | Statistical and artifact tests | `tests/test_strategy_analysis.py` | Local worktree |
| REQ-006 | Robust observed pace evolution is deterministic and correctly labelled | Automated and inspection | Statistical, terminology, metadata tests | `tests/test_strategy_analysis.py` | Local worktree |
| REQ-007 | Compound modes enforce estimands, weighting, and result kinds | Automated and manual | Mode, weighting, and unavailable-state tests | `tests/test_strategy_analysis.py` | Local worktree |
| REQ-008 | Pit-cycle values preserve measurement category | Automated and manual | Calculation, metadata, visual tests | `tests/test_strategy_analysis.py`; generated artifact inspection | Local worktree |
| REQ-009 | Driver Battle synchronizes exactly two drivers and one interval | Automated and manual | Validation, renderer, browser tests | Lifecycle test; in-app browser chart inspection | Local worktree |
| REQ-010 | Shared schemas and dependencies are consistent | Automated tests | Schema, diagnostics, frontend tests | Workspace tests; frontend typecheck/build | Local worktree |
| REQ-011 | Analytical methods and evidence are versioned and reproducible | Automated tests | Determinism and LLM contract tests | Strategy and LLM tests | Local worktree |
| REQ-012 | Conservative presets validate and migrate | Automated and manual | Preset and Workbench tests | Migration and workspace tests | Local worktree |
| REQ-013 | Measured gap and derived cumulative pace modes remain distinct and coverage-aware | Automated and manual | Calculation, metadata, renderer, and browser tests | `tests/test_strategy_analysis.py` | Local worktree |
| NFR-001 | Regeneration is local and deterministic | Automated test | Cache-only integration test | Strategy workspace lifecycle test | Local worktree |
| NFR-002 | Each template meets the 3-second p95 target | Benchmark | Strategy benchmark, 20 warm runs/template | `scripts/benchmark_strategy_templates.py` (max isolated p95 1.543 s after AMEND-002) | Local worktree |
| NFR-003 | Full-field outputs remain bounded and readable | Automated and manual | Scale tests and visual checks | Benchmark fixture; desktop/mobile browser smoke | Local worktree |
| NFR-004 | Shared models form a stable extension boundary | Automated tests | Dependency and plugin tests | `tests/test_plugins.py` | Local worktree |
| SEC-001 | No implicit external transmission exists | Inspection and tests | Dependency and boundary checks | Shared local service implementation; full unit suite | Local worktree |
| SEC-002 | Configuration remains typed data only | Automated tests | Schema and API security tests | Pydantic models and workspace schema tests | Local worktree |
| DATA-001 | Strategy-lap records preserve source and exclusions | Automated tests | Model and derivation tests | `tests/test_strategy_analysis.py` | Local worktree |
| DATA-002 | Stint summaries are typed and deterministic | Automated tests | Model and statistics tests | `tests/test_strategy_analysis.py` | Local worktree |
| DATA-003 | Result models prevent measured, derived, descriptive, and estimated conflation | Automated tests | Model and calculation tests | `tests/test_strategy_analysis.py` | Local worktree |
| DATA-004 | Strategy metadata remains package-compatible and bounded | Automated tests | Compatibility and integrity tests | Strategy lifecycle and package export tests | Local worktree |
| API-001 | Discovery exposes complete typed template schemas | Automated tests | API contract and frontend type tests | Workspace tests; frontend typecheck | Local worktree |
| API-002 | Diagnostics and generation use identical rules | Automated tests | API/workspace parity tests | Strategy workspace lifecycle test | Local worktree |
| API-003 | LLM inspection is bounded and evidence-aware | Automated tests | LLM contract tests | Strategy lifecycle and LLM tests | Local worktree |
| UX-001 | Every template completes the current chart lifecycle | Automated and manual | Workbench interaction checks | Seven-template lifecycle test; browser smoke | Local worktree |
| UX-002 | Analytical basis is visible and matches metadata | Automated and manual | UI and metadata parity checks | Lifecycle test; in-app browser diagnostics inspection | Local worktree |
| UX-003 | Measurement categories are accessible and visible | Manual and automated | Accessibility and visual checks | Typed metadata tests; generated artifact inspection | Local worktree |
| UX-004 | Basic and Advanced controls remain usable | Automated and manual | Schema, UI, responsive checks | Frontend typecheck/build; desktop/mobile browser smoke | Local worktree |
| UX-005 | Degraded states are explicit and actionable | Automated and manual | Partial-data browser checks | Partial-data strategy tests and diagnostics contract | Local worktree |

## Test plan

### Unit tests

- Strategy-lap classification and exclusion precedence.
- Stint and compound boundary derivation.
- Source, derived, discontinuous, and unavailable tyre age.
- Median, trimmed mean, interquartile range, robust slope, residual dispersion,
  and deterministic quality grade.
- Comparable-window selection and insufficient overlap.
- Pit-cycle windows, gaps, lapped-driver states, and measurement categories.
- Measured direct-gap normalization and derived cumulative paired-lap sums.
- Coverage breaks, benchmark resolution, rejoin ordering, traffic grouping,
  later observed pit events, and measured pit-lane duration.
- Sector-specific fits and consistency-summary sorting.
- Model validation, serialization, versioning, and deterministic ordering.

### Integration tests

- All templates through recipe registry and Analysis Workspace generation.
- Stint Pace Summary, Pace Evolution sector mode, Pit-Cycle rejoin and
  execution panels, and Race-Time Delta Evolution modes through the same
  persisted chart lifecycle.
- Diagnostics/generation parity.
- Preset application and migration.
- Stale-state, save/generate separation, regeneration, removal, review, and
  export behavior.
- Package integrity and backward compatibility.
- LLM template discovery and generated-result inspection.
- Plugin consumption of the shared strategy model.

### Required test data

- Existing 2023 Bahrain Race fixture for full-field dry-race behavior.
- A compact synthetic fixture with exact expected laps, stints, compound
  changes, gaps, stops, exclusions, and analytical values.
- A partial-data fixture lacking tyre age, gap stream, track status, and
  weather independently.
- No additional real-race verification fixture is required by this spec.

### Frontend and browser checks

- Add, configure, diagnose, save, generate, reopen, regenerate, remove, review,
  and export every template.
- Basic/Advanced dependencies and reset behavior.
- Full-field desktop and mobile rendering with no horizontal overflow.
- Complete, partial, insufficient-sample, and unavailable states.
- Measured versus derived cumulative-delta labelling, rejoin traffic states,
  conditional execution components, and shared context overlays.
- Keyboard navigation and non-color measurement-category distinction.

### Commands expected at implementation completion

- `python -m unittest discover -s tests -p "test_*.py"`
- `python scripts/benchmark_strategy_templates.py`
- `pnpm --dir frontend typecheck`
- `pnpm --dir frontend build`
- `python scripts/validate_governance.py`
- `python scripts/validate_specs.py`
- `python scripts/validate_drift.py`

## Rollback plan

- Keep the new templates additive and leave existing recipes and saved analyses
  readable.
- Remove new registry entries, presets, UI exposure, and strategy-only APIs or
  fields while retaining existing chart artifact compatibility.
- Version strategy-derived models so saved metadata can be rejected with an
  explicit unsupported-version diagnostic rather than misread.
- Do not migrate or rewrite existing `tyre_strategy` chart instances until the
  compatibility decision is approved and separately verified.
- If a calculation is found analytically unsound, disable only the affected
  template through availability diagnostics while preserving other strategy
  templates and existing artifacts.

## Open questions

- [x] The approved delivery contains all seven templates, including Compound
  Comparison and Driver Battle.
- [x] Strategy Timeline replaces the current `tyre_strategy` implementation
  through a versioned expansion of the stable `tyre_strategy` recipe id. Saved
  chart instances remain readable: supported legacy parameters are normalized
  into the Strategy Timeline v2 schema, and parameters that cannot be mapped
  produce explicit migration diagnostics rather than being silently ignored.
  No separate `strategy_timeline` recipe id is introduced.

## Human decisions required

- [x] **Template scope:** All seven proposed templates are approved for the
  first delivery.
- [x] **Timeline compatibility:** The existing `tyre_strategy` recipe id is
  retained and receives the versioned Strategy Timeline contract and migration
  behavior recorded above.
- [x] **Spec approval:** Nelson Jeanrenaud explicitly approved SPEC-008 in the
  Codex implementation task on 2026-08-05.

## Conflict check

- SPEC-001 defines the extensible chart and artifact framework; SPEC-008 adds
  recipes within it.
- SPEC-004 defines the Analysis Workbench lifecycle; SPEC-008 reuses it and
  does not introduce a competing page.
- SPEC-005 and SPEC-006 govern template discovery, normalized parameter
  schemas, presets, diagnostics, renderer semantics, and reproducibility;
  SPEC-008 is additive and adopts those contracts.
- SPEC-007 defines race playback, timing, track status, tyre context, and
  manual playback decisions; SPEC-008 may consume the same saved snapshot data
  but does not behaviorally change Race Playback.
- The existing `tyre_strategy` versus proposed Strategy Timeline boundary is
  resolved by retaining the stable recipe id and replacing its implementation
  with the versioned Strategy Timeline contract and explicit migration
  diagnostics.
- No blocking authoritative conflict is currently identified;
  `conflicts_with` remains empty.

## Traceability table

| Requirement ID | Design / component | Implementation (file/function) | Test | Status |
| -------------- | ------------------ | ------------------------------ | ---- | ------ |
| REQ-001 | Shared strategy derivation | `strategy/service.py::derive_strategy_analysis` | `tests/test_strategy_analysis.py` | Implemented |
| REQ-002 | Exclusion policy | `strategy/models.py::StrategyExclusionPolicy`; workspace schema | Strategy classification and schema tests | Implemented |
| REQ-003 | Stint and tyre-age resolver | `strategy/service.py` stint/age derivation | Strategy fixture tests | Implemented |
| REQ-004 | Strategy Timeline recipe | `recipes/strategy_templates.py::StrategyTimelineRecipe` | Seven-template render/lifecycle tests | Implemented |
| REQ-005 | Stint Pace recipe | `recipes/strategy_templates.py::StintPaceRecipe` | Seven-template render/lifecycle tests | Implemented |
| REQ-006 | Pace Evolution recipe | `recipes/strategy_templates.py::PaceEvolutionRecipe` | Statistics and render tests | Implemented |
| REQ-007 | Compound Comparison recipe | `strategy/service.py::compare_compounds`; recipe wrapper | Comparison-mode tests | Implemented |
| REQ-008 | Pit-Cycle Comparison recipe | `strategy/service.py::compare_pit_cycle`; recipe wrapper | Pit-cycle and render tests | Implemented |
| REQ-009 | Driver Battle recipe | `recipes/strategy_templates.py::DriverBattleRecipe` | Lifecycle and browser checks | Implemented |
| REQ-010 | Shared strategy schema | `analysis/workspace.py::recipe_parameter_schema` | Workspace and frontend checks | Implemented |
| REQ-011 | Analytical metadata | Strategy result models and recipe metadata | Determinism and LLM tests | Implemented |
| REQ-012 | Built-in presets | `analysis/workspace.py` built-in strategy presets/migration | Workspace migration tests | Implemented |
| REQ-013 | Race-Time Delta Evolution recipe | `strategy/service.py::race_time_delta`; recipe wrapper | Measured/derived tests | Implemented |
| NFR-001 | Local snapshot execution | `AnalysisService` strategy lifecycle | Cache-fixture lifecycle test | Implemented |
| NFR-002 | Strategy benchmark | `scripts/benchmark_strategy_templates.py` | 20 warm runs/template | Verified |
| NFR-003 | Scale and readability | Bounded metadata and renderer panels | Benchmark and browser smoke | Implemented |
| NFR-004 | Plugin strategy boundary | `f1_telemetry_charts.strategy` public package | Plugin tests | Implemented |
| SEC-001 | Local data boundary | Shared local derivation service | Full unit suite | Implemented |
| SEC-002 | Typed configuration | Strategy Pydantic models and normalized schemas | Model/schema tests | Implemented |
| DATA-001 | Strategy lap model | `strategy/models.py::StrategyLap` | Strategy fixture tests | Implemented |
| DATA-002 | Stint summary model | `strategy/models.py::StintSummary` | Statistics/determinism tests | Implemented |
| DATA-003 | Comparison result models | Typed comparison, delta, and pit-cycle models | Measurement-category tests | Implemented |
| DATA-004 | Artifact metadata | Strategy recipe metadata and bounded summaries | Render/export/LLM tests | Implemented |
| API-001 | Discovery API | Recipe registry metadata and workspace schemas | Workspace/API tests | Implemented |
| API-002 | Diagnostics API | `AnalysisService.resolve_chart_diagnostics` | Lifecycle parity test | Implemented |
| API-003 | LLM inspection | `llm.inspect_analysis` strategy summaries | LLM contract tests | Implemented |
| UX-001 | Workbench lifecycle | Analysis Workbench strategy integration | Seven-template lifecycle/browser checks | Implemented |
| UX-002 | Analytical basis summary | Diagnostics view and frontend summary | Lifecycle/browser checks | Implemented |
| UX-003 | Measurement categories | Typed result metadata and renderer labels | Strategy/render tests | Implemented |
| UX-004 | Progressive controls | Workspace dependencies and frontend Basic/Advanced UI | Frontend/browser checks | Implemented |
| UX-005 | Degraded states | Explicit unavailable/confounded result states | Partial-data tests | Implemented |

## Implementation notes

- Implementation is authorized by the recorded 2026-08-05 human approval.
- Recommended architecture is one shared, renderer-independent strategy
  derivation service consumed by seven thin chart recipes. This prevents each
  recipe from independently defining stints, exclusions, tyre age, or pit
  cycles.
- The initial trend method, residual calculation, minimum distinct values, and
  quality-grade thresholds are fixed normatively in this draft. Five laps make
  a fit available but provisional; they do not imply strong trend evidence.
- Median and interquartile range are primary descriptive statistics. The
  secondary trimmed mean uses the normative 10% symmetric rule and records trim
  and effective sample counts.
- Automatic traffic classification is intentionally not required in this
  draft because the current normalized model does not guarantee a defensible
  local traffic measure for every lap. A later amendment may add it after the
  source and thresholds are specified. Analysts can still use timing context
  and explicit interval selection.
- Automatic undercut/overcut verdicts and natural-language observations remain
  later work. Pit-Cycle Comparison and Driver Battle provide evidence without
  asserting intent or causality.

## Spec amendments

### AMEND-001: Replace Strategy Timeline annotation and legend encoding

- **Approved:** 2026-08-05 by Nelson Jeanrenaud during implementation review.
- **Change:** Replace full-height pit-in/pit-out annotation lines and repeated
  driver-stint/event legend entries with row-local pit markers, one legend item
  per compound, coalesced subtle Safety Car/VSC background bands, driver-code
  y-axis labels, and distinct unknown-compound, missing-stint, and source-backed
  retirement encodings.
- **Reason:** The first implementation contained the correct analytical data
  but obscured stint comparison with event annotations and an overwhelming
  legend. This amendment replaces the encoding logic before further styling.
- **Compatibility:** The stable `tyre_strategy` recipe id, saved parameters,
  analytical results, and artifact metadata remain compatible. The renderer
  model gains optional row-label, hatch, edge, and point-marker presentation
  fields.

### AMEND-002: Final Strategy Timeline acceptance refinements

- **Approved:** 2026-08-05 by Nelson Jeanrenaud after implementation review.
- **Change:** Add one shared triangle `Pit stop` legend key, strengthen Hard
  contrast, add explicit source-backed `RET` endpoints, label VSC bands in the
  plot, order dry-compound legend keys Soft/Medium/Hard, keep the default free
  of optional analytical overlays, and use session-first default titles across
  all seven strategy templates (for example, `2023 Bahrain GP Race Strategy`).
- **Reason:** These refinements make the already-correct timeline structure
  self-explanatory and remove the remaining ambiguity without adding visual
  complexity.
- **Compatibility:** User-supplied titles and saved presentation selections are
  unchanged. Default titles and rendered presentation metadata change only for
  newly generated artifacts.

### AMEND-003: Focus Stint Pace on the selected stint domain

- **Approved:** 2026-08-06 by Nelson Jeanrenaud during Stint Pace review.
- **Change:** Default Stint Pace to stint-relative x, retain tyre age and race
  lap as explicit alternatives, clip context to selected stints, add distinct
  line styles and point markers, consolidate excluded laps, add direct endpoint
  labels and compact legend/subtitle copy, and expose representative count,
  median, IQR, and two-stint median delta in the rendered summary.
- **Reason:** The first rendering allowed an unrelated later VSC to expand a
  short head-to-head stint comparison and used indistinguishable same-team
  traces, leaving most of the chart empty and the comparison hard to read.
- **Compatibility:** Existing saved charts without an x-axis choice adopt the
  new `stint_progress` default. `race_lap` restores the former contextual x-axis;
  analytical stint statistics and exclusions are unchanged.

### AMEND-004: Separate excluded laps from the Stint Pace scale

- **Approved:** 2026-08-06 by Nelson Jeanrenaud during Stint Pace review.
- **Change:** Move excluded laps into a narrow strip above the representative
  plot, retain driver identity through hollow grey versions of each driver's
  marker, move the descriptive summary into a compact in-chart annotation box,
  and express the two-driver result as the faster driver's absolute median
  advantage.
- **Reason:** Slow excluded laps compressed the representative traces even
  though they were analytically omitted. The detached footer and signed
  subtraction also made the primary comparison slower to interpret.
- **Compatibility:** Representative samples, exclusions, statistics, x-axis
  choices, and signed delta metadata remain unchanged. Only the rendered
  presentation and human-readable comparison wording change.
- **Final acceptance refinement:** Reduce the exclusion strip height while
  explicitly labelling the hollow-marker convention, preserve exclusion
  reasons in metadata rather than static chart copy, and keep both direct
  labels and legend entries in exports. Nelson Jeanrenaud approved the template
  on 2026-08-06 with no additional analytical overlays.

### AMEND-005: Require and identify the Race-Time Delta comparator

- **Approved:** 2026-08-06 by Nelson Jeanrenaud during Race-Time Delta review.
- **Change:** Require an explicit focal/comparator driver pair, remove teammate
  and field-benchmark fallback, define the default derived display as cumulative
  pace difference normalized to zero at the first comparable point, identify
  the pair and subtraction sign in the title/y-axis/subtitle, consolidate all
  coverage segments under one legend identity, and add driver-specific pit-stop
  markers while retaining neutralization bands.
- **Reason:** The first output silently chose PER when no comparator was
  selected, exposed internal segment numbering, omitted the sign convention,
  and started a purported cumulative comparison away from zero.
- **Compatibility:** Saved charts with an explicit comparator remain valid and
  regenerate with corrected normalization and presentation. Saved charts that
  relied on implicit comparator fallback are invalid until a comparator is
  selected. The typed measured and derived result kinds remain distinct.
- **Final refinement:** Render a thin zero reference, state the concrete
  normalization lap in shorter subtitle copy, keep pit markers visually
  secondary, and record every rendered line break in metadata with per-lap
  `coverage_loss` or `excluded_comparison_window` classification and available
  exclusion reasons.
- **Template accepted:** Nelson Jeanrenaud approved Race-Time Delta on
  2026-08-09 after visual review of the amended output.

### AMEND-006: Center Pit-Cycle Comparison on one measured stop

- **Approved:** 2026-08-06 by Nelson Jeanrenaud during Pit-Cycle review.
- **Change:** Require an explicit focal driver, rival, and pit-in lap; identify
  the focal stop ordinal in the session-specific title; render the pre-stop,
  pit-in, pit-out, and first eligible post-stop references explicitly; limit
  both panels and race-control context to that focal window; replace the lower
  strategy crop with two driver-labelled compound rows and one compact compound
  legend; and show a typed partial/unavailable state with exact reasons whenever
  the measured direct-gap inputs cannot support the trace and net change.
- **Reason:** A pit-cycle chart without its direct-gap trace, focal event, or
  explicit reference boundaries cannot support the intended comparison. A
  silent empty plot and a generic strategy crop obscured whether the metric was
  missing or merely off-screen.
- **Compatibility:** Saved charts must now supply the focal driver, rival, and
  pit-in lap explicitly. Analytical output gains focal-stop/reference fields
  and typed unavailability reasons. No gap is inferred from position or lap-
  valued timing, and optional rejoin/execution analysis remains unchanged.
- **Final acceptance refinement:** Present the pre/post values as measured
  endpoints joined by a visually secondary dotted connector, describe the
  result as the focal driver's measured gain or loss relative to the rival,
  keep specific confounding reasons in warnings/metadata rather than the
  headline, and require the pit shading boundaries to equal the pit-in and
  pit-out markers exactly. The result remains observed window-level gap change
  and must never imply that the stop caused the change.
- **Final presentation cleanup:** Fit the measured endpoint panel's y-domain
  around its two values with proportional padding so the observed change stays
  legible, and omit its redundant series legend. Reference labels, sign-axis
  wording, and exported metadata remain sufficient to identify the values.
- **Template accepted:** Nelson Jeanrenaud approved Pit-Cycle Comparison on
  2026-08-09 after visual review of the amended output.

### AMEND-007: Rebuild Driver Battle around direct head-to-head gap

- **Approved:** 2026-08-07 by Nelson Jeanrenaud during Driver Battle review.
- **Change:** Make absolute focal-minus-rival direct gap the mandatory middle-
  panel metric and remove position fallback; identify the session and pair in
  the title; add start gap, end gap, and observed relative change to the header;
  simplify pace legend labels and add direct endpoint labels; align explicit
  driver pit markers across all panels; and replace repetitive stint legends
  with driver rows, compact compound keys, and visible stint/tyre-age labels.
- **Reason:** The prior chart combined individually useful panels without
  making the selected head-to-head battle its central signal. Position fallback
  and repeated stint legends obscured the direct timing comparison.
- **Compatibility:** Exactly-two-driver selection remains unchanged. Artifacts
  with insufficient numeric paired timing now show a typed unavailable middle
  panel instead of position. Measured absolute-gap points are added alongside
  the existing normalized gap-change result without changing Race-Time Delta
  semantics.
- **Wording refinement:** State the relative result directly, for example
  `VER gained 1.300 s relative to PER`, without an `Observed:` prefix. The
  measured endpoint basis and non-causal limitation remain in metadata.
- **Template accepted:** Nelson Jeanrenaud approved Driver Battle on 2026-08-09
  after visual review of the amended output.

### AMEND-008: Redesign Compound Comparison around compound evidence

- **Approved:** 2026-08-07 by Nelson Jeanrenaud during Compound Comparison review.
- **Change:** Replace internal numeric categories and per-stint legend series
  with categorical compound ticks, lightly jittered representative samples,
  compound-standard colours, outlined Hard points, median/IQR marks and exact
  labels, and per-compound sample counts. Show a compound-level headline only
  for a valid comparable-window scalar; otherwise label the artifact
  `Descriptive only` and emit no delta.
- **Reason:** The previous sample-series encoding wasted space, exposed internal
  positions, hid sample-size imbalance, and made it difficult to answer the
  compound-level question without over-reading unequal evidence.
- **Compatibility:** Comparison modes, eligibility rules, selected samples,
  scalar results, and driver/stint metadata remain unchanged. Artifact metadata
  gains compound-level count/median/quartile summaries and categorical tick
  labels; static per-stint legend entries are removed.
- **Final presentation refinement:** Replace crossbar summaries with a standard
  lightly filled IQR box and median line, place exact median/IQR copy close to
  its compound group, and fit the y-domain more tightly to the observed sample
  range. `Descriptive only` remains mandatory for the reviewed unequal-sample
  chart; no compound delta headline is added.
- **Label cleanup:** Center each `n=` label directly beneath its compound
  category tick so sample weight reads as part of that category.
- **Template accepted:** Nelson Jeanrenaud approved Compound Comparison on
  2026-08-09 after visual review of the amended output.

### AMEND-009: Make Pace Evolution fits directly interpretable

- **Approved:** 2026-08-07 by Nelson Jeanrenaud during Pace Evolution review.
- **Change:** Preserve team colour while differentiating selected drivers with
  the same marker-shape and line-style treatments as Stint Pace; show one
  compact visible row per fit containing signed slope in seconds per lap,
  representative sample count, and quality; label each fitted line directly at
  its observed endpoint; reduce the legend to driver identities; and state
  explicitly when source tyre age is unavailable and stint progress is used.
- **Reason:** The fit geometry was analytically valid but same-team drivers
  were visually indistinguishable, the derived result was only available in
  metadata, and the fallback x basis was not sufficiently prominent.
- **Compatibility:** The Theil-Sen calculation, representative-lap policy,
  absolute lap-time y-axis, and fit domain remain unchanged. Fits continue only
  across observed sample ranges. No confidence band or causal tyre-degradation
  wording is introduced. Sector Evolution mode is unchanged by this review.
- **Final presentation cleanup:** Omit the Pace Evolution legend because the
  direct endpoint labels identify every fit. Preserve the explicit basis
  subtitle in production, retain each raw representative sample at its observed
  value, and overlay the independently calculated fit without replacing or
  projecting the sample scatter.
- **Template accepted:** Nelson Jeanrenaud approved Pace Evolution on
  2026-08-09 after visual review of the amended output. Advanced variants remain
  subject to their own visual reviews.

### AMEND-010: Make Sector Pace Evolution a direct sector attribution view

- **Approved:** 2026-08-09 by Nelson Jeanrenaud during Sector Pace Evolution
  review.
- **Change:** Retain one panel per sector and raw representative samples, while
  adding each driver-sector's independently calculated observed fit, Stint Pace
  marker and line treatments, direct endpoint labels, and a compact panel-local
  slope/count/quality summary. Use one shared y-domain and x-domain across all
  three panels. State once in the subtitle the selected driver-stints,
  compound, tyre-age or stint-progress basis, and normalization to each
  driver's first representative sector sample; use the concise repeated axis
  label `Normalized sector-time delta (s)`.
- **Reason:** Scatter alone did not expose the derived evolution result, same-
  team drivers were indistinguishable, repeated legends obscured the plot, and
  independent y-scales could misrepresent which sector contributed most to the
  overall observed pace evolution.
- **Compatibility:** Raw sector samples, representative-lap eligibility,
  Theil-Sen calculation, per-driver normalization, and the three-panel layout
  remain unchanged. Fits remain bounded to each observed sample range. The
  chart makes no causal balance, fuel, degradation, or vehicle claim.
- **Variant accepted:** Nelson Jeanrenaud approved Sector Pace Evolution on
  2026-08-09 after visual review of the amended output. Direct endpoint labels
  remain the default, but they are the first presentation element to omit when
  a tighter export would crowd the right edge. No additional legends or
  annotations are added.

### AMEND-011: Make Stint Pace Summary row-led and median-first

- **Approved:** 2026-08-09 by Nelson Jeanrenaud during Stint Pace Summary
  review.
- **Change:** Label each y-axis row directly with its driver-stint identity,
  sort rows by median with the faster stint on top, strengthen the median mark,
  reduce min/max to a light secondary range, retain IQR as the darker primary
  interval, and replace all driver/stint legend entries with the single compact
  encoding key `dot = median`, `dark band = IQR`, and
  `light band = min/max`.
- **Reason:** Numeric row positions and repeated driver/stint interval keys made
  the correct analytical summary unnecessarily difficult to scan and allowed
  the min/max range to compete with the median and IQR.
- **Compatibility:** The x-axis, representative-lap eligibility, stored
  statistics, team colour, annotation-box values, and median-advantage wording
  are unchanged. This amendment changes only ordering and visual encoding in
  `consistency_summary` mode.
- **Variant accepted:** Nelson Jeanrenaud approved Stint Pace Summary on
  2026-08-09 after visual review. The final cleanup increases the light
  min/max range height slightly while keeping it thinner and lighter than the
  IQR band; all other accepted presentation remains unchanged.

### AMEND-012: Compress Pit Rejoin and Execution into one contextual strip

- **Approved:** 2026-08-09 by Nelson Jeanrenaud during Pit Rejoin/Execution
  variant review.
- **Change:** When rejoin context or execution breakdown is enabled, keep the
  measured focal-versus-rival gap result as the standalone headline and label
  the exact pre/post endpoints in the primary panel. Render one compact strip
  directly beneath the pit-cycle window. Its rejoin block shows only the
  nearest useful car-ahead interval, focal rejoin position, traffic
  classification, and next observed event. Its execution block shows only the
  focal stop's measured pit-lane duration, pit-in-to-pit-out source, and the
  unavailable stationary/entry/exit components.
- **Reason:** Separate full-height text panels made one pit-cycle analysis read
  as a report page. Post-three-lap state and comparison against another focal
  stop answer different analytical questions and distracted from the selected
  focal-versus-rival cycle.
- **Compatibility:** Rejoin participants, post-three-lap state, execution
  comparison candidates, signed duration deltas, compatibility flags, and raw
  timestamps remain in structured metadata/details. They are omitted only
  from this default static variant. Base Pit-Cycle Comparison behavior and all
  measured values are unchanged.
- **Final presentation cleanup:** Size the two driver bars at approximately 60%
  of each lower-panel row, retain the focal driver's explicit stop gap and the
  pit-interval shading, and keep the synchronized lower-panel event lines while
  omitting their repeated labels. Rename the strip `Additional context`; phrase
  the next event as `PER next stop: within 2 laps`; and omit a compound legend
  when every displayed segment uses the same compound. When compounds differ,
  retain the compact compound-only legend.
- **Variant accepted:** Nelson Jeanrenaud approved Pit Rejoin/Execution on
  2026-08-10 after visual review. The accepted default retains endpoint values
  and upper-panel event labels, uses unlabelled synchronized event lines and
  pit shading below, and conditionally shows compound keys only when the
  displayed compounds differ.

## Review checklist

- [x] spec_id is unique and follows the SPEC-XXX format.
- [x] Every requirement has an ID, statement, rationale, acceptance criteria,
      verification method, and evidence location.
- [x] Non-goals are listed.
- [x] Open questions are resolved or explicitly deferred.
- [x] Verification matrix covers every requirement.
- [x] Conflict check completed.
- [x] Human approval recorded before status set to Approved.
