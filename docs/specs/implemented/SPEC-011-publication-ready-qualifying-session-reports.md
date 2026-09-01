---
doc_type: spec
spec_id: SPEC-011
title: Publication-Ready Qualifying Session Reports
status: Implemented
owner: Nelson Jeanrenaud
related_issue:
related_prs: []
delivery_refs:
  - https://github.com/Nelson-Jnrnd/F1_Telemetry_Charts/commit/027d5b2
affected_components:
  - qualifying analytical result providers
  - qualifying chart templates
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
  - SPEC-009
  - SPEC-010
conflicts_with: []
last_verified_at: 2026-08-14
---

# SPEC-011: Publication-Ready Qualifying Session Reports

## Summary

This spec adds publication-ready reports for one standard Formula 1 Qualifying
session. It reuses the reviewed analytical-result and publication authority
from SPEC-009 and SPEC-010, but introduces qualifying-specific evidence,
selection, charts, article structure, and readiness. The report establishes
Q1/Q2/Q3 classification and elimination first, then explains valid-lap
progression, runs, pole and cutoff margins, and sector contributions. Track
evolution, traffic, and deleted laps appear only when the source supports them.
Missing secondary evidence is explicit and never guessed. This is a deliberate
Qualifying-only increment, not an all-session reporting framework.

## Context

SPEC-009 makes typed analytical results the authority for findings, review,
freshness, and evidence. SPEC-010 extends that authority with publication
selection, human framing, exact preview, readiness, and portable Race-report
export. SPEC-010 explicitly excludes Qualifying and does not define qualifying
chronology, comparisons, or language.

Qualifying is not a shorter Race report. Its useful analytical units are timed
segments, elimination boundaries, attempts, valid best-lap progression, and
same-segment comparisons. A credible report must also separate official
classification from lap-level timing, and observed temporal improvement from
an unsupported claim that the circuit alone caused the improvement.

## Problem statement

The application cannot currently turn Qualifying timing and telemetry into a
selective, traceable article. A user must manually reconstruct segment order,
eliminations, attempts, margins, and sector deltas, while deleted laps, traffic,
interruptions, and changing conditions invite unsupported explanations. A
generic session abstraction would hide these qualifying-specific semantics and
create unnecessary complexity before a second session type proves common needs.

## Goals

- Publish the official Q1/Q2/Q3 outcome and elimination chronology accurately.
- Show valid best-lap progression and pit-delimited run or attempt sequence.
- Compare the Q3 pole margin and Q1/Q2 advancement cutoffs on the correct basis.
- Attribute selected same-lap deltas to recorded sector-time differences.
- Add track-evolution, traffic, and deleted-lap context only when supported.
- Preserve explicit partial, unavailable, and unsupported states.
- Produce a concise qualifying article with purposeful charts and readiness.
- Validate dry, interrupted, and wet Qualifying packages.

## Non-goals

- Practice long-run, fuel-load, degradation, or race-pace analysis.
- Sprint, Sprint Qualifying/Shootout, Race, or multi-session reporting.
- Full-weekend synthesis or comparison with practice and race sessions.
- A generic all-session spine, article template, or compatibility framework.
- Theoretical-best laps assembled from sectors recorded on different laps.
- Lap-time correction for track evolution, traffic, fuel, tyres, or weather.
- Causal claims about setup, driver errors, tyre preparation, strategy intent,
  or lost time without supporting telemetry and an approved analytical method.
- Automatic counterfactual claims that a deleted lap would have advanced,
  eliminated, or secured pole.
- Live reporting, external editorial sources, CMS publication, or autonomous
  ghostwriting.

## Users or actors

- A motorsport analyst reviewing timing, telemetry, and evidence quality.
- A publication author selecting the qualifying story and supplying framing.
- A motorsport editor accepting the final draft.
- The local Analysis Workbench, report authority, and package exporter.
- Optional read-only LLM consumers of bounded report summaries.

## Authoritative concepts

### Qualifying evidence hierarchy

Official evidence is represented as three distinct concepts:

- `official_segment_order`: the authoritative order and times within Q1, Q2,
  or Q3;
- `official_advancement_outcome`: the authoritative decision on who advanced
  or was eliminated from Q1 and Q2; and
- `official_session_classification`: the authoritative final Qualifying result.

Official advancement determines who advanced. Timing quantifies a cutoff only
when that outcome was genuinely time-based. Official segment and session data
own Q1/Q2/Q3 order, advancement, elimination, and pole. Lap timing owns lap
chronology, validity, deletion status, sectors, and pit-boundary reconstruction.
Positional timing or aligned telemetry owns traffic proximity. Track-status and
weather records independently own interruption and condition context. A lower
source may not silently replace a higher source; disagreements and missing
fields produce explicit degraded or unavailable states.

### Measurement categories

- **Measured:** source-recorded classification, segment times, lap and sector
  times, deletion flags or reasons, pit boundaries, track status, weather, and
  positional proximity.
- **Derived:** best-lap progression, run grouping, signed margins, sector
  contributions, coverage, and field-level temporal summaries calculated from
  measured inputs.
- **Descriptive:** bounded wording that reports an observed pattern or context
  without attributing cause.
- **Estimated:** model-dependent values. SPEC-011 does not select estimated
  qualifying claims by default.

Measurement category is not an evidence-strength ranking. Availability,
coverage, comparability, quality, confounding, and editorial relevance remain
independent.

### Valid lap

A valid lap for progression or comparison is a timed lap assigned to the
correct qualifying segment that the authoritative source does not mark deleted
or invalid. In-laps, out-laps, missing lap times, and laps outside the segment
are excluded. If validity or segment assignment cannot be established, the lap
is not promoted into a valid-best claim and the coverage limitation is explicit.

### Attempt and run

A timed-lap record is one source-recorded completed lap with a lap time. An
attempt is a valid timed-lap record eligible to update best-lap progression;
its only derived role is `best_update` or `valid_no_update`. Deleted, invalid,
out-lap, in-lap, and untimed records remain contextual. These labels do not
imply push intent, tyre preparation, energy deployment, cooldown, or abortion.
A run is the pit-out to pit-in sequence containing zero or more timed laps and
attempts. One run may contain multiple attempts separated by contextual laps.
Publication wording prioritises attempt chronology and uses `Run N / Attempt N`
only where pit boundaries support the run. A fallback reconstructed from
incomplete boundaries must be labelled partial and must not invent exact pit
events.

### Comparable sector contribution

Sector contribution compares complete recorded sectors from two selected valid
laps in the same qualifying segment. The signed sector differences must
reconcile to the recorded lap-time difference within 0.003 seconds. Version 1
marks two laps comparable only when both are valid, all compared sectors are
present, neither crosses a red-flag or other invalidating track-status boundary,
and their reliably recorded wet/dry compound class matches. If compound class
or track-status evidence is missing, condition comparability is `unknown`, not
automatically `confounded`; the result may remain inspectable but is excluded
from automatic publication. The method does not combine each driver's best
sectors or correct for temperature, rainfall rate, traffic, or any other factor.

### Observed temporal evolution

Track-evolution context is a field-level temporal pattern in valid lap times,
not a track-only correction or causal estimate. Driver mix, tyre state, fuel,
traffic, weather, interruptions, and execution remain possible contributors.
The report may say that the observed valid-lap sample became quicker or slower;
it may not state that the track produced a quantified gain.

### Qualifying publication policy version 2

Default story ranking and reportability are deterministic:

1. Pole and the official Q3 outcome are always the primary story.
2. A Q1 or Q2 cutoff margin becomes a canonical claim only when the time-based
   margin is at most 0.100 seconds. An official tie or non-time-based advancement
   may be reported as an outcome, but not as a fabricated margin.
3. Segment progression becomes a canonical claim when one driver changes at
   least three official positions between consecutive segments among drivers
   present in both.
4. A pole-versus-P2 sector comparison is eligible only when REQ-007 returns
   `comparable`; an `unknown` or `confounded` comparison is evidence-only.
5. Material wet-condition change or a session suspension is promoted into the
   main session story and ordered ahead of generic progression. Pole remains an
   official outcome, but it need not be the sole analytical headline when
   conditions or interruptions materially define how the outcome was produced.
6. Field-wide early-versus-late medians remain supporting context only. Primary
   temporal interpretation uses same-driver running bests and the running
   competitive benchmark on session time.
7. Traffic is excluded from analyst and reader output unless aligned telemetry
   ties proximity to one identified valid attempt and supports an explicit
   compromised-lap assessment. Raw proximity counts remain audit evidence only.
8. A contradiction between official segment results and lap-level deletion or
   validity flags is a blocking deletion-integrity conflict. It cannot be
   rendered as "no deleted laps" or pass publication readiness.

A computable metric that does not meet these rules remains inspectable evidence;
it is not automatically a publishable claim.

## Functional requirements

### REQ-001: Enforce Qualifying-only scope

- **Statement:** SPEC-011 must accept only a standard Formula 1 Qualifying
  target with Q1, Q2, and Q3 semantics and must not introduce a generic session
  abstraction.
- **Rationale:** Sprint, practice, and race sessions have materially different
  analytical units and editorial questions.
- **Acceptance criteria:** Standard Qualifying is accepted; Race, Practice,
  Sprint, and Sprint Qualifying/Shootout targets return an explicit
  unsupported-scope diagnostic; public types and UI copy use qualifying terms.
- **Verification method:** Scope-validation, schema, and UI inspection tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-002: Reuse the existing report authority

- **Statement:** Qualifying results, findings, review, publication selection,
  framing, freshness, preview, and export must extend the SPEC-009/SPEC-010
  authority; no parallel qualifying narrative store may be created.
- **Rationale:** Review and traceability must remain coherent.
- **Acceptance criteria:** One persisted authority produces analyst and reader
  renderings; qualifying findings reference typed results; existing Race
  behavior remains unchanged.
- **Verification method:** Architecture inspection, persistence tests, and Race
  regression tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-003: Preserve source authority and unavailable states

- **Statement:** Every qualifying result must record source, measurement
  category, segment, coverage, quality, limitations, and exact availability;
  lower-authority evidence must not silently fill missing official facts.
- **Rationale:** Plausible reconstructed timing is not official classification.
- **Acceptance criteria:** Complete, partial, unavailable, unsupported, and
  source-conflict fixtures produce deterministic typed states; missing traffic,
  sector, deletion-reason, or weather evidence remains explicit and does not
  block unrelated analysis.
- **Verification method:** Provider truth tables and degraded-fixture tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-004: Materialise segment classification and elimination chronology

- **Statement:** The analysis must materialise one versioned
  `qualifying_segment_classification` result with distinct
  `official_segment_order`, `official_advancement_outcome`, and
  `official_session_classification` structures, plus official best times and
  statuses.
- **Rationale:** The article needs an official spine before interpretation.
- **Acceptance criteria:** Q1 and Q2 identify the official advancing and
  eliminated groups; Q3 identifies pole and the classified order; ties,
  no-time entries, penalties, withdrawals, and incomplete segments retain the
  applicable official concepts and explicit status; none is reconstructed by
  sorting lap timing; lap timing never overrides an official outcome.
- **Verification method:** Provider tests using complete and exceptional
  classification fixtures.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-005: Materialise valid best-lap and run progression

- **Statement:** The analysis must materialise one versioned
  `qualifying_attempt_progression` result containing chronological timed-lap
  records, valid attempts classified only as `best_update` or
  `valid_no_update`, supported pit-delimited runs,
  validity, and each driver's valid best-lap progression by segment.
- **Rationale:** Qualifying performance is understood through attempts and
  improvement, not only final times.
- **Acceptance criteria:** Only valid laps update the best; deleted and invalid
  laps remain visible as context but cannot become the recorded best; one run
  may contain multiple attempts; out-laps and non-attempt timed laps retain
  neutral contextual labels; no record is labelled as tyre preparation,
  charging, push, cooldown, or abort without an authoritative source; run and
  attempt numbering is stable; incomplete pit boundaries produce partial run
  coverage rather than invented events; every timed record includes session
  time and compound state when available so progression can use chronology
  rather than cross-driver attempt ordinal.
- **Verification method:** Sequence, validity, and boundary tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-006: Calculate pole and advancement margins correctly

- **Statement:** The analysis must materialise one versioned
  `qualifying_margin_comparison` result for the Q3 pole-to-P2 margin and the Q1
  and Q2 advancement boundaries.
- **Rationale:** Pole and elimination margins are the clearest qualifying
  comparisons when computed within the correct segment.
- **Acceptance criteria:** Pole margin uses official Q3 best times; each cutoff
  comparison first uses `official_advancement_outcome` to identify the slowest
  official advancer and fastest official eliminated driver, then reports a
  signed within-segment difference only when that boundary was genuinely
  time-based; ties and non-time-based outcomes make the margin unavailable
  while preserving the official outcome; cross-segment times are never used.
- **Verification method:** Margin, tie, penalty, and missing-time tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-007: Calculate reconciled sector contributions

- **Statement:** The analysis must materialise one versioned
  `qualifying_sector_contribution` result for an explicitly selected pair of
  comparable valid laps, defaulting to the pole lap and official Q3 P2 best.
- **Rationale:** Sector deltas show where the recorded lap-time difference
  accumulated without pretending to explain why.
- **Acceptance criteria:** The result records both lap identities and segment;
  both laps are valid and in the same segment; every compared sector is present;
  signed sector deltas reconcile to the lap delta within 0.003 seconds; neither
  lap crosses an invalidating track-status boundary; reliably available wet/dry
  compound class matches; missing condition evidence produces `unknown`, while
  a known mismatch produces `confounded`; only `comparable` is automatically
  publishable; theoretical-best sectors are prohibited. When material sector
  direction reverses, synthesis states each driver's gain and recovery by
  sector instead of collapsing opposing sectors into a remainder.
- **Verification method:** Numerical reconciliation and comparability tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-008: Materialise independently owned qualifying context

- **Statement:** The analysis must materialise five separate versioned results:
  `qualifying_temporal_evolution`, `qualifying_interruptions`,
  `qualifying_traffic_context`, `qualifying_deleted_laps`, and
  `qualifying_conditions`. They may share utilities but must not share semantic
  result identity or one aggregate fingerprint.
- **Rationale:** Context matters, but unsupported context is more misleading
  than omission.
- **Acceptance criteria:** Each result has independent provenance, fingerprint,
  freshness, availability, coverage, assessment, and review; a weather change
  cannot stale deleted-lap evidence and missing telemetry cannot degrade the
  interruption result; traffic requires aligned positional timing or telemetry
  and cannot be inferred from a slow sector; deleted laps retain raw time and
  reason when recorded but do not alter classification; observed evolution uses
  a named versioned policy, minimum coverage, and explicit confounders;
  interruptions use recorded track status or control timing; official segment
  results are reconciled against lap-level deletion and validity signals, and
  any unexplained faster or unofficial-segment lap produces a blocking
  deletion-integrity conflict; traffic is reader-visible only when linked to a
  specific valid attempt with a supported compromised-lap assessment.
- **Verification method:** Context-provider, coverage, and phrase-policy tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-009: Use result-provider ownership and deduplication

- **Statement:** All nine qualifying result types must register through the
  SPEC-009 provider contract and receive its assessment, disposition,
  fingerprint, deduplication, finding, evidence, and review behavior.
- **Rationale:** Qualifying cannot bypass the established analytical boundary.
- **Acceptance criteria:** Each unique result has one assessment; repeated chart
  support does not duplicate findings; unavailable or context-only results do
  not become publishable claims.
- **Verification method:** Registry, identity, disposition, and deduplication
  tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-010: Select a qualifying story deterministically

- **Statement:** A named versioned qualifying policy must propose a small,
  compatible set of canonical claims, summary references, and chart placements
  from current reviewed evidence.
- **Rationale:** A qualifying article needs editorial selection, not a timing
  dump.
- **Acceptance criteria:** The default prioritises official outcome and pole or
  a reportable cutoff, while material wet conditions and interruptions are
  promoted ahead of generic progression; comparable sector evidence states the
  supported motorsport conclusion rather than merely restating arithmetic;
  traffic remains audit-only unless tied to a specific compromised attempt;
  the version 2 thresholds in Authoritative concepts govern
  automatic reportability; unavailable, estimated, low-quality, unknown-
  comparability, or materially confounded claims are excluded by default; one
  claim has one detailed placement; a large calculable cutoff is not promoted
  merely because it exists.
- **Verification method:** Determinism, ranking, compatibility, and placement
  tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-011: Use a qualifying-specific article structure

- **Statement:** The publication plan must support, in order, Headline,
  Standfirst, At a Glance, optional Session Context, How Qualifying Unfolded,
  Pole and Cutoff Battles, optional Sector Comparison, Conclusion, and Methods
  and Evidence.
- **Rationale:** The structure follows qualifying chronology and decision
  boundaries rather than Race strategy.
- **Acceptance criteria:** Empty optional sections disappear; At a Glance uses
  the actual canonical finding text rather than category or placeholder labels
  and does not introduce new metrics; the report does not
  manufacture a pole battle, traffic story, deleted-lap controversy, or
  decisive sector. Absolute qualifying lap times render as `M:SS.mmm` in
  reader and analyst prose while typed evidence retains numeric seconds.
- **Verification method:** Plan-validation and Markdown structure tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-012: Provide three purposeful qualifying charts

- **Statement:** SPEC-011 must provide a qualifying progression chart, a
  pole-and-cutoff margin chart, and a sector-contribution chart backed by the
  typed results in this spec.
- **Rationale:** These views answer distinct practical questions without
  creating a dashboard inventory.
- **Acceptance criteria:** Progression separates Q1/Q2/Q3 and distinguishes
  valid, deleted, invalid, and unavailable attempts; the margin chart never
  shares one misleading scale across incomparable segment concepts and labels
  the compared boundary; sector contributions use a zero baseline and signed
  deltas that reconcile to the shown lap margin; condition, coverage, and
  interruption context is annotated only when supported; progression uses
  session time, shows running bests for relevant drivers and the running cutoff
  benchmark, labels compound state, and marks recorded red-flag periods. Long
  stoppages are visibly compressed while tick labels retain session time;
  deleted laps and integrity conflicts have distinct labels and markers.
- **Verification method:** Recipe, renderer, metadata, and visual acceptance
  tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-013: Enforce chart economy

- **Statement:** Automatic publication selection must choose two or three
  charts when that many are useful and may choose zero or one when evidence is
  sparse; it must not pad the article or duplicate the same comparison.
- **Rationale:** Classification is often clearer as prose or a compact table,
  and not every session supports every chart.
- **Acceptance criteria:** Every selected chart has purpose, placement,
  caption, alt text, and result references; redundant selections are rejected;
  more than three charts requires explicit editorial inclusion. The
  pole-and-cutoff margin recipe remains available for inspection but is not
  selected automatically because labelled values communicate the comparison
  more directly.
- **Verification method:** Selection, validation, and browser tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-014: Preserve structured human framing

- **Statement:** Authors must be able to provide qualifying-specific headline,
  standfirst, section ledes, captions, alt text, and conclusion through the
  existing structured editorial fields.
- **Rationale:** Publication framing is human work, but it must stay bounded and
  traceable.
- **Acceptance criteria:** Human fields cannot masquerade as analytical
  findings, survive refresh, become review-required when dependencies change,
  and cannot assert unsupported causes or counterfactual outcomes in a ready
  package. When fixed acceptance packages use official reporting to add crash
  attribution or session sequence not present in the timing feed, those URLs
  are recorded as editorial sources in the package evidence. The source-backed
  edited canonical claim is shared by reader and analyst reports, and an
  equivalent section lede is not rendered as duplicate prose.
- **Verification method:** Persistence, freshness, and phrase-review tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-015: Validate qualifying publication readiness

- **Statement:** The existing publication freshness graph and workflow states
  must be extended with qualifying prerequisites and one explicit
  `Publication draft ready` decision.
- **Rationale:** Missing optional evidence should not block a sound report, but
  missing official outcome or stale selected evidence must.
- **Acceptance criteria:** Readiness requires current official classification,
  segment order and advancement outcomes, reviewed included claims, complete
  required framing, valid selected charts, exact current preview, package
  integrity, no duplicate placement, no unsupported language, and no
  deletion-integrity conflict between official results and lap timing;
  unavailable
  optional sector, traffic, deletion-reason, evolution, or weather evidence is
  visible to the analyst but does not block readiness when no published claim
  depends on it.
- **Verification method:** Readiness and freshness transition matrices.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-016: Render and export a clean qualifying package

- **Statement:** The publication renderer and exporter must produce clean
  portable Markdown, article metadata, web-ready selected chart assets, a
  machine-readable evidence sidecar, and a health/readiness manifest.
- **Rationale:** The output must be usable without the Analysis workspace.
- **Acceptance criteria:** Reader output omits internal implementation detail
  and repetitive confidence scaffolding; each published claim retains an
  explicit evidence ID; package-scoped asset paths resolve after relocation;
  analyst-only unavailable states remain in the sidecar; preview and export are
  structurally equivalent. Ready exports and blocked QA packages expose
  editorial source URLs, publication policy ID/version, and export contract
  version consistently; ready exports include `publication-plan.json` and the
  manifest points to it.
- **Verification method:** Golden Markdown, leakage, relocation, parity, and
  integrity tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### REQ-017: Produce three qualifying acceptance packages

- **Statement:** Implementation acceptance must produce and preserve one dry,
  one materially interrupted, and one wet Qualifying publication package from
  distinct real sessions through the application workflow.
- **Rationale:** Dry-only success does not validate interruptions, sparse runs,
  or condition-sensitive comparisons.
- **Acceptance criteria:** The dry fixture completes Q1/Q2/Q3; the interrupted
  fixture contains a recorded suspension and restart; the wet fixture contains
  recorded wet or intermediate running and material condition variation, and
  demonstrates at least one sector or cross-lap comparison correctly rejected
  or qualified because deterministic comparability is not met. Each package is
  healthy, current, source-identified, human-reviewed against the same rubric,
  and demonstrates at least one honest unavailable or excluded optional context
  state where the source lacks support.
- **Verification method:** End-to-end generation, package inspection, and
  recorded human editorial acceptance.
- **Evidence location:** See requirement traceability and closeout evidence.

## Non-functional requirements

### NFR-001: Deterministic and reproducible output

- **Statement:** Qualifying results, assessments, findings, chart data,
  selection, readiness, and rendering must be deterministic for identical
  source snapshots and policy versions.
- **Rationale:** Review and freshness require stable identity.
- **Acceptance criteria:** Repeated runs preserve fingerprints, ordering,
  calculations, selection, and Markdown apart from explicit timestamps.
- **Verification method:** Repeated-run comparison tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### NFR-002: Analytical language safety

- **Statement:** Generated and readiness-approved copy must distinguish what
  was measured, derived, described, estimated, unavailable, and confounded and
  must not convert correlation or chronology into causality.
- **Rationale:** Qualifying timing commonly supports description but not an
  explanation of why time was gained or lost.
- **Acceptance criteria:** Phrase-policy tests reject unsupported setup, error,
  tyre-preparation, traffic-loss, track-gain, strategy-intent, and
  counterfactual-advancement claims.
- **Verification method:** Positive and negative phrase fixtures plus human
  review.
- **Evidence location:** See requirement traceability and closeout evidence.

### NFR-003: Publication quality

- **Statement:** A ready report must let a competent motorsport editor improve
  voice and emphasis without reconstructing the qualifying order, correcting
  comparison bases, removing duplicated evidence, or restructuring the article.
- **Rationale:** This is the practical definition of publication-ready.
- **Acceptance criteria:** Dry, interrupted, and wet packages pass one recorded
  rubric for analytical correctness, readability, utility, traceability, and
  editorial economy.
- **Verification method:** Three-package human acceptance.
- **Evidence location:** See requirement traceability and closeout evidence.

### NFR-004: Responsive and accessible review

- **Statement:** Qualifying Story, Evidence, Preview, and Export must remain
  operable at desktop and 390x844 mobile viewports with keyboard navigation and
  accessible chart descriptions.
- **Rationale:** Dense timing information must remain reviewable.
- **Acceptance criteria:** No unexpected page overflow; segment, validity, and
  availability are not communicated by colour alone; controls and tables have
  accessible names and focus behavior.
- **Verification method:** Browser, keyboard, and viewport checks.
- **Evidence location:** See requirement traceability and closeout evidence.

## Security and privacy considerations

### SEC-001: Safe Markdown and package containment

- **Statement:** Editorial text, Markdown, metadata, alt text, and asset paths
  must be escaped or sanitized and contained within the export package.
- **Rationale:** Human content and source strings are untrusted inputs.
- **Acceptance criteria:** Injection and path traversal are rejected; exported
  files cannot resolve outside the package.
- **Verification method:** Injection and containment tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### SEC-002: Local-only publishing handoff

- **Statement:** SPEC-011 must not transmit reports or evidence to an external
  publishing service.
- **Rationale:** CMS integration and external transfer are out of scope.
- **Acceptance criteria:** Copy and download remain local; no publishing
  credentials, network destination, or upload endpoint is added.
- **Verification method:** API and dependency inspection.
- **Evidence location:** See requirement traceability and closeout evidence.

## Data model impact

### DATA-001: Versioned qualifying result schemas

- **Statement:** The nine qualifying result types must use versioned typed
  payloads with stable identity inputs, subject laps or drivers, segment,
  source authority, measurement category, coverage, quality, comparability,
  limitations, and component availability.
- **Rationale:** Qualifying semantics must remain inspectable and migratable.
- **Acceptance criteria:** Complete and degraded payloads serialize, validate,
  fingerprint, and either migrate or fail explicitly by version.
- **Verification method:** Schema, round-trip, and compatibility tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### DATA-002: Qualifying publication plan

- **Statement:** The publication plan must represent the qualifying structure,
  canonical claim placements, summary references, chart purposes, structured
  human fields, evidence dependencies, and exclusion reasons.
- **Rationale:** Editorial selection must not duplicate analytical facts.
- **Acceptance criteria:** Duplicate placements, dangling IDs, unsupported
  sections, and missing chart fields are rejected.
- **Verification method:** Model and round-trip tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### DATA-003: Acceptance and package metadata

- **Statement:** Analysis and export metadata must version qualifying
  readiness, source session identity, policy versions, rendered paths, evidence
  paths, and acceptance-fixture category.
- **Rationale:** Review evidence must be reproducible and portable.
- **Acceptance criteria:** Reload and relocation preserve identity and health;
  incompatible versions and stale artifacts are explicit.
- **Verification method:** Persistence, relocation, and compatibility tests.
- **Evidence location:** See requirement traceability and closeout evidence.

## API impact

### API-001: Qualifying analysis and publication workflow

- **Statement:** Typed APIs must support qualifying result generation, chart
  generation, proposal refresh, plan and editorial mutation, readiness
  inspection, exact preview, and local export through the existing workflow.
- **Rationale:** The UI must not derive analytical facts or readiness.
- **Acceptance criteria:** Requests validate Qualifying scope and evidence
  fingerprints; stale writes are rejected; failures are atomic; Race API
  behavior is unchanged.
- **Verification method:** API validation, concurrency, and regression tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### API-002: Bounded read-only inspection

- **Statement:** Any LLM-facing qualifying contract must expose bounded result,
  availability, claim, review, and readiness summaries without granting silent
  authority to change facts or human text.
- **Rationale:** Assistance must remain evidence-bound.
- **Acceptance criteria:** Responses preserve measurement category and
  unavailable states, are size-bounded, and reject fact mutation fields.
- **Verification method:** Contract and boundary tests.
- **Evidence location:** See requirement traceability and closeout evidence.

## UI or UX impact

### UX-001: Qualifying Story workflow

- **Statement:** Story must show the official outcome, three proposed main
  points, qualifying sections, selected claims, chart placement, exclusions,
  and missing framing using qualifying terminology.
- **Rationale:** Authors should understand the report without reading models.
- **Acceptance criteria:** Q1/Q2/Q3, pole, cutoff, attempt, and sector labels are
  unambiguous; no Race-specific labels appear; each missing item has one next
  action.
- **Verification method:** Component, browser, and copy tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### UX-002: Evidence and availability inspection

- **Statement:** Evidence must expose official versus lap-level sources,
  the three distinct official concepts, validity, attempt policy, run
  boundaries, comparison basis, measurement category, coverage, confounders,
  and independently owned unavailable states.
- **Rationale:** Reviewers must be able to challenge a qualifying claim quickly.
- **Acceptance criteria:** Every published claim navigates to its result and
  source evidence; unavailable context is distinct from an error or editorial
  exclusion; deleted laps cannot be mistaken for valid classification laps.
- **Verification method:** Navigation, state, and accessibility tests.
- **Evidence location:** See requirement traceability and closeout evidence.

### UX-003: Readable qualifying charts

- **Statement:** Charts must remain legible with a full field and clearly
  distinguish segment, driver, validity, threshold, and selected comparison.
- **Rationale:** Qualifying plots become unreadable quickly when every event is
  given equal emphasis.
- **Acceptance criteria:** Default views emphasize the selected story, use
  direct labels where practical, avoid 20-driver legends, provide compact
  detail on demand, and remain legible at supported export sizes.
- **Verification method:** Desktop, mobile, and exported-image visual review.
- **Evidence location:** See requirement traceability and closeout evidence.

### UX-004: Exact preview and local export

- **Statement:** Preview must show the exact article structure, copy, tables,
  captions, alt text, and chart assets included by Export.
- **Rationale:** Editorial acceptance cannot rely on an approximation.
- **Acceptance criteria:** Preview/export parity passes; stale preview cannot be
  ready; package health and next action are visible.
- **Verification method:** Parity and browser workflow tests.
- **Evidence location:** See requirement traceability and closeout evidence.

## Configuration impact

No generic session configuration is introduced. Qualifying policy versions,
selected comparisons, chart placement, and editorial fields belong to the
Analysis-local authority. Traffic and temporal-evolution thresholds must be
named, versioned analytical policy rather than user-facing tuning knobs in the
initial delivery.

## Error handling

- Missing official session classification, required segment order, or required
  advancement outcome blocks publication readiness and does not fall back
  silently to lap order.
- Missing optional sector, traffic, weather, or deletion-reason evidence creates
  an explicit unavailable component and allows unrelated claims to proceed.
- Source conflicts retain both sources, identify the authoritative one, and
  require review when they affect a selected claim.
- Unsupported session types fail before qualifying results or charts are
  persisted.
- Numerical sector reconciliation failure makes the contribution unavailable.
- Stale evidence or framing blocks readiness and current export without deleting
  the last valid package.
- Preview and export writes are atomic; prior valid artifacts remain inspectable.

## Edge cases

- A driver records no time in one or more segments.
- Equal official times are ordered by the authoritative classification.
- A driver is advanced or classified contrary to raw time order.
- A segment is shortened, suspended, restarted, or not completed.
- A driver sets multiple timed laps in one run.
- Pit-out or pit-in boundaries are missing.
- A deleted lap is quicker than the official valid best.
- A deleted-lap reason is absent.
- Pole is set before Q3 ends because later attempts are interrupted.
- Sector times are missing or do not reconcile within source precision.
- Wet and dry laps occur in the same segment.
- Traffic evidence covers only part of a lap or part of the field.
- Temporal samples change driver composition across buckets.
- Classification is complete but no useful qualifying chart is available.
- A legacy Race analysis is opened after qualifying support is installed.

## Acceptance criteria

SPEC-011 is ready for implementation only after human approval. Implementation
is complete only when:

1. Only standard Qualifying targets are accepted; no generic session framework
   or non-Qualifying report behavior is added.
2. The nine qualifying result types use SPEC-009 ownership and explicit source,
   measurement, coverage, quality, and availability semantics.
3. Q1/Q2/Q3 classification, elimination, progression, pole/cutoff margins, and
   sector contributions satisfy their analytical contracts.
4. Track evolution, traffic, deleted laps, weather, and interruptions appear
   only as supported, bounded context.
5. The three chart families pass numerical, metadata, accessibility, and visual
   review without clutter or misleading comparisons.
6. Qualifying selection and structure produce one canonical placement per claim
   and omit unsupported optional sections.
7. Readiness blocks missing official outcome, stale or unreviewed selected
   evidence, unsupported language, invalid charts, unhealthy export, and any
   deleted-lap integrity conflict.
8. Dry and wet real-session packages pass the recorded human acceptance rubric;
   the interrupted package must either pass with reconciled deletion evidence
   or demonstrate the expected blocking state without claiming readiness.
9. Existing Race report behavior and packages pass regression checks.

## Verification matrix

| Requirement ID | Acceptance criterion | Verification method | Test / command / manual check | Evidence location | PR reference |
| -------------- | -------------------- | ------------------- | ----------------------------- | ----------------- | ------------ |
| REQ-001 | Only standard Qualifying is accepted | Automated/inspection | Scope and schema tests | `tests/test_qualifying_report.py`; `analysis/qualifying.py` | |
| REQ-002 | One existing authority owns Qualifying publication | Automated/inspection | Architecture, persistence, Race regression | qualifying tests; full unittest discovery | |
| REQ-003 | Source and unavailable semantics are explicit | Automated | Provider truth tables | source-conflict/optional-context tests | |
| REQ-004 | Official segment order and outcomes are preserved | Automated | Classification fixtures | unit tests; 2021 Belgium no-time Q3 entry | |
| REQ-005 | Valid bests and runs progress correctly | Automated | Sequence and boundary tests | progression tests and chart evidence | |
| REQ-006 | Pole and cutoff margins use correct segments | Automated | Margin and exception tests | margin tests and three real packages | |
| REQ-007 | Sector deltas reconcile and remain comparable | Automated | Numerical tests | reconciliation/condition tests | |
| REQ-008 | Context is supported, bounded, and componentised | Automated/manual | Context and phrase fixtures | independent-fingerprint test; package sidecars | |
| REQ-009 | Providers deduplicate results and findings | Automated | Registry and identity tests | nine-assessment/deduplication tests | |
| REQ-010 | Story selection is deterministic and selective | Automated | Policy truth tables | selection/source-conflict tests | |
| REQ-011 | Qualifying structure is ordered and optional | Automated | Plan and Markdown tests | qualifying section test; exported articles | |
| REQ-012 | Three charts preserve analytical semantics | Automated/manual | Recipe, renderer, metadata, visual review | chart tests; acceptance package PNGs | |
| REQ-013 | Automatic chart selection is economical | Automated/manual | Selection and browser tests | proposal validation; browser Story review | |
| REQ-014 | Human framing stays bounded and fresh | Automated | Persistence and freshness tests | AnalysisService acceptance workflow | |
| REQ-015 | Every readiness prerequisite is enforced | Automated | Readiness transition matrix | readiness test; two ready manifests and one expected integrity block | |
| REQ-016 | Export is clean, traceable, portable, and exact | Automated/manual | Golden, leakage, relocation, parity tests | export packages; mobile Preview check | |
| REQ-017 | Dry, interrupted, and wet packages exercise acceptance | Automated/manual | Three end-to-end packages and rubric | Bahrain/Belgium accepted; Austria accepted as the expected integrity block | |
| NFR-001 | Identical inputs produce stable outputs | Automated | Repeated-run comparison | deterministic fingerprint test | |
| NFR-002 | Language does not overstate evidence | Automated/manual | Phrase policy and human review | readiness language policy; package copy | |
| NFR-003 | Reports need no analytical reconstruction | Manual | Three-package editorial review | accepted by Nelson Jeanrenaud on 2026-08-14 | |
| NFR-004 | Workflow is responsive and accessible | Automated/manual | Keyboard and viewport checks | typecheck/build; 390x844 browser check | |
| SEC-001 | Markdown and assets remain contained | Automated | Injection and path tests | existing package safety suite; preview asset route | |
| SEC-002 | Publishing handoff remains local | Inspection | API and dependency inspection | local AnalysisService exporter only | |
| DATA-001 | Qualifying schemas validate and version | Automated | Schema and compatibility tests | data/result models and serialization tests | |
| DATA-002 | Plan rejects invalid placement and references | Automated | Model round-trip tests | publication validation tests | |
| DATA-003 | Package identity and health survive relocation | Automated | Persistence and relocation tests | acceptance manifests and SHA-256 records | |
| API-001 | Workflow APIs are typed, stale-safe, and atomic | Automated | API and concurrency tests | full API/workspace regression suite | |
| API-002 | LLM inspection is bounded and read-only | Automated | Contract tests | `llm/contract.py::_report_summary`; contract suite | |
| UX-001 | Story uses clear qualifying terminology | Automated/manual | Component and browser checks | qualifying Story browser snapshot | |
| UX-002 | Published claims navigate to inspectable evidence | Automated/manual | Navigation and state tests | Evidence browser review with nine-result accounting | |
| UX-003 | Full-field charts remain readable | Manual | Exported chart visual review | dry/interrupted/wet PNG inspection | |
| UX-004 | Preview and export are equivalent | Automated/manual | Parity and browser tests | exported Markdown and responsive Preview inspection | |

## Test plan

### Unit tests

- Session-scope recognition and explicit rejection of all non-Qualifying types.
- Official classification, advancement, elimination, ties, penalties, no-time,
  incomplete-segment cases, and separation of segment order, advancement
  outcome, and final session classification.
- Segment assignment, validity filtering, deleted laps, neutral timed-lap
  records, best progression, multi-attempt runs, and incomplete pit boundaries.
- Pole and cutoff margins, including ties and official outcomes that differ
  from raw time order.
- Sector arithmetic with the 0.003-second tolerance, missing sectors, segment
  mismatch, invalidating track status, wet/dry class match and mismatch, and
  unknown condition comparability.
- Independent fingerprint and freshness tests for track status, weather,
  traffic proximity, deleted laps, temporal coverage, and unavailable context.
- Result identity, assessment, disposition, finding ownership, deduplication,
  selection, placement, freshness, and readiness.
- Chart model and metadata semantics for all valid and degraded states.
- Phrase-policy rejection of causal and counterfactual claims.

### Integration and API tests

- Generate qualifying evidence and all supported charts from a fixed snapshot.
- Save, reload, refresh, review, preview, and export without identity loss.
- Reject stale writes and preserve human framing as review-required.
- Prove optional unavailable context does not block an otherwise sound package.
- Prove missing official classification and selected stale evidence do block it.
- Verify reader claim IDs resolve to sidecar results and package assets.
- Reopen existing Race analyses and rerun SPEC-010 publication regressions.

### Frontend and visual tests

- Story, Evidence, Preview, and Export at desktop and 390x844.
- Keyboard navigation, focus, accessible names, non-colour validity states, and
  chart descriptions.
- Progression legibility with a full field, multiple runs, deletions, and an
  interruption.
- Margin-chart separation of pole and cutoff concepts.
- Sector zero baseline, sign convention, labels, and reconciliation copy.
- Exact preview/export parity and explicit unavailable-state presentation.

### Acceptance packages

- Produce one application-exported dry Qualifying package with complete
  Q1/Q2/Q3 chronology and sector comparison.
- Produce one interrupted Qualifying QA package with recorded suspensions,
  restarts, attempt-sequence impact, and a correct readiness failure when
  deletion integrity cannot be reconciled.
- Produce one application-exported wet Qualifying package with wet or
  intermediate running, condition-aware comparison handling, and at least one
  comparison correctly rejected or qualified by the deterministic contract.
- Record session identity, source snapshot fingerprint, policy versions,
  package hash, validation commands, screenshots, and human verdict for each.
- Apply one rubric: correct official story, sound comparison bases, honest
  availability, non-causal wording, useful charts, no duplication, readable
  mobile output, claim-to-evidence traceability, and no required structural
  rewrite.

### Expected completion commands

- `python scripts/validate_governance.py`
- `python scripts/validate_specs.py`
- `python scripts/validate_drift.py`
- `python -m unittest discover -s tests -p "test_*.py"`
- Frontend typecheck and production build using the repository's configured
  package manager.
- `git diff --check`

## Rollback plan

- Keep qualifying providers, schemas, policies, recipes, and UI branches behind
  Qualifying dispatch so they can be removed without changing Race behavior.
- Preserve existing Analysis and package schema readers; add versioned fields
  rather than reinterpreting stored Race data.
- If a new qualifying schema or policy is defective, mark affected evidence and
  exports stale and require regeneration after correction.
- Roll back qualifying registration and UI exposure together; do not leave
  readable but unreviewable qualifying packages.

## Open questions

None. Exact fixture events may be selected during implementation planning if
they satisfy REQ-017 and are recorded as acceptance evidence; fixture identity
does not change product behavior.

## Human decisions required

- [x] Approve SPEC-011 as written before implementation begins. Approval must
      confirm the Qualifying-only boundary, evidence hierarchy, three chart
      families, qualifying article structure, and mandatory dry/interrupted/wet
      acceptance packages.

## Conflict check

- SPEC-009 remains authoritative for analytical-result ownership, assessment,
  findings, review, freshness, and evidence. SPEC-011 extends it with new
  qualifying result providers; it does not create a second authority.
- SPEC-010 remains authoritative for the shared publication workflow and Race
  behavior. Its Qualifying non-goal limited SPEC-010 scope; it does not prohibit
  this separately approved extension. SPEC-011 must not weaken or reinterpret
  SPEC-010 Race requirements.
- SPEC-006 validity and explicit unavailable-state semantics apply where shared.
  SPEC-011 narrows valid qualifying laps further by requiring correct segment
  assignment and authoritative non-deletion.
- No blocking conflict was found. The derived spec index must remain a summary
  of this document.

## Traceability table

| Requirement ID | Design / component | Implementation (file/function) | Test | Status |
| -------------- | ------------------ | ------------------------------ | ---- | ------ |
| REQ-001 | Qualifying dispatch | `analysis/qualifying.py::is_standard_qualifying`; workspace dispatch | `test_scope_and_nine_independent_results` | Implemented |
| REQ-002 | Existing report authority | `analysis/findings.py::build_report_content`; `analysis/workspace.py` | qualifying authority tests; full Race regression suite | Implemented |
| REQ-003 | Source/availability contract | qualifying result records and `QualifyingSegmentClassification` | source-conflict and optional-context tests | Implemented |
| REQ-004 | Segment classification provider | `analysis/qualifying.py::_classification_result`; FastF1 official result mapping | classification, no-time, and real wet-session evidence | Implemented |
| REQ-005 | Attempt progression provider | `analysis/qualifying.py::_progression_result` | session-time sequence/deletion tests; full-field visual review | Implemented |
| REQ-006 | Margin provider | `analysis/qualifying.py::_margin_result` | margin tests; Belgium no-time-advancer browser regression | Implemented |
| REQ-007 | Sector contribution provider | `analysis/qualifying.py::_sector_result` | reconciliation, condition-comparability, and conclusion tests | Implemented |
| REQ-008 | Five independent context providers | context result functions and deletion-integrity reconciliation in `analysis/qualifying.py` | fingerprint/context/integrity tests; three real packages | Implemented |
| REQ-009 | Provider registry | `analysis/findings.py::_qualifying_provider` | nine-assessment and chart-reference deduplication tests | Implemented |
| REQ-010 | Qualifying selection policy v4 | `analysis/publication.py::_propose_qualifying_publication_plan`; qualifying context synthesis | deterministic plan, context-dominance, source-conflict, finding-led summary, and reader formatting tests | Implemented |
| REQ-011 | Qualifying article plan | qualifying report/publication section orders | plan and exported Markdown inspection | Implemented |
| REQ-012 | Three chart recipes/renderers | `recipes/qualifying.py`; Matplotlib renderer | chart contract tests; dry/interrupted/wet PNG review | Implemented |
| REQ-013 | Chart selection validation | qualifying publication proposal/validation | maximum-three and unique-primary-result tests | Implemented |
| REQ-014 | Structured editorial fields | existing `PublicationEditorial`; qualifying Story fields | persistence/readiness application workflow | Implemented |
| REQ-015 | Qualifying readiness | `analysis/publication.py::_evaluate_qualifying_readiness` | readiness tests; Austria deleted-lap integrity block | Implemented |
| REQ-016 | Reader renderer/exporter | `analysis/report.py`; `preview/reader.py`; `DraftPreview` | relocation/export, image path, and mobile preview checks | Implemented |
| REQ-017 | Acceptance workflow | `scripts/generate_spec011_acceptance.py` | Bahrain/Belgium accepted; Austria expected-blocked QA package accepted as validation evidence | Implemented |

## Implementation notes

- Do not start implementation until this spec is explicitly approved and moved
  to `docs/specs/approved/`.
- Prefer qualifying-specific providers and policies behind existing extension
  points. Do not refactor Race and Qualifying into generic base classes unless a
  later approved spec demonstrates a concrete shared requirement.
- Record all analytical thresholds, sign conventions, precision tolerances,
  and minimum coverage in versioned provider policy and tests.
- Record fixture selection and implementation sequencing in the implementation
  plan, not as new requirements outside this spec.

Implementation plan approved on 2026-08-13:

1. Extend the normalized source model with official Q1/Q2/Q3 records, segment
   assignment, and deletion reasons without changing Race semantics.
2. Add nine qualifying-specific analytical providers behind the existing
   result, assessment, finding, review, and freshness authority.
3. Add the versioned qualifying publication policy, article structure,
   readiness rules, reader renderer, and portable export support.
4. Add the three qualifying chart recipes and qualifying-specific Story fields.
5. Validate with deterministic unit/integration tests and distinct dry,
   interrupted, and wet real-session acceptance packages.

Implementation status: Implemented. All automated checks pass, the three
real-session packages are regenerated with motorsport-formatted chart axes, and
Nelson Jeanrenaud approved the qualifying analysis architecture and directed
SPEC-011 closure on 2026-08-14.

## Spec amendments

- **2026-08-14 — Analyst-readiness correction (approved by Nelson Jeanrenaud):**
  Publication policy advances to version 2. Deleted-lap integrity conflicts now
  block readiness; material wet conditions and interruptions become primary
  session context; sector synthesis must state the supported motorsport
  conclusion; progression moves to session time with running-best, cutoff,
  compound, rainfall, and red-flag context; field-wide median evolution is
  supporting only; raw traffic proximity counts are removed from analyst and
  reader output. No additional recipes are introduced.

- **2026-08-14 — Presentation and synthesis correction (approved by Nelson Jeanrenaud):**
  Publication policy advances to version 3. The three approved analytical
  recipes remain available, but the pole-and-cutoff margin chart is no longer
  selected automatically; its values appear as labelled findings. At a Glance
  contains findings rather than category labels. Long red-flag periods retain
  session-time meaning but use a visibly compressed axis, and deleted laps and
  integrity conflicts use distinct labels and markers. Acceptance-package
  editorial framing may state source-backed crash attribution and session
  sequence supplied by the human editor, with the official sources recorded in
  package evidence. Condition synthesis leads with the competitive sequence,
  not aggregate wet-lap counts. No analytical recipe is added.

- **2026-08-14 — Output quality and provenance consistency (approved by Nelson Jeanrenaud):**
  Publication policy advances to version 4. Reader-facing qualifying lap times
  use motorsport `M:SS.mmm` formatting while typed evidence retains seconds.
  Sector synthesis preserves directional gains and recoveries across all three
  sectors when that reversal is material. Combined session context renders once
  rather than repeating a human lede and equivalent analytical paragraph. The
  strongest source-backed interpretation is shared by reader and analyst
  reports. Every ready export and blocked QA package exposes the same editorial
  source URLs, qualifying publication policy ID/version, and export contract
  version in auditable JSON; ready exports also include the publication plan.
  No analytical architecture or recipe changes are introduced.

Nelson Jeanrenaud approved the original spec on 2026-08-13 and approved this
amendment through the recorded editorial verdict on 2026-08-14.

- **2026-08-27 — Analysis-scoped narrative evidence (approved by Nelson
  Jeanrenaud):** In accordance with SPEC-009 AMEND-001, official Qualifying
  classification, integrity conflicts, and essential session context remain
  foundational evidence, while only result identities supported by generated
  Analysis charts may produce automatic narrative findings, conclusions, and
  Story selections. The Evidence surface separates Scope, Findings, and source
  detail and does not present every available session result as the subject of
  the Analysis. Tests cover zero, one, and several generated qualifying chart
  families plus scope-change freshness.

## Review checklist

- [x] spec_id is unique and follows the SPEC-XXX format.
- [x] Every requirement has an ID, statement, rationale, acceptance criteria,
      verification method, and evidence location.
- [x] Non-goals are listed.
- [x] Open questions are resolved or explicitly deferred.
- [x] Verification matrix covers every requirement.
- [x] Conflict check completed.
- [x] Human approval recorded before status is set to Approved.
