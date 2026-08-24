---
doc_type: spec
spec_id: SPEC-012
title: Practice and Long-Run Reports
status: In Implementation
owner: Nelson Jeanrenaud
related_issue:
related_prs: []
delivery_refs:
  - https://github.com/Nelson-Jnrnd/F1_Telemetry_Charts/commit/027d5b2
affected_components:
  - practice analytical result providers
  - practice chart templates
  - report plan and review
  - publication selection and rendering
  - report package export
  - local preview UI
affected_interfaces:
  - Analysis Workbench Story view
  - Analysis Workbench Evidence view
  - Analysis Workbench Preview view
  - Analysis Workbench Export view
  - portable Markdown publication package
supersedes: []
superseded_by:
depends_on:
  - SPEC-001
  - SPEC-004
  - SPEC-006
  - SPEC-008
  - SPEC-009
  - SPEC-010
  - SPEC-011
conflicts_with: []
last_verified_at: 2026-08-24
---

# SPEC-012: Practice and Long-Run Reports

## Summary

This spec adds publication-ready reporting for one standard Formula 1 Free
Practice session: FP1, FP2, or FP3. It extends the reviewed analytical-result
and publication authority from SPEC-009 through SPEC-011 with practice-specific
session order, run reconstruction, representative-lap filtering, long-run pace,
observed pace evolution, and condition context. The reader report distinguishes
the official fastest-lap order from supported long-run observations and states
sample comparability before comparing drivers. It never presents unknown fuel
load, engine mode, setup, tyre preparation, or programme intent as measured or
corrected fact. This is a single-session Practice increment, not a weekend
forecasting or race-prediction system.

## Context

SPEC-008 defines representative-lap, robust pace-summary, and observed-pace-
evolution contracts for Race stints. SPEC-009 makes typed analytical results the
authority for findings, evidence, review, and freshness. SPEC-010 adds selective
reader rendering, human framing, readiness, and portable export. SPEC-011 proves
that a second session type can extend those shared contracts while retaining
session-specific providers, policy, charts, and article structure.

Practice has different evidence limits. Official classification records the
fastest lap, but teams run different programmes with unobserved fuel loads,
engine modes, setup experiments, tyre histories, and objectives. A sequence of
timed laps can support an observed long-run pace distribution and within-run
trend. It does not by itself reveal race pace, tyre degradation, competitive
order, or intent. SPEC-012 therefore treats transparency about programme and
comparability as part of the analytical result, not as optional disclaimer copy.

## Problem statement

The application cannot currently turn a Practice session into a selective,
traceable article. Users must manually separate short runs from sustained
running, exclude non-representative laps, compare unequal samples, reconstruct
conditions and interruptions, and repeatedly explain why apparent pace is not
fuel-corrected. Reusing Race or Qualifying semantics would either overstate the
evidence or obscure the questions a Practice report must answer.

## Goals

- Report the official Practice classification and session context accurately.
- Reconstruct pit-bounded runs without inferring their operational intent.
- Identify long-run samples through an explicit, versioned eligibility policy.
- Summarise observed pace level, consistency, and within-run evolution.
- Compare runs only when their recorded evidence is sufficiently compatible.
- Keep short-run and long-run evidence visibly separate.
- Produce a concise, traceable Practice article with purposeful charts.
- Validate dry, interrupted, and wet or mixed-condition Practice packages.

## Non-goals

- Combining FP1, FP2, FP3, Qualifying, Sprint, or Race into a weekend report.
- Predicting qualifying order, race pace, stint length, strategy, or result.
- Estimating or correcting fuel load, engine mode, energy deployment, setup,
  tyre preparation, traffic loss, or team programme intent.
- Calling an observed lap-time slope tyre degradation or fuel burn-off.
- Comparing different compounds through an automatic scalar performance delta.
- Theoretical best laps, telemetry-based setup diagnosis, or vehicle ranking.
- Sprint practice, testing sessions, rookie tests, or historic non-standard
  Practice formats whose semantics are not FP1, FP2, or FP3.
- Live reporting, external editorial research, CMS publication, or autonomous
  ghostwriting.

## Users or actors

- A motorsport analyst reviewing Practice timing, telemetry, and evidence.
- A publication author selecting and framing the supported Practice story.
- A motorsport editor accepting the final draft.
- The local Analysis Workbench, report authority, and package exporter.
- Optional read-only LLM consumers of bounded report summaries.

## Authoritative concepts

### Practice evidence hierarchy

- Official session results own Practice classification, position, fastest time,
  status, and classified driver identity.
- Lap timing owns lap chronology, recorded lap and sector times, validity,
  compound, tyre age when available, and pit-boundary reconstruction.
- Track-status and weather records independently own interruptions and recorded
  conditions.
- Aligned positional timing or telemetry owns proximity context. A slow lap or
  sector alone does not establish traffic.
- No available source in this scope owns fuel load, engine mode, setup, tyre
  treatment, or programme intent. These remain unknown unless a future approved
  spec introduces an authoritative source and method.

A lower-authority source may not silently replace official classification.
Disagreement or missing data produces a typed partial, unavailable, unknown, or
source-conflict state.

### Measurement categories

- **Measured:** source-recorded classification, lap and sector times, compound,
  tyre age, pit boundaries, track status, weather, and positional proximity.
- **Derived:** run grouping, eligibility, pace summaries, coverage, robust trend,
  and compatible-window differences calculated from measured inputs.
- **Descriptive:** bounded statements about the observed sample without cause.
- **Estimated:** model-dependent corrections or predictions. SPEC-012 does not
  automatically select estimated Practice material.

Measurement category is not an evidence-strength hierarchy. Coverage,
comparability, quality, confounding, and relevance remain independent.

### Timed lap, representative lap, run, and long run

A timed lap is one source-recorded completed lap with a finite lap time. A
representative lap applies SPEC-008's explicit exclusions only: pit-in and
pit-out, inaccurate, deleted or generated timing, and recorded neutralisation
or other non-green track status are applied with exact reasons. No additional statistical outlier-
removal rule is applied. Laps without an explicit exclusion reason remain in
the analytical sample. Missing sectors do not exclude an otherwise valid lap-
time sample unless a complete-sector analysis requires them. Excluded laps
remain inspectable.

A run is a pit-out to pit-in sequence containing zero or more timed laps.
Incomplete pit boundaries produce a partial run; the system does not invent pit
events. `Run N` is a neutral chronology label and does not imply short-run,
long-run, qualifying simulation, race simulation, push, cooldown, or programme.

A sustained-run sample is one run with five to seven representative timed laps
and the same number of distinct run-progress values on one recorded compound
class. It is inspectable evidence, but is not called a long run and is excluded
from automatic pace, comparison, and trend publication.

A long-run sample is one run with at least eight representative timed laps and
eight distinct run-progress values on one recorded compound class. The threshold
establishes analytical availability, not team intent. A run with fewer than five
representative laps remains a shorter-run sample and may support official or
lap-level context only.

### Long-run analytical contract

Each sustained-run or long-run sample records representative and excluded laps,
type-7 median and quantiles, interquartile range, 10% symmetric trimmed mean
under the existing SPEC-008 summary contract, and a Theil-Sen observed-pace-
evolution fit over run progress. The fit records slope, intercept, residual MAD,
sample count, coverage, method, and version. Five to seven representative
samples produce a provisional evidence-only fit. At least eight representative
samples and eight distinct x values are required for long-run status and any
automatic pace-evolution publication. Negative slopes are retained.

The slope is described only as observed pace evolution. It may reflect fuel
burn-off, tyre state, traffic, track evolution, weather, management, damage,
deployment, or execution. It is never automatically described as degradation.

### Run comparability

Two long-run samples are `comparable` only when both are current, use the same
recorded dry compound or the same wet-condition compound class, share an
overlapping session-time window, have no material track-status boundary inside
that window, and have compatible recorded wet/dry conditions. Reliable source
tyre age is mandatory: it must be present, non-decreasing, free of an unexplained
reset, and provide at least eight shared tyre-age values with one representative
lap from each run at every value. The scalar comparison is the type-7 median of
the paired lap-time differences at those shared tyre ages, not the difference
between unmatched whole-run medians. Missing or insufficient tyre-age evidence
produces `unknown` and exposes no publishable scalar; a known compound,
condition, or track-status mismatch produces `confounded`.

Even a `comparable` result is an observed-sample comparison, not a fuel-corrected
ranking. Different compounds remain separate descriptive evidence. Automatic
publication may state a paired median difference only for a comparable
same-compound, shared-tyre-age window and must name the drivers, runs, compound,
session-time window, shared tyre-age range, paired sample count, and unknown
fuel/programme limitation.

### Practice publication policy version 1

Only current, reviewed findings with the provider-owned `reportable`
disposition are lead candidates. Default lead selection uses this fixed
editorial priority:

1. Reportable session-changing conditions or interruption.
2. A `comparable` matched long-run comparison.
3. A reportable individual long-run observation.
4. A reportable fastest-lap or short-run observation.
5. Official classification as the fallback lead.

The labels `significant`, `meaningful`, and `strongest supported story` are not
selection inputs. Candidate ordering is the deterministic tuple:

1. editorial category in the fixed order above;
2. evidence quality, ordered `high`, `medium`, `low`, `provisional`;
3. absolute effect size, largest first; and
4. stable result ID, ascending, as the final tie-break.

No weights, cross-category score, or editorial machine-learning model is used.
Effect size is the candidate's typed provider-owned scalar in seconds:

- conditions or interruption: recorded session duration materially affected;
- matched long-run comparison: absolute paired median lap-time difference;
- individual long-run observation: absolute fitted end-to-start lap-time change
  over the observed run range;
- fastest-lap or short-run observation: absolute referenced lap-time difference.

Provider reportability remains governed by explicit versioned criteria under
the SPEC-009 contract. Candidates without a finite effect size remain eligible
in their category but rank after candidates with one; stable result ID resolves
the remaining tie. Official classification is always prominent and mandatory
even when another category leads.

Additional selection constraints are fixed:

- A long run may be selected when it has at least eight representative laps and
  at least 75% representative coverage; a five-to-seven-lap sustained-run sample
  remains provisional and evidence-only.
- A same-compound long-run comparison may be selected only when the
  comparability contract returns `comparable`; unmatched distributions may
  remain descriptive Evidence, but unrestricted, unknown, or confounded samples
  expose no scalar comparison.
- Observed pace evolution may be selected only from a long run with at least
  eight representative laps, at medium or high quality under the SPEC-008 fit-
  quality contract, and with the non-causal basis stated.
- Short-run order and long-run order are never merged into one competitive
  ranking or used to predict Qualifying or Race.
- Traffic is reader-visible only when aligned evidence ties proximity to one
  identified representative or excluded lap and supports a bounded
  compromised-lap assessment. Generic proximity counts never become findings.

## Functional requirements

### REQ-001: Enforce standard Practice scope

- **Statement:** SPEC-012 must accept one standard FP1, FP2, or FP3 session and
  reject all other session types without introducing a generic weekend target.
- **Rationale:** Practice sessions share the contract in this spec; Qualifying,
  Sprint, Race, testing, and weekend synthesis require different authority.
- **Acceptance criteria:** FP1, FP2, and FP3 targets are accepted independently;
  Qualifying, Sprint, Sprint Qualifying, Race, testing, and multi-session targets
  return explicit unsupported-scope diagnostics; public types and UI copy use
  Practice terminology.
- **Verification method:** Scope, schema, dispatch, and UI inspection tests.
- **Evidence location:** To be filled during implementation.

### REQ-002: Reuse the existing report authority

- **Statement:** Practice results, findings, review, publication selection,
  framing, freshness, preview, and export must extend the SPEC-009 through
  SPEC-011 authority; no parallel Practice narrative store may be created.
- **Rationale:** Review, evidence, and freshness must remain coherent.
- **Acceptance criteria:** One persisted authority produces analyst and reader
  renderings; Practice findings reference typed results; Race and Qualifying
  behavior and stored packages remain unchanged.
- **Verification method:** Architecture inspection, persistence tests, and Race
  and Qualifying regression suites.
- **Evidence location:** To be filled during implementation.

### REQ-003: Preserve source authority and explicit unknowns

- **Statement:** Every Practice result must record source, measurement category,
  session and run boundaries, coverage, quality, limitations, and availability;
  unknown programme variables must remain explicit.
- **Rationale:** Practice timing is easy to overinterpret when fuel and intent
  are not observed.
- **Acceptance criteria:** Complete, partial, unavailable, unsupported,
  unknown-comparability, confounded, and source-conflict fixtures produce stable
  typed states; no generated result claims fuel correction, engine mode, setup,
  tyre preparation, programme intent, or causal degradation.
- **Verification method:** Provider truth tables, degraded fixtures, and phrase
  policy tests.
- **Evidence location:** To be filled during implementation.

### REQ-004: Materialise official Practice classification

- **Statement:** The analysis must materialise one versioned
  `practice_classification` result from the official session result source.
- **Rationale:** The report needs the recorded session outcome before analysis.
- **Acceptance criteria:** The result records classified order, fastest times,
  gaps when officially available, lap counts, and statuses; ties, no-time,
  withdrawn, disqualified, and incomplete entries remain explicit; classification
  is never reconstructed by sorting lap timing when official data is absent.
- **Verification method:** Complete and exceptional classification fixtures.
- **Evidence location:** To be filled during implementation.

### REQ-005: Reconstruct neutral run chronology

- **Statement:** The analysis must materialise one versioned
  `practice_run_chronology` result containing pit-bounded runs and all timed-lap
  records in session-time order.
- **Rationale:** Long-run analysis requires transparent sample boundaries.
- **Acceptance criteria:** Each run records driver, ordinal, pit boundaries,
  compound and tyre-age evidence, representative and excluded laps, exact
  exclusion reasons, and boundary confidence; incomplete boundaries produce a
  partial run; labels do not infer push, cooldown, simulation, or programme.
- **Verification method:** Run sequence, pit-boundary, and exclusion tests.
- **Evidence location:** To be filled during implementation.

### REQ-006: Materialise long-run pace summaries

- **Statement:** The analysis must materialise one independently identified
  `practice_long_run_pace` result per sustained-run or long-run sample using the
  authoritative analytical contract.
- **Rationale:** A Practice report needs robust sample summaries without hiding
  exclusions or unequal evidence.
- **Acceptance criteria:** Each result records median, trimmed mean, IQR,
  minimum, maximum, representative count, excluded count, coverage, compound,
  tyre-age coverage, session-time window, and shorter-run, sustained-run, or
  long-run status; five-to-seven-lap samples are sustained runs and evidence-
  only; fewer than five laps is unavailable for sustained-run analysis; fewer
  than eight laps is unavailable for long-run claims.
- **Verification method:** Summary arithmetic, threshold, and round-trip tests.
- **Evidence location:** To be filled during implementation.

### REQ-007: Materialise observed pace evolution

- **Statement:** The analysis must materialise one independently identified
  `practice_observed_pace_evolution` result per sustained-run or long-run sample
  using the versioned SPEC-008 Theil-Sen and residual-MAD method on run progress
  and, when complete, a separate tyre-age basis.
- **Rationale:** Within-run change can be described without pretending its cause
  is known.
- **Acceptance criteria:** Result identity distinguishes run-progress and
  tyre-age bases; slope, units, sample count, coverage, residual MAD, quality,
  method, and limitations are present in Evidence; bases are never mixed; fewer
  than five samples is unavailable; five to seven is provisional and evidence-
  only; automatic publication requires at least eight samples and medium or high
  quality; generated wording never calls the slope degradation.
- **Verification method:** Fixed numerical fixtures, basis separation, quality,
  and language tests.
- **Evidence location:** To be filled during implementation.

### REQ-008: Compare only compatible long-run windows

- **Statement:** The analysis must materialise versioned
  `practice_long_run_comparison` results only through the run-comparability
  contract in this spec.
- **Rationale:** Uncontrolled full-run averages create false precision.
- **Acceptance criteria:** Every comparison records both run identities,
  compound, overlap window, samples, tyre-age and condition states, status, and
  limitations; only `comparable` same-compound windows with at least eight
  shared recorded tyre ages expose the median of paired lap-time differences for
  automatic publication; missing or insufficient tyre age is `unknown` and
  exposes no scalar; confounded, unrestricted, and different-compound samples
  remain descriptive and unranked.
- **Verification method:** Comparability truth table and matched-window tests.
- **Evidence location:** To be filled during implementation.

### REQ-009: Materialise independently owned Practice context

- **Statement:** The analysis must materialise separate versioned
  `practice_conditions`, `practice_interruptions`, and
  `practice_traffic_context` results with independent fingerprints and
  freshness.
- **Rationale:** Missing traffic must not degrade weather or interruption truth.
- **Acceptance criteria:** Each result has independent provenance, coverage,
  assessment, and review; conditions use recorded weather and compound evidence;
  interruptions use track status or control timing; traffic requires aligned
  positional timing or telemetry tied to one identified lap, is not inferred
  from lap time, and never promotes generic proximity counts into findings;
  unsupported context does not block unrelated results.
- **Verification method:** Independent freshness and source-coverage tests.
- **Evidence location:** To be filled during implementation.

### REQ-010: Use provider ownership and deduplication

- **Statement:** All Practice result types must register through the SPEC-009
  provider contract and receive its assessment, disposition, fingerprint,
  deduplication, finding, evidence, and review behavior.
- **Rationale:** Practice must not bypass the established analytical boundary.
- **Acceptance criteria:** Each unique result has one assessment; repeated chart
  support does not duplicate findings; unavailable, provisional, context-only,
  unknown, or confounded results do not become automatic claims.
- **Verification method:** Registry, identity, disposition, and deduplication
  tests.
- **Evidence location:** To be filled during implementation.

### REQ-011: Select a Practice story deterministically

- **Statement:** A named, versioned Practice policy must propose a small,
  compatible set of canonical claims, summary references, and chart placements
  from current reviewed evidence.
- **Rationale:** A useful Practice article is selective, not a timing dump.
- **Acceptance criteria:** The policy follows version 1 in Authoritative
  concepts; lead candidates follow the fixed five-category order, then evidence
  quality, absolute typed effect size, and stable result ID; no score or weights
  exist; official classification remains prominent and is the fallback lead;
  official order is distinct from long-run observation; unavailable,
  provisional, unknown, confounded, estimated, or low-quality comparisons are
  excluded by default; one claim has one detailed placement.
- **Verification method:** Determinism, ranking, compatibility, and placement
  tests.
- **Evidence location:** To be filled during implementation.

### REQ-012: Use a Practice-specific article structure

- **Statement:** The publication plan must support, in order, Headline,
  Standfirst, Session Context, Official Classification, Relevant Runs, optional
  Matched Long-Run Comparison, optional Observed Run Trend, Conclusion, and
  Methods and Evidence.
- **Rationale:** Practice requires a clear separation between recorded order and
  sustained-running evidence.
- **Acceptance criteria:** Empty optional sections disappear; the lead follows
  the fixed Practice editorial priority and does not default to official order
  when a higher-category reportable candidate exists;
  absolute lap times render as `M:SS.mmm`; the article does not use `Run
  Programmes`, label a run as a simulation, create a race-pace ranking, or
  predict the weekend outcome.
- **Verification method:** Plan validation, golden Markdown, and phrase tests.
- **Evidence location:** To be filled during implementation.

### REQ-013: Provide three purposeful Practice charts

- **Statement:** SPEC-012 must provide a Practice run overview, long-run pace
  summary, and observed pace evolution chart backed by typed results, with
  separate Evidence and publication presentations.
- **Rationale:** These answer chronology, pace level/spread, and within-run
  change without duplicating one another.
- **Acceptance criteria:** Evidence may show the full-field overview with every
  driver's pit-bounded runs, compound, representative count, conditions, and
  recorded interruptions; automatic article charts include only drivers and
  runs relevant to selected canonical claims and never default to a full-field
  run overview; the pace summary shows median, IQR, sample count, tyre-age match
  status, and compatibility without ranking incompatible rows; the reader-facing
  evolution chart shows representative laps and the trend line with concise run,
  compound, and axis-basis labels, while estimator method, residual MAD, fit
  quality, detailed exclusions, and other statistical diagnostics remain in
  Evidence; all absolute lap-time axes use `M:SS.mmm`.
- **Verification method:** Recipe, renderer, metadata, and visual tests.
- **Evidence location:** To be filled during implementation.

### REQ-014: Enforce chart economy and structured framing

- **Statement:** Automatic publication must choose zero to three non-duplicative
  charts and authors must provide Practice-specific framing through existing
  structured editorial fields.
- **Rationale:** Evidence quality, not inventory, should determine article size.
- **Acceptance criteria:** Every selected chart has one purpose, placement,
  caption, alt text, and result references; more than three requires explicit
  editorial inclusion; headline, standfirst, section ledes, captions, alt text,
  and conclusion survive refresh as review-required when dependencies change;
  framing cannot make unsupported causal or predictive claims in a ready package.
- **Verification method:** Selection, persistence, freshness, and phrase tests.
- **Evidence location:** To be filled during implementation.

### REQ-015: Validate, render, and export Practice publication packages

- **Statement:** The shared workflow must evaluate one explicit `Publication
  draft ready` decision and export clean Practice Markdown, metadata, selected
  chart assets, evidence sidecar, publication plan, and health manifest.
- **Rationale:** A ready package must remain usable and auditable outside the
  workspace.
- **Acceptance criteria:** Readiness requires current official classification,
  current selected results, reviewed claims, complete required framing, valid
  charts, exact preview, package integrity, no duplicate placement, and no
  unsupported fuel, intent, degradation, causal, or predictive language;
  unavailable optional context does not block a report when no selected claim
  depends on it; package-relative assets resolve after relocation and reader
  claims resolve to evidence IDs.
- **Verification method:** Readiness matrix, golden, leakage, relocation, parity,
  and integrity tests.
- **Evidence location:** To be filled during implementation.

### REQ-016: Produce three Practice acceptance packages

- **Statement:** Acceptance must preserve one dry, one materially interrupted,
  and one wet or mixed-condition Practice package from distinct real sessions
  through the application workflow.
- **Rationale:** Dry uninterrupted running cannot validate sparse, stopped, and
  condition-sensitive samples.
- **Acceptance criteria:** The dry package includes at least two eligible long
  runs and one same-compound comparison; the interrupted package demonstrates
  run boundaries and exclusions around a recorded stoppage; the wet or mixed
  package demonstrates condition-aware comparison rejection or qualification;
  every package is source-identified, healthy or intentionally readiness-
  blocked for a documented reason, reviewed against one rubric, and includes at
  least one honest unavailable or excluded state.
- **Verification method:** End-to-end generation, package inspection, and human
  editorial acceptance.
- **Evidence location:** To be filled during implementation.

## Non-functional requirements

### NFR-001: Deterministic and reproducible output

- **Statement:** Practice results, assessments, findings, charts, selection,
  readiness, and rendering must be deterministic for identical source snapshots
  and policy versions.
- **Rationale:** Review and freshness require stable identity.
- **Acceptance criteria:** Repeated runs preserve fingerprints, ordering,
  calculations, selection, and Markdown apart from explicit timestamps.
- **Verification method:** Repeated-run comparison tests.
- **Evidence location:** To be filled during implementation.

### NFR-002: Analytical language safety

- **Statement:** Generated and readiness-approved copy must distinguish
  measured, derived, descriptive, estimated, unavailable, unknown, and
  confounded material and must not convert observed Practice timing into cause
  or prediction.
- **Rationale:** Hidden Practice variables make confident interpretation unsafe.
- **Acceptance criteria:** Phrase-policy tests reject unsupported fuel, engine-
  mode, setup, tyre-treatment, traffic-loss, programme-intent, degradation,
  qualifying prediction, race-pace ranking, and result-prediction claims.
- **Verification method:** Positive and negative phrase fixtures plus review.
- **Evidence location:** To be filled during implementation.

### NFR-003: Publication quality

- **Statement:** A ready report must let a competent motorsport editor improve
  voice and emphasis without reconstructing session order, run boundaries,
  comparison bases, or evidence limitations.
- **Rationale:** This is the practical definition of publication-ready.
- **Acceptance criteria:** All three packages pass one recorded rubric for
  correctness, restraint, readability, chart purpose, and traceability, with no
  required structural rewrite.
- **Verification method:** Human editorial review.
- **Evidence location:** To be filled during implementation.

### NFR-004: Responsive and accessible review

- **Statement:** Practice Story, Evidence, Preview, and charts must remain
  keyboard-operable and readable at desktop and 390x844 viewports.
- **Rationale:** Full-field Practice data is dense and must remain reviewable.
- **Acceptance criteria:** No horizontal page overflow; states are not encoded
  by color alone; controls have accessible names; charts have descriptions and
  alt text; full-field labels remain legible or use explicit pagination/scroll.
- **Verification method:** Frontend checks and browser inspection.
- **Evidence location:** To be filled during implementation.

## Security and privacy considerations

### SEC-001: Safe Markdown and package containment

- **Statement:** Practice editorial fields, metadata, Markdown, and asset paths
  must use the established sanitisation and package-containment rules.
- **Rationale:** Source and human text must not create injection or path escape.
- **Acceptance criteria:** Injection fixtures render inertly; asset paths remain
  package-relative and cannot traverse outside the export root.
- **Verification method:** Existing security suite plus Practice fixtures.
- **Evidence location:** To be filled during implementation.

### SEC-002: Local-only publishing handoff

- **Statement:** SPEC-012 must not transmit reports, evidence, or telemetry to
  an external service.
- **Rationale:** The approved workflow is local and user-controlled.
- **Acceptance criteria:** No new network publishing dependency or automatic
  upload path exists; export writes only to the selected local destination.
- **Verification method:** Dependency and API inspection.
- **Evidence location:** To be filled during implementation.

## Data model impact

### DATA-001: Versioned Practice result schemas

- **Statement:** Practice classification, chronology, run pace, evolution,
  comparison, conditions, interruptions, and traffic results must use versioned
  typed schemas with stable identities.
- **Rationale:** Evidence must survive persistence, refresh, and policy change.
- **Acceptance criteria:** Schemas validate complete and degraded states; result
  fingerprints include semantic inputs and exclude presentation-only fields;
  stored Race and Qualifying packages remain readable.
- **Verification method:** Schema, fingerprint, compatibility, and round-trip
  tests.
- **Evidence location:** To be filled during implementation.

### DATA-002: Practice publication plan

- **Statement:** The publication plan must record Practice policy ID/version,
  section order, canonical claim placements, chart placements, structured
  framing, evidence references, and readiness state.
- **Rationale:** Selection and rendering need one persisted authority.
- **Acceptance criteria:** Invalid sections, duplicate claim placement, stale
  references, incompatible comparisons, and missing chart metadata are rejected;
  valid plans round-trip without loss.
- **Verification method:** Model validation and persistence tests.
- **Evidence location:** To be filled during implementation.

### DATA-003: Long-run sample auditability

- **Statement:** Every long-run summary and comparison must retain the exact
  included and excluded lap identities, exclusion reasons, run boundaries,
  compound, tyre-age state, condition state, and policy versions.
- **Rationale:** Aggregate Practice claims must be reproducible from evidence.
- **Acceptance criteria:** A reviewer can reconstruct every published scalar and
  fit from the sidecar; no excluded lap contributes to summaries or trends.
- **Verification method:** Evidence reconstruction tests.
- **Evidence location:** To be filled during implementation.

## API impact

### API-001: Practice workflow operations

- **Statement:** Existing analysis, review, preview, readiness, and export APIs
  must accept Practice targets and return typed, stale-safe, atomic responses.
- **Rationale:** Practice should use the established application workflow.
- **Acceptance criteria:** APIs expose explicit unsupported, unavailable,
  partial, stale, and conflict diagnostics; stale writes are rejected; Race and
  Qualifying contracts remain backward-compatible.
- **Verification method:** API, concurrency, and regression tests.
- **Evidence location:** To be filled during implementation.

### API-002: Bounded read-only inspection

- **Statement:** LLM inspection may expose only bounded Practice report status,
  selected claim summaries, readiness, limitations, and package-relative paths;
  it may not mutate review or framing.
- **Rationale:** Inspection must not bypass human authority.
- **Acceptance criteria:** Contract payload size is bounded, unknown programme
  variables remain visible, and no review or editorial mutation operation is
  added.
- **Verification method:** Contract and negative mutation tests.
- **Evidence location:** To be filled during implementation.

## UI or UX impact

### UX-001: Practice Story workflow

- **Statement:** Story must present session context, official classification,
  relevant runs, matched long-run comparison, observed run trend,
  evidence, selection, framing, and readiness in Practice terminology.
- **Rationale:** Authors must understand what can safely be published.
- **Acceptance criteria:** Official and long-run sections are visibly distinct;
  eligibility and comparability are concise statuses; no instructional prose or
  speculative programme labels are added to the product UI.
- **Verification method:** Component and browser tests.
- **Evidence location:** To be filled during implementation.

### UX-002: Evidence and availability inspection

- **Statement:** Evidence must let analysts inspect run boundaries, included and
  excluded laps, fit basis, coverage, quality, comparability, conditions,
  limitations, and provenance.
- **Rationale:** Practice aggregates are credible only when their samples are
  inspectable.
- **Acceptance criteria:** Every published claim navigates to its result and lap
  evidence; unavailable, unknown, confounded, and provisional states are
  distinguishable without color alone.
- **Verification method:** Navigation, state, and accessibility tests.
- **Evidence location:** To be filled during implementation.

### UX-003: Readable Practice charts

- **Statement:** Practice Evidence charts must remain readable for a full field,
  while publication charts must be restricted to story-relevant drivers and
  expose sample and compatibility semantics without visual ranking of
  incompatible evidence.
- **Rationale:** Dense charts can imply comparisons the data does not support.
- **Acceptance criteria:** Driver and compound have distinct accessible
  encodings; incompatible rows are separated or labelled descriptive; excluded
  laps do not affect analytical axes; full-field Evidence overflow uses explicit
  scrolling, pagination, or additional chart instances without silently
  dropping rows; reader-facing evolution charts omit estimator method, residual
  MAD, fit quality, and detailed exclusion diagnostics.
- **Verification method:** Visual and responsive acceptance tests.
- **Evidence location:** To be filled during implementation.

### UX-004: Exact preview and local export

- **Statement:** Preview must show the exact current Practice article structure,
  copy, charts, captions, and limitations that export will write.
- **Rationale:** Editors must review the actual deliverable.
- **Acceptance criteria:** Preview indicates stale and blocked states; ready
  preview and exported Markdown are structurally equivalent; relocated assets
  resolve; export remains an explicit local action.
- **Verification method:** Parity, relocation, and browser tests.
- **Evidence location:** To be filled during implementation.

## Configuration impact

- Add versioned Practice provider, long-run eligibility, comparison, selection,
  phrase, chart, readiness, and export policy identifiers.
- Default thresholds are normative values in this spec and are not user-tunable
  in the initial implementation.
- Existing Race and Qualifying defaults and stored configuration retain their
  behavior.

## Error handling

- Unsupported session types return a typed scope diagnostic before analysis.
- Missing official classification blocks readiness but does not prevent lap and
  run evidence inspection.
- Missing or incomplete pit boundaries produce partial runs, never fabricated
  events.
- Five-to-seven representative laps produce a sustained-run, provisional,
  evidence-only result; fewer than eight cannot become a long-run claim.
- Missing, unreliable, or fewer than eight shared tyre ages produces explicit
  unknown comparability and no scalar comparison.
- Known compound, condition, or interruption mismatch produces confounded or
  incompatible comparison, not a scalar ranking.
- A stale selected result blocks preview-current and export-current states.
- Export failure is atomic and does not replace the last healthy package.

## Edge cases

- Session cancelled, shortened, or run with no representative timed laps.
- Driver with no time, one installation lap, repeated pit exits, or missing pit
  boundaries.
- Compound changes inside one apparent run or missing compound identity.
- Used tyres with non-zero starting age, missing tyre age, or tyre-age reset.
- Red flag, VSC, yellow, rain transition, or track-status boundary inside a run.
- Timing corrections that change official classification after lap data loads.
- Equal lap times, duplicate timing records, deleted laps, and missing sectors.
- Long runs at non-overlapping session times or with unequal sample counts.
- Negative observed slope, high residual dispersion, or low representative
  coverage.
- Wet and dry compounds in one session without a compatible comparison window.
- More than 20 eligible runs and more than four selected comparison traces.

## Acceptance criteria

SPEC-012 is satisfied when:

1. FP1, FP2, and FP3 single-session targets are supported and other scopes are
   explicitly rejected.
2. Official classification and neutral run chronology are typed and traceable.
3. Sustained-run and long-run eligibility, summaries, evolution, and comparison implement the
   exact versioned contracts in this spec.
4. Unknown fuel, engine mode, setup, tyre treatment, and programme intent are
   never inferred or corrected.
5. Official order, short-run evidence, and long-run evidence remain distinct.
6. Practice selection, framing, readiness, preview, and export extend the shared
   report authority without changing Race or Qualifying behavior.
7. Three purposeful chart families and chart-economy rules are verified.
8. Dry, interrupted, and wet or mixed acceptance packages pass the common
   editorial rubric or preserve an intentional evidence-based readiness block.
9. Repository governance, specification, drift, backend, frontend, security,
   accessibility, and package-integrity checks pass.
10. Nelson Jeanrenaud explicitly approves the spec before implementation.

## Verification matrix

| Requirement ID | Acceptance criterion | Verification method | Test / command / manual check | Evidence location | PR reference |
| -------------- | -------------------- | ------------------- | ----------------------------- | ----------------- | ------------ |
| REQ-001 | Only one FP1/FP2/FP3 target is accepted | Automated | Scope and dispatch tests | `tests/test_practice_report.py` | |
| REQ-002 | One authority governs Practice and existing sessions regress | Automated/inspection | Persistence and regression tests | `tests/test_analysis_workspace.py`; full regression suite | |
| REQ-003 | Sources and unknown programme variables remain explicit | Automated | Truth tables and phrase policy | `tests/test_practice_report.py`; acceptance evidence | |
| REQ-004 | Official classification is not reconstructed | Automated | Classification fixtures | `tests/test_practice_report.py`; `tests/test_fastf1_gateway.py` | |
| REQ-005 | Runs and exclusions are neutral and traceable | Automated | Boundary and sequence tests | `tests/test_practice_report.py` | |
| REQ-006 | Long-run summaries follow thresholds and arithmetic | Automated | Summary fixtures | `tests/test_practice_report.py` | |
| REQ-007 | Fits are versioned, basis-specific, and non-causal | Automated | Numerical and language fixtures | `tests/test_practice_report.py`; shared strategy tests | |
| REQ-008 | Only compatible windows expose scalar differences | Automated | Comparability truth table | `tests/test_practice_report.py`; acceptance evidence | |
| REQ-009 | Context results own independent identity and freshness | Automated | Freshness and source tests | `tests/test_practice_report.py` | |
| REQ-010 | Providers own assessment, identity, and deduplication | Automated | Registry tests | `tests/test_practice_report.py`; `tests/test_report_findings.py` | |
| REQ-011 | Lead selection follows category, quality, effect, and stable-ID order | Automated | Determinism and ranking truth-table tests | `tests/test_practice_report.py` | |
| REQ-012 | Article separates official and long-run evidence | Automated/manual | Golden Markdown and phrase review | `tests/test_practice_report.py`; acceptance evidence | |
| REQ-013 | Three charts preserve approved semantics | Automated/manual | Recipe and visual tests | `tests/test_practice_report.py`; acceptance evidence | |
| REQ-014 | Chart economy and framing are bounded and fresh | Automated | Selection and persistence tests | `tests/test_practice_report.py`; workspace tests | |
| REQ-015 | Readiness and export are exact, safe, and portable | Automated/manual | Readiness, parity, relocation tests | report/reader tests; acceptance evidence | |
| REQ-016 | Three real packages exercise material conditions | Automated/manual | End-to-end packages and rubric | `scripts/generate_spec012_acceptance.py`; `docs/reports/SPEC-012-acceptance-evidence.md` | |
| NFR-001 | Identical inputs produce stable output | Automated | Repeated-run comparison | `tests/test_practice_report.py`; acceptance fingerprints | |
| NFR-002 | Language avoids cause and prediction | Automated/manual | Phrase fixtures and review | `tests/test_practice_report.py`; acceptance evidence | |
| NFR-003 | Reports require no analytical reconstruction | Manual | Editorial rubric | `docs/reports/SPEC-012-acceptance-evidence.md` | |
| NFR-004 | Workflow is responsive and accessible | Automated/manual | Frontend and viewport checks | frontend build/typecheck; acceptance browser check | |
| SEC-001 | Markdown and assets remain contained | Automated | Injection and path tests | existing report/reader security tests | |
| SEC-002 | Publishing handoff remains local | Inspection | Dependency and API inspection | local package implementation; acceptance evidence | |
| DATA-001 | Practice schemas validate and version | Automated | Schema and compatibility tests | `tests/test_practice_report.py`; `tests/test_fastf1_gateway.py` | |
| DATA-002 | Plan rejects invalid placement and references | Automated | Round-trip and validation tests | `tests/test_practice_report.py`; report tests | |
| DATA-003 | Aggregates reconstruct from included lap evidence | Automated | Evidence reconstruction tests | `tests/test_practice_report.py`; package `results.json` | |
| API-001 | Workflow APIs are typed, atomic, and stale-safe | Automated | API and concurrency tests | workspace/server regression tests | |
| API-002 | Inspection is bounded and read-only | Automated | Contract tests | LLM contract tests; `src/f1_telemetry_charts/llm/contract.py` | |
| UX-001 | Story uses clear Practice terminology | Automated/manual | Component and browser checks | frontend typecheck/build; acceptance browser check | |
| UX-002 | Claims navigate to inspectable lap evidence | Automated/manual | Navigation and state tests | package sidecars; acceptance browser check | |
| UX-003 | Evidence handles the full field and publication charts stay focused | Manual | Evidence and exported chart review | acceptance packages and browser check | |
| UX-004 | Preview and export are equivalent | Automated/manual | Parity and browser tests | report/reader tests; acceptance browser check | |

## Test plan

### Unit tests

- Practice scope recognition and rejection of non-Practice targets.
- Official classification, ties, no-time entries, corrections, and absence.
- Pit-boundary reconstruction, compound changes, neutral run labels, and partial
  boundaries.
- Representative-lap exclusions and exact reason accounting.
- Five-to-seven-lap sustained-run status and eight-lap long-run/publication
  thresholds.
- Type-7 summaries, Theil-Sen slope, intercept, residual MAD, fit quality, and
  run-progress versus tyre-age basis separation.
- Same-compound overlap windows, paired shared-tyre-age differences, fewer than
  eight shared tyre ages, missing or reset tyre age, wet/dry changes,
  interruptions, unequal samples, and non-overlap.
- Independent conditions, interruption, and traffic fingerprints/freshness.
- Provider identity, assessment, disposition, finding ownership,
  deduplication, selection, placement, freshness, and readiness.
- Lead-selection truth table covering every category, evidence-quality order,
  finite and missing effect sizes, equal effects, and stable-ID ties.
- Phrase rejection for fuel, mode, setup, intent, degradation, and prediction.

### Integration and API tests

- Generate all Practice results and supported charts from fixed snapshots.
- Save, reload, refresh, review, preview, and export without identity loss.
- Reject stale writes and preserve human framing as review-required.
- Prove optional unavailable context does not block an otherwise sound package.
- Prove missing official classification or selected stale evidence does block.
- Verify reader claim IDs resolve to sidecar results and exact lap samples.
- Reopen and rerun existing Race and Qualifying analyses and publication tests.

### Frontend and visual tests

- Story, Evidence, Preview, and Export at desktop and 390x844.
- Keyboard navigation, focus, accessible names, non-color status, and chart alt
  text.
- Full-field Evidence run overview with compound changes, rain, and interruption;
  focused article overview containing only story-relevant drivers and runs.
- Pace summary with long-run, sustained-run, unavailable, unknown, and confounded
  rows.
- Evidence evolution fits with exclusions, basis, quality, and diagnostics;
  simplified reader charts with representative laps, trend line, and motorsport
  time formatting.
- Exact preview/export parity and explicit blocked-state presentation.

### Acceptance packages

- One dry Practice package with at least two same-compound long runs and at
  least eight paired shared-tyre-age samples if it publishes a scalar delta.
- One interrupted Practice package with a recorded stoppage and correct run/
  exclusion treatment.
- One wet or mixed Practice package with a comparison correctly rejected or
  qualified by condition evidence.
- Record session identity, source fingerprint, policy versions, package hash,
  validation commands, screenshots, and human verdict for each.
- Apply one rubric: correct official order, transparent sample selection,
  compatible comparison basis, non-causal language, no prediction, useful
  charts, no duplication, readable mobile output, and claim-to-lap traceability.

### Expected completion commands

- `python scripts/validate_governance.py`
- `python scripts/validate_specs.py`
- `python scripts/validate_drift.py`
- `python -m unittest discover -s tests -p "test_*.py"`
- Frontend typecheck and production build using the configured package manager.
- `git diff --check`

## Rollback plan

- Keep Practice providers, schemas, policies, recipes, and UI branches behind
  Practice dispatch so removal does not alter Race or Qualifying behavior.
- Add versioned fields and result types rather than reinterpret stored packages.
- If a Practice policy or schema is defective, mark dependent evidence and
  exports stale and require regeneration after correction.
- Roll back Practice registration and UI exposure together; do not leave
  readable but unreviewable Practice packages.

## Open questions

None. Exact fixture events may be chosen during implementation planning if they
satisfy REQ-016 and are recorded as acceptance evidence; fixture identity does
not change product behavior.

## Human decisions required

- [x] Approve SPEC-012 as written before implementation begins. Approval must
      confirm the single-session FP1/FP2/FP3 boundary, five-to-seven-lap
      sustained-run category, eight-lap long-run and trend-publication threshold,
      mandatory paired tyre-age comparison contract, focused publication charts,
      simplified article structure, and mandatory dry/interrupted/wet-or-mixed
      acceptance packages.

## Conflict check

- SPEC-009 remains authoritative for analytical-result ownership, assessment,
  findings, review, freshness, and evidence. SPEC-012 adds Practice providers;
  it does not create a second authority.
- SPEC-010 remains authoritative for the shared publication workflow and Race
  behavior. Its Practice non-goal limited its scope and is not contradicted by a
  separately approved extension.
- SPEC-011 remains authoritative for Qualifying semantics and proves the
  session-specific extension pattern. SPEC-012 must not generalize or reinterpret
  Qualifying behavior.
- SPEC-008 owns the shared representative-lap, summary, Theil-Sen, residual-MAD,
  and observed-pace-evolution mathematics. Practice reuses those methods while
  introducing Practice-specific run eligibility and comparison policy.
- No blocking conflict or supersession is identified. Shared components are
  declared in `depends_on`; Race and Qualifying regression is mandatory.

## Traceability table

| Requirement ID | Design / component | Implementation (file/function) | Test | Status |
| -------------- | ------------------ | ------------------------------ | ---- | ------ |
| REQ-001 through REQ-016 | Practice providers, publication policy, charts, workflow, export | `analysis/practice.py`, `analysis/findings.py`, `analysis/publication.py`, `analysis/report.py`, `analysis/workspace.py`, `recipes/practice.py` | `tests/test_practice_report.py`, full regression suite, three acceptance packages | Implemented; human acceptance pending |
| NFR-001 through NFR-004 | Determinism, language, editorial and responsive quality | Practice result fingerprints, policy v1, structured editorial and responsive Workbench | Practice tests, frontend gates, browser check | Implemented; human acceptance pending |
| SEC-001 through SEC-002 | Existing sanitisation, containment, local export | Shared report renderer, reader resolver, local API/export | Existing security/regression tests and package inspection | Implemented |
| DATA-001 through DATA-003 | Versioned results, plan, lap audit trail | Practice result schemas, publication plan, representative/excluded lap payloads | Practice and FastF1 tests; acceptance sidecars | Implemented |
| API-001 through API-002 | Analysis workflow and bounded inspection | Workspace dispatch and bounded LLM contract | Workspace, server, and contract regression tests | Implemented |
| UX-001 through UX-004 | Story, Evidence, charts, Preview and Export | Workbench Practice branches, three recipes, exact reader renderer | Frontend gates, Practice tests, desktop/mobile browser check | Implemented; human acceptance pending |

## Implementation notes

- Implementation was authorised by Nelson Jeanrenaud on 2026-08-24 in the
  current Codex task after approving the spec as written.
- AMEND-001 was approved during implementation and removes any additional
  statistical Practice-lap outlier deletion. SPEC-008 was not modified.
- Practice implementation, automated tests, frontend build, real dry/
  interrupted/wet packages, and desktop/mobile browser verification completed
  on 2026-08-24. Evidence is recorded in
  `docs/reports/SPEC-012-acceptance-evidence.md`.
- The configured FastF1 source returned no current official Practice
  classification for the three fixtures. Each package therefore remains
  intentionally not ready; recorded lap timing was not used as a substitute.
- Human editorial acceptance remains pending, so lifecycle status stays In
  Implementation.

## Spec amendments

### AMEND-001: Apply explicit exclusions only

- **Date:** 2026-08-24
- **Approved by:** Nelson Jeanrenaud in the current Codex task.
- **Change:** Representative Practice laps apply only SPEC-008's explicit
  exclusions. No statistical outlier-removal rule is applied, and every lap
  without an explicit exclusion reason remains in the analytical sample.
- **Reason:** Legitimately slow Practice laps can reflect preparation, traffic,
  management, conditions, mistakes, or programme differences. Median, trimmed
  mean, and Theil-Sen already provide robust summaries without silently deleting
  real session behaviour.
- **Compatibility:** SPEC-008 is unchanged. Existing explicit exclusion reasons,
  sample auditability, and robust summary methods remain authoritative.

## Review checklist

- [x] spec_id is unique and follows the SPEC-XXX format.
- [x] Every requirement has an ID, statement, rationale, acceptance criteria,
      verification method, and evidence location.
- [x] Non-goals are listed.
- [x] Open questions are resolved or explicitly deferred.
- [x] Verification matrix covers every requirement.
- [x] Conflict check completed.
- [x] Human approval recorded before status set to Approved (Nelson Jeanrenaud,
      2026-08-24, current Codex task: "I approve and authorize spec 12 you can
      implement it").
