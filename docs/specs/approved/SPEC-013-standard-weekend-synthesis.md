---
doc_type: spec
spec_id: SPEC-013
title: Standard Weekend Synthesis
status: In Implementation
owner: Nelson Jeanrenaud
related_issue:
related_prs: []
delivery_refs: []
affected_components:
  - report synthesis
  - publication selection and rendering
  - report review and readiness
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
  - SPEC-009
  - SPEC-010
  - SPEC-011
  - SPEC-012
conflicts_with: []
last_verified_at: 2026-08-24
---

# SPEC-013: Standard Weekend Synthesis

## Summary

This spec adds one publication-ready narrative for a standard Formula 1
weekend by synthesizing already accepted Practice, Qualifying, and Race
evidence from the same event. It reuses current session results, claims, and
chart artifacts without rerunning or replacing any session analytics. The
weekend report tells one chronological story, merges duplicate claims,
compares explicit pre-Race expectations with observed outcomes descriptively,
and preserves machine-readable links from every published claim to its source
session and analytical result. Publication contains three to five purposeful
existing figures. Sprint weekends and Sprint-format sessions are
outside this scope.

## Context

SPEC-009 makes typed analytical results authoritative for findings, synthesis,
review, freshness, and export. SPEC-010, SPEC-011, and SPEC-012 apply that
authority to Race, standard Qualifying, and one standard Practice session.
Each session report is deliberately bounded to its own evidence and explicitly
excludes full-weekend synthesis.

Readers nevertheless experience a Grand Prix as one weekend. Practice can
establish observed pace and condition context, Qualifying records the starting
competitive outcome, and the Race records the final outcome and its supported
strategy story. Publishing those reports consecutively repeats context and
leaves the reader to reconcile which earlier observations carried through,
which did not, and which comparisons are not supported. This spec adds that
editorial synthesis layer while leaving every session provider, calculation,
threshold, quality decision, and source hierarchy unchanged.

## Problem statement

The application cannot currently turn accepted evidence from multiple sessions
of one standard weekend into one concise, traceable article. A manual author
must copy claims from separate reports, remove repetition, reconcile evolving
observations, choose a small set of figures, and avoid turning descriptive
changes between sessions into causal explanations. That process can detach a
claim from its source result, silently reuse stale evidence, or imply that an
earlier observation predicted or caused a later outcome.

## Goals

- Combine accepted Practice, Qualifying, and Race evidence from one standard
  weekend into one coherent publication narrative.
- Reuse existing current session results and figures without recomputing
  session analytics.
- Place each publishable proposition once while retaining all supporting
  session and result references.
- Compare explicit pre-Race expectations with observed outcomes descriptively.
- Prevent unsupported causal, predictive, and counterfactual interpretation.
- Limit publication output to three to five purposeful figures without padding.
- Preserve claim-to-session, claim-to-result, and claim-to-asset traceability.
- Validate dry, disrupted, and mixed-condition standard weekends.

## Non-goals

- Sprint, Sprint Shootout, Sprint Qualifying, Sprint Race, or any weekend using
  a Sprint format.
- Recomputing, correcting, normalizing, or replacing Practice, Qualifying, or
  Race analytical results.
- Creating cross-session fuel, tyre, setup, engine-mode, degradation, traffic,
  strategy, or performance models.
- Predicting the Race from Practice or Qualifying evidence.
- Inferring team expectations, intent, targets, or programme from timing data.
- Claiming that an earlier-session observation caused a Qualifying or Race
  outcome merely because the events occurred in sequence.
- Cross-event, season, team, or driver trend reporting.
- Live weekend reporting before accepted Race evidence exists.
- New session chart recipes, combined telemetry plots, or chart-level
  recalculation of source metrics.
- External editorial research, autonomous source discovery, CMS publication,
  or social-media output.

## Users or actors

- A motorsport analyst selecting accepted evidence for a weekend story.
- A publication author providing bounded framing and explicit expectations.
- A motorsport editor reviewing the complete weekend narrative.
- The local Analysis Workbench, report authority, and package exporter.
- Optional read-only LLM consumers of bounded report summaries.

## Authoritative concepts

### Standard weekend scope

A standard weekend target identifies one championship event and may contain
FP1, FP2, and FP3, one standard Qualifying session with Q1/Q2/Q3 semantics, and
one Race. It contains no Sprint-format session. Up to three Practice inputs are
allowed, but at least one accepted Practice input, one accepted standard
Qualifying input, and one accepted Race input are required for a publishable
weekend synthesis. A cancelled or unavailable Practice session may be recorded
as context, but it does not satisfy the accepted Practice-evidence minimum.

Every included session must resolve to the same season, event identity, and
standard-weekend format. Display-name similarity is not sufficient identity.
An event mismatch, duplicated session type, Sprint-format marker, or ambiguous
format blocks synthesis.

### Accepted session evidence

The weekend synthesizer consumes immutable references to current analytical
results, accepted findings or conclusions, reviewed human framing, and accepted
chart artifacts already owned by the session analyses. An input claim is
eligible only when its source result is current, its review state is accepted,
its report disposition permits publication, and every source-session readiness
or integrity rule required for that claim is satisfied.

Unavailable, unknown, confounded, rejected, and stale results remain visible in
Evidence when useful for explaining a gap, but they cannot be restated as
positive findings. Weekend readiness never overrides a source-session blocker.
The source result payload, provider version, policy version, source fingerprint,
quality, limitations, and measurement category remain authoritative.

### Permitted synthesis operations

Weekend synthesis may select, order, group, deduplicate, qualify, and render
accepted source claims. It may compare the semantic status of an explicit
earlier expectation with an accepted later outcome. It may not reload raw
timing or telemetry, call a session analytical provider, derive a new session
metric, change a threshold, recalculate a scalar, or strengthen a source
claim's measurement category or quality.

Formatting an existing value, resolving a source reference, or arranging
existing figure assets is not analytical recomputation. Any value appearing in
the weekend report must be copied from one or more referenced source results or
from reviewed human framing that itself cites those results.

### Weekend claim and traceability

A weekend claim is one publication proposition with a stable weekend claim ID,
canonical subject, predicate, object or value, temporal scope, measurement
category, quality, limitations, source claim IDs, source session identities,
source result IDs, and optional source chart asset IDs. A claim may cite
multiple sessions and results, but every factual clause must resolve to at least
one source result. Human framing is stored separately from sourced factual
clauses and retains its author, review state, and result references.

Traceability is transitive: weekend claim to source claim, source session,
typed result, and evidence sidecar. The weekend package does not copy an
analytical value without also copying or referencing its identity and
provenance.

### Deduplication and evolution

Claims are duplicates when their normalized subject, predicate, object or
value, comparison basis, temporal scope, and underlying result identity are
equivalent. Equivalent claims are merged into one canonical placement whose
traceability union retains every supporting source reference.

Claims about the same subject are not duplicates when their values, conditions,
or temporal scopes differ materially. When those claims form a supported
sequence, the report may express one progression statement that names each
session phase and preserves every contributing result reference. A conflict
that cannot be explained by explicit scope or condition differences is shown
as disagreement or unavailable synthesis; the system does not choose a winner.

No claim or materially equivalent paraphrase may appear in more than one body
section, summary item, caption, or conclusion. A short navigational label may
refer to a body claim by ID without restating it.

### Expectations and outcomes

An expectation is eligible only when it was recorded before the Race as
reviewed human framing or an accepted source claim, is explicitly marked as an
expectation, and cites the accepted Practice or Qualifying results that bound
it. The synthesizer does not convert observed pace, grid position, or any other
earlier result into an expectation automatically.

An expectation-outcome comparison pairs that explicit expectation with one or
more accepted Qualifying or Race outcome results for the same subject and
comparison basis. The output uses the editorially descriptive states `aligned`,
`partially aligned`, `not aligned`, or `not comparable`, followed by the source
facts. Those states describe correspondence only; they are not scores, do not
feed a score, ranking, rate, or aggregate expectation-performance metric, do
not measure forecast skill, and do not establish why the outcome occurred. If
no eligible expectation exists, the report omits the comparison rather than
inventing one.

### Causality and uncertainty

Cross-session sequence, agreement, reversal, or non-alignment does not by
itself support causality. Weekend synthesis may carry forward a supported
session-local attribution only within its original scope and with its original
source and qualification. It may not extend that attribution to explain a
different session's outcome without an accepted result that explicitly owns
that relationship.

Terms including `because`, `caused`, `led to`, `resulted in`, `proved`,
`confirmed`, `underperformed`, and `overperformed` require an explicit accepted
source relationship appropriate to the clause. Otherwise the report uses
chronological and descriptive wording such as `earlier`, `later`, `while`,
`compared with`, `aligned with`, or `did not align with`. Unknown and confounded
states remain explicit.

### Purposeful figure policy

A publishable weekend report contains three to five figures selected
from accepted source-session chart artifacts. Each figure must support a
distinct placed weekend claim or claim cluster, add information not already
communicated by another included figure, retain its source result and asset
identity, and remain valid outside its original package through package-local
copying. Captions and alt text must state the session and the supported point.

The synthesizer does not generate a new analytical chart or modify plotted
values. Multiple visual renderings of the same primary result count as
redundant unless they support materially different accepted claims. Publication
never adds a figure to reach a preferred count. Fewer than three purposeful
eligible figures blocks readiness; more than five figures is rejected.

### Canonical narrative structure

The reader report uses this ordered structure:

1. `Weekend Story` — the reviewed lede and no more than three non-duplicative
   summary claims spanning the weekend.
2. `From Practice to the Grid` — only the accepted evidence needed to establish
   the pre-Race competitive context and Qualifying outcome.
3. `Race Outcome` — the accepted result and race-defining evidence needed to
   complete the story.
4. `Expectations and Outcomes` — optional; rendered only for one or more
   eligible explicit expectation comparisons.
5. `Evidence and Limitations` — concise source-session coverage, material
   unknowns, conflicts, and links to the machine-readable evidence sidecar.

This is one weekend narrative, not five concatenated session reports. Session
chronology determines factual order, while editorial selection determines
which accepted claims are necessary. Unselected accepted evidence remains
inspectable in the analyst view.

## Functional requirements

### REQ-001: Enforce standard-weekend scope

- **Statement:** The system must accept only one non-Sprint championship event
  containing accepted Practice, standard Qualifying, and Race evidence and
  reject Sprint-format or cross-event inputs.
- **Rationale:** Session semantics and evidence authority differ on Sprint
  weekends, and cross-event synthesis is outside this increment.
- **Acceptance criteria:** A same-event standard weekend with at least one
  accepted FP1/FP2/FP3 input, one accepted Q1/Q2/Q3 Qualifying input, and one
  accepted Race input is eligible; Sprint markers, Sprint sessions, duplicate
  Qualifying or Race inputs, event mismatches, and ambiguous formats return
  explicit unsupported-scope diagnostics.
- **Verification method:** Automated scope, identity, and dispatch tests.
- **Evidence location:** To be filled during implementation.

### REQ-002: Consume accepted current session evidence

- **Statement:** Weekend synthesis must consume only current, accepted,
  reportable source claims and results from the existing session authorities.
- **Rationale:** The weekend layer must not bypass review, freshness, source
  integrity, or provider-owned reportability.
- **Acceptance criteria:** Every selected source item records its session,
  result, review, disposition, fingerprint, provider, and policy identity;
  stale, rejected, unavailable, unknown, confounded, or blocked inputs cannot
  become positive weekend findings; a source-session integrity blocker remains
  a weekend blocker for dependent claims.
- **Verification method:** Automated eligibility truth tables and integration
  tests.
- **Evidence location:** To be filled during implementation.

### REQ-003: Prohibit session analytical recomputation

- **Statement:** The weekend workflow must not load raw session data or invoke,
  reproduce, or alter Practice, Qualifying, or Race analytics.
- **Rationale:** Existing accepted results are the analytical source of truth.
- **Acceptance criteria:** Synthesis reads persisted result and publication
  records only; no source gateway or session provider is invoked; every
  published scalar exactly matches a referenced source result after display
  formatting; provider thresholds and quality grades remain unchanged.
- **Verification method:** Automated dependency-spy, value-parity, and
  architecture inspection tests.
- **Evidence location:** To be filled during implementation.

### REQ-004: Build an explicit weekend session inventory

- **Statement:** The system must record the included, unavailable, cancelled,
  and omitted standard-weekend sessions in chronological order.
- **Rationale:** Readers and reviewers need to know which evidence phases the
  synthesis covers without treating missing running as evidence.
- **Acceptance criteria:** The inventory records event identity, format,
  session type, session time, source analysis/package ID, source status, and
  inclusion reason; zero to three Practice entries are represented without
  inventing cancelled-session results; Qualifying and Race are unique.
- **Verification method:** Automated schema, ordering, and missing-session
  tests.
- **Evidence location:** To be filled during implementation.

### REQ-005: Create traceable weekend claims

- **Statement:** Every factual weekend proposition must have one stable claim
  ID and transitive references to all owning source sessions, claims, results,
  and optional chart assets.
- **Rationale:** Multi-session prose must remain auditable to the accepted
  analytical evidence.
- **Acceptance criteria:** Every factual clause in article JSON and Markdown
  resolves to a weekend claim ID; every weekend claim resolves to at least one
  source result and session; copied values match their sources; broken,
  cross-event, or category-incompatible references fail validation.
- **Verification method:** Automated graph-integrity, value-parity, relocation,
  and rendered-output tests.
- **Evidence location:** To be filled during implementation.

### REQ-006: Deduplicate equivalent claims

- **Statement:** The system must merge equivalent claims into one canonical
  placement while retaining the union of their supporting references.
- **Rationale:** Repetition across session reports weakens the weekend story and
  obscures the actual evidence base.
- **Acceptance criteria:** Equivalent normalized claims appear once; summaries,
  body sections, captions, and conclusions do not restate the same proposition;
  merged claims retain every supporting session/result reference; materially
  different temporal or conditional claims remain distinct.
- **Verification method:** Automated equivalence, paraphrase, placement, and
  reference-union tests plus manual editorial inspection.
- **Evidence location:** To be filled during implementation.

### REQ-007: Represent supported evolution and disagreement

- **Statement:** Related non-duplicate claims must be sequenced by session and
  either expressed as a traceable progression or exposed as disagreement,
  confounding, or unavailable synthesis.
- **Rationale:** Changing conditions and outcomes must not be flattened into a
  false consistent trend.
- **Acceptance criteria:** Progression statements name the relevant phases and
  cite each source result; explicit condition or scope changes remain visible;
  unresolved source conflicts block the affected synthesis claim; the system
  never silently selects one conflicting accepted claim.
- **Verification method:** Automated progression and conflict fixtures plus
  manual mixed-condition review.
- **Evidence location:** To be filled during implementation.

### REQ-008: Produce one coherent weekend narrative

- **Statement:** The publication plan must use the canonical weekend structure
  and select the minimum accepted evidence needed to tell one chronological
  story rather than concatenate session reports.
- **Rationale:** The reader needs synthesis, not repeated session summaries.
- **Acceptance criteria:** Required sections appear in order; the optional
  expectation section appears only when populated; Weekend Story has no more
  than three distinct summary claims; each body claim has one canonical
  placement; unselected accepted evidence remains available to reviewers.
- **Verification method:** Automated plan and golden-render tests plus manual
  editorial rubric.
- **Evidence location:** To be filled during implementation.

### REQ-009: Compare explicit expectations and outcomes descriptively

- **Statement:** The system may compare an earlier expectation with a later
  outcome only when the expectation is explicit, pre-Race, reviewed, and
  traceable to accepted Practice or Qualifying results.
- **Rationale:** Earlier observations must not be retroactively turned into
  predictions.
- **Acceptance criteria:** Eligible pairs use `aligned`, `partially aligned`,
  `not aligned`, or `not comparable`; every state cites the expectation and
  outcome evidence; no expectation is inferred from timing, pace, grid, or
  classification alone; the states remain editorial descriptors and never feed
  a score, ranking, rate, or aggregate performance metric; absent eligible
  expectations omit the section without blocking the rest of an otherwise ready
  report.
- **Verification method:** Automated pairing truth table, phrase-policy tests,
  and manual editorial review.
- **Evidence location:** To be filled during implementation.

### REQ-010: Prevent unsupported causal interpretation

- **Statement:** Weekend synthesis must preserve source qualifications and must
  not infer cause, prediction, intent, or counterfactual outcome across
  sessions.
- **Rationale:** Chronology and correspondence are not causal evidence.
- **Acceptance criteria:** Unsupported causal and predictive phrases fail
  readiness; supported session-local attribution retains its original scope
  and source; no cross-session causal wording is published without an accepted
  result that explicitly owns that relationship; unknown and confounded states
  remain reader-visible.
- **Verification method:** Automated adversarial phrase fixtures, result-scope
  checks, and manual review.
- **Evidence location:** To be filled during implementation.

### REQ-011: Select three to five purposeful figures

- **Statement:** A publishable weekend plan must contain three to five
  non-redundant figures selected from accepted source-session chart artifacts.
- **Rationale:** A weekend report needs enough visual evidence to span the story
  without becoming a chart dump.
- **Acceptance criteria:** Every figure maps to a distinct placed claim or claim
  cluster and retains source result/asset identity; no plotted value is
  recomputed or modified; duplicate primary-result figures are rejected unless
  they support materially different accepted claims; no figure is selected to
  pad the count; fewer than three eligible purposeful figures blocks readiness;
  more than five is invalid.
- **Verification method:** Automated selection, redundancy, asset-integrity,
  and minimum/maximum tests plus manual visual review.
- **Evidence location:** To be filled during implementation.

### REQ-012: Preserve review, freshness, and readiness authority

- **Statement:** Weekend claims, framing, expectations, placements, and figures
  must participate in the existing review and freshness workflow without
  weakening any source-session readiness rule.
- **Rationale:** Multi-session output becomes stale whenever any selected source
  or editorial decision changes.
- **Acceptance criteria:** A source fingerprint, result, review, expectation,
  framing, placement, or asset change marks dependent weekend content stale;
  stale or unreviewed selected content blocks readiness; refresh preserves
  unchanged identities and accepted review where the existing authority allows;
  stale writes are rejected atomically.
- **Verification method:** Automated freshness, concurrency, persistence, and
  readiness transition tests.
- **Evidence location:** To be filled during implementation.

### REQ-013: Export one portable traceable package

- **Statement:** Preview and export must render the same reviewed weekend plan
  and produce a portable package containing the article, evidence graph,
  manifest, and selected source figures.
- **Rationale:** The reader artifact must remain equivalent to reviewed state
  and independently auditable after relocation.
- **Acceptance criteria:** Markdown and structured article content are
  equivalent; package-relative figure links survive relocation; the evidence
  sidecar maps every claim to source session/result identities and limitations;
  the manifest records source package fingerprints, synthesis policy version,
  figure count, and package health; no unselected chart is exported.
- **Verification method:** Automated preview/export parity, golden, containment,
  relocation, and manifest tests.
- **Evidence location:** To be filled during implementation.

### REQ-014: Provide bounded weekend inspection

- **Statement:** The local UI and read-only agent interface must expose weekend
  coverage, placed claims, source links, limitations, readiness, and freshness
  without exposing raw telemetry or mutation capabilities.
- **Rationale:** Analysts and bounded consumers need to audit the synthesis at
  the correct semantic level.
- **Acceptance criteria:** Story, Evidence, Preview, and Export distinguish
  weekend synthesis from source sessions; a reviewer can navigate from a claim
  to each source session and result; missing or blocked evidence is explicit;
  bounded inspection returns summaries and IDs only.
- **Verification method:** Automated component/API tests and desktop/mobile
  browser inspection.
- **Evidence location:** To be filled during implementation.

### REQ-015: Validate three material weekend conditions

- **Statement:** Acceptance must exercise one dry, one disrupted, and one
  mixed-condition standard weekend through the application workflow.
- **Rationale:** Deduplication, condition qualification, chronology, and causal
  restraint must hold beyond a clean dry event.
- **Acceptance criteria:** The dry package has accepted Practice, Qualifying,
  and Race evidence under dry conditions; the disrupted package includes at
  least one source-recorded red flag, safety car, virtual safety car,
  suspension, shortened session, or cancellation; the mixed-condition package
  contains accepted wet and dry condition evidence within or across included
  sessions; every package contains three to five purposeful figures and passes
  one common traceability/editorial rubric or demonstrates the expected
  source-integrity block without claiming readiness; all are non-Sprint events.
- **Verification method:** End-to-end package generation, automated integrity
  checks, responsive visual inspection, and recorded human verdict.
- **Evidence location:** To be filled during implementation.

### REQ-016: Preserve source-session behavior

- **Statement:** Adding weekend synthesis must not change the analytics,
  publication output, or stored semantics of standalone Practice, Qualifying,
  and Race reports.
- **Rationale:** This feature composes accepted outputs and does not generalize
  or reinterpret their contracts.
- **Acceptance criteria:** Existing SPEC-010, SPEC-011, and SPEC-012 fixtures
  reopen and render unchanged; standalone session tests pass; no source result
  schema is reinterpreted; weekend-specific code remains behind weekend
  dispatch.
- **Verification method:** Full regression suite, stored-package compatibility
  tests, and architecture inspection.
- **Evidence location:** To be filled during implementation.

## Non-functional requirements

### NFR-001: Deterministic synthesis

- **Statement:** Identical accepted inputs, review state, editorial framing,
  and policy versions must produce identical claim identity, ordering,
  deduplication, figure selection, and package content.
- **Rationale:** Review and traceability require reproducible output.
- **Acceptance criteria:** Repeated generation produces the same structured
  plan, claim graph, selected asset set, and package hash apart from explicitly
  excluded timestamps.
- **Verification method:** Automated repeated-run comparison.
- **Evidence location:** To be filled during implementation.

### NFR-002: Editorial economy

- **Statement:** The reader report must be concise, non-repetitive, and
  understandable without opening the three source session reports.
- **Rationale:** Weekend synthesis should reduce editorial burden and reader
  repetition.
- **Acceptance criteria:** No claim appears twice; no section is empty; no more
  than three Weekend Story claims are used; three to five figures suffice to
  support the selected story; a human rubric finds no required structural
  rewrite or analytical reconstruction.
- **Verification method:** Automated structure checks and human editorial
  review.
- **Evidence location:** To be filled during implementation.

### NFR-003: Accessible responsive output

- **Statement:** Weekend Story, Evidence, Preview, and exported output must be
  keyboard accessible and readable at desktop and 390x844 viewports.
- **Rationale:** The existing publication workflow is used on desktop and
  mobile review surfaces.
- **Acceptance criteria:** No horizontal overflow; focus order and accessible
  names are correct; readiness and source states do not rely on colour alone;
  each figure has concise session-aware alt text.
- **Verification method:** Frontend checks and manual browser inspection.
- **Evidence location:** To be filled during implementation.

### NFR-004: Bounded synthesis cost

- **Statement:** Weekend synthesis must operate on persisted result and package
  metadata without reopening FastF1 sessions or loading raw telemetry.
- **Rationale:** Composition should be materially cheaper and more reliable than
  session analysis.
- **Acceptance criteria:** Performance tests show no source gateway calls and
  memory use is bounded by selected persisted results and figure assets.
- **Verification method:** Automated dependency and performance tests.
- **Evidence location:** To be filled during implementation.

## Security and privacy considerations

### SEC-001: Preserve package containment

- **Statement:** Imported source references, editorial Markdown, and copied
  figure assets must remain within the local analysis and export roots and pass
  the existing sanitisation contract.
- **Rationale:** Combining packages increases path and content inputs but must
  not weaken local preview safety.
- **Acceptance criteria:** Traversal, absolute-path escape, unsafe links,
  scripts, and malformed Markdown are rejected or sanitised; copied assets use
  validated package-local names; source packages are not modified.
- **Verification method:** Automated path, injection, and containment tests.
- **Evidence location:** To be filled during implementation.

### SEC-002: Keep publication local

- **Statement:** Weekend synthesis and export must not transmit evidence,
  telemetry, editorial content, or packages to an external service.
- **Rationale:** The established reporting workflow is local-first.
- **Acceptance criteria:** No network publishing dependency or credential is
  introduced; export writes only to the configured local destination.
- **Verification method:** Dependency and API inspection.
- **Evidence location:** To be filled during implementation.

## Data model impact

### DATA-001: Version the weekend synthesis record

- **Statement:** Persist a versioned weekend record containing event identity,
  format, session inventory, source fingerprints, synthesis policy identity,
  claim graph, review state, readiness, and freshness.
- **Rationale:** Multi-session synthesis must be durable and migration-safe.
- **Acceptance criteria:** Schema validation rejects missing identities,
  duplicate unique sessions, Sprint inputs, invalid references, and unknown
  versions; round trips preserve stable IDs and order; legacy analyses remain
  readable.
- **Verification method:** Automated schema, serialization, migration, and
  compatibility tests.
- **Evidence location:** To be filled during implementation.

### DATA-002: Persist transitive claim provenance

- **Statement:** Each weekend claim must persist its source claim IDs, session
  IDs, result IDs, measurement category, quality, limitations, and selected
  asset IDs.
- **Rationale:** Rendered prose alone cannot preserve multi-session evidence
  lineage.
- **Acceptance criteria:** Referential-integrity validation is complete and
  acyclic; no factual claim has an empty result set; merged claims preserve the
  reference union; deleted or changed source identity makes the claim stale.
- **Verification method:** Automated graph, mutation, and freshness tests.
- **Evidence location:** To be filled during implementation.

### DATA-003: Persist expectation-outcome pairs

- **Statement:** Expectation comparisons must store the reviewed expectation,
  its temporal and result provenance, outcome references, comparison basis,
  descriptive state, limitations, and review state.
- **Rationale:** Expectation language needs stronger provenance than ordinary
  chronology.
- **Acceptance criteria:** Post-Race or unreviewed expectations are invalid;
  missing bases produce `not comparable`; edits invalidate dependent review;
  no inferred expectation record is created automatically; descriptive states
  cannot be converted into a score, ranking, rate, or aggregate performance
  metric.
- **Verification method:** Automated schema and lifecycle tests.
- **Evidence location:** To be filled during implementation.

## API impact

### API-001: Add typed weekend workflow operations

- **Statement:** The local application API must support creating, inspecting,
  refreshing, reviewing, previewing, and exporting a standard-weekend synthesis
  with optimistic concurrency and typed diagnostics.
- **Rationale:** Weekend reports need the same atomic lifecycle as session
  reports.
- **Acceptance criteria:** Operations validate event scope and source versions;
  stale writes fail atomically; refresh does not mutate source analyses;
  unsupported Sprint inputs return typed diagnostics; preview/export consume
  the same reviewed plan.
- **Verification method:** Automated API, concurrency, and integration tests.
- **Evidence location:** To be filled during implementation.

### API-002: Extend bounded read-only inspection

- **Statement:** Read-only consumers may inspect weekend identity, session
  coverage, claim summaries, source IDs, figure count, limitations, and
  readiness but may not request raw evidence arrays or mutate review state.
- **Rationale:** Agent access should remain useful and bounded.
- **Acceptance criteria:** Responses are size-limited, identifier-based, and
  omit telemetry; no mutating weekend tool is added to the read-only contract.
- **Verification method:** Automated contract and payload-bound tests.
- **Evidence location:** To be filled during implementation.

## UI or UX impact

### UX-001: Distinguish weekend synthesis from session reports

- **Statement:** The Workbench must label the target as a Standard Weekend and
  show its Practice, Qualifying, and Race coverage without instructional UI
  prose.
- **Rationale:** Users must understand the composition target and source state
  at a glance.
- **Acceptance criteria:** Concise labels expose event, format, session status,
  readiness, and freshness; Sprint inputs show an unsupported state; source
  session reports remain independently navigable.
- **Verification method:** Component tests and browser inspection.
- **Evidence location:** To be filled during implementation.

### UX-002: Make provenance navigable

- **Statement:** Reviewers must be able to navigate from every weekend claim
  and figure to all referenced source sessions, results, and limitations.
- **Rationale:** Deduplication must not hide evidence ownership.
- **Acceptance criteria:** Merged and progression claims expose multiple source
  references clearly; broken references are non-interactive errors; keyboard
  navigation and focus return are preserved.
- **Verification method:** Automated navigation/state tests and manual keyboard
  review.
- **Evidence location:** To be filled during implementation.

### UX-003: Keep figure selection focused

- **Statement:** Story and Preview must present three to five selected figures
  in narrative order while Evidence retains the broader eligible asset set.
- **Rationale:** The publication should be purposeful without hiding analyst
  evidence.
- **Acceptance criteria:** Figure count and redundancy diagnostics are visible
  to the reviewer; captions name their session and claim; figures remain
  legible at supported viewports; unavailable figures do not create empty
  placeholders.
- **Verification method:** Component tests and desktop/mobile visual review.
- **Evidence location:** To be filled during implementation.

### UX-004: Preserve preview/export equivalence

- **Statement:** Preview must show the exact reviewed structure, prose, claims,
  figures, captions, and limitations written to export.
- **Rationale:** Human acceptance must apply to the delivered artifact.
- **Acceptance criteria:** Structured and rendered parity tests pass; no analyst
  controls or rejected evidence leak into reader output; export health and
  source blockers are visible before export.
- **Verification method:** Automated parity tests and browser/package review.
- **Evidence location:** To be filled during implementation.

## Configuration impact

- Add a versioned Standard Weekend synthesis policy identifier.
- Add no environment variable, network service, feature score, or adjustable
  analytical threshold.
- Keep source-session provider and publication policies unchanged.
- Figure minimum three and maximum five are fixed by this spec, not user-tunable
  defaults; no preferred count or padding rule exists within that range.

## Error handling

- Reject Sprint-format, cross-event, duplicate Qualifying/Race, or ambiguous
  weekend identity before creating a synthesis.
- Report missing accepted Practice, Qualifying, or Race evidence as a typed
  readiness blocker without generating substitute analytics.
- Mark dependent claims stale when a selected source changes or disappears.
- Expose source conflicts, unknowns, and confounding at claim scope; do not
  silently discard them to make a narrative coherent.
- Reject invalid or escaping figure assets and keep source packages unchanged.
- Block readiness for fewer than three purposeful figures and reject more than
  five.
- Reject unsupported causal or inferred-expectation language with the affected
  claim ID and reason.

## Edge cases

- FP1, FP2, or FP3 is cancelled, shortened, or has no accepted reportable
  evidence.
- More than one Practice report contributes the same condition or competitive
  claim.
- Practice and Qualifying observations differ because recorded conditions or
  comparison bases changed.
- Qualifying order and final starting order differ, or the Race starts from the
  pit lane.
- A Race result remains provisional or a selected session result is corrected
  after weekend review.
- An explicit expectation exists but its subject or comparison basis does not
  match the Race outcome.
- No explicit expectation exists.
- The same result supports several source charts but only one is purposeful.
- Only three eligible figures survive source readiness or asset-integrity
  checks.
- A disrupted weekend is otherwise dry.
- A mixed-condition weekend contains wet running in only one session.
- A session-local causal attribution is supported, but no accepted result links
  it to a later session outcome.
- Two accepted source claims conflict without a recorded condition or scope
  distinction.

## Acceptance criteria

SPEC-013 is ready for implementation only after human approval. Implementation
is complete only when:

1. Only same-event standard weekends with accepted Practice, Qualifying, and
   Race evidence are accepted; every Sprint-format input is rejected.
2. The workflow consumes existing accepted current results without source
   gateway access or analytical recomputation.
3. One canonical narrative places each proposition once and preserves
   supported progression, disagreement, uncertainty, and source qualifications.
4. Explicit expectations are compared with outcomes descriptively; no earlier
   observation is automatically converted into a prediction.
5. Unsupported causal, predictive, intent, and counterfactual claims block
   publication.
6. Every ready package contains three to five purposeful accepted source
   figures and no new analytical chart.
7. Every factual clause and figure resolves through the weekend evidence graph
   to source session and result identity.
8. Preview/export parity, review, freshness, portability, accessibility, and
   standalone session regressions pass.
9. Dry, disrupted, and mixed-condition non-Sprint packages pass the common
   rubric or demonstrate an expected source-integrity block without claiming
   readiness.

## Verification matrix

| Requirement ID | Acceptance criterion | Verification method | Test / command / manual check | Evidence location | PR reference |
| -------------- | -------------------- | ------------------- | ----------------------------- | ----------------- | ------------ |
| REQ-001 | Standard same-event weekends only | Automated | Scope and identity tests | `tests/test_weekend_synthesis.py::test_sprint_cross_event_and_duplicate_session_scope_are_rejected` | Pass |
| REQ-002 | Only accepted current session evidence is publishable | Automated | Eligibility and blocker truth tables | `tests/test_weekend_synthesis.py::test_rejected_stale_unknown_and_causal_claims_cannot_publish` | Pass |
| REQ-003 | No session analytics are recomputed | Automated/inspection | Dependency-spy and value-parity tests | `tests/test_dependency_boundaries.py::test_weekend_composer_does_not_import_source_data_or_analytics` | Pass |
| REQ-004 | Weekend session coverage is explicit and ordered | Automated | Inventory schema/order tests | `tests/test_weekend_synthesis.py::test_dry_weekend_is_deterministic_traceable_and_exportable` | Pass |
| REQ-005 | Every factual claim is transitively traceable | Automated | Graph, value, and relocation tests | `tests/test_weekend_synthesis.py::test_dry_weekend_is_deterministic_traceable_and_exportable` | Pass |
| REQ-006 | Equivalent claims have one canonical placement | Automated/manual | Deduplication and editorial review | `analysis/weekend.py::_merge_and_check_claims`; human editorial review pending | Automated pass; manual pending |
| REQ-007 | Evolution and disagreement remain qualified | Automated/manual | Progression/conflict/mixed-condition fixtures | `tests/test_weekend_synthesis.py::test_disrupted_and_mixed_conditions_remain_qualified`; human review pending | Automated pass; manual pending |
| REQ-008 | Output is one coherent canonical narrative | Automated/manual | Plan/golden tests and rubric | `test_dry_weekend_is_deterministic_traceable_and_exportable`; human rubric pending | Automated pass; manual pending |
| REQ-009 | Only explicit expectations are compared | Automated/manual | Pairing truth table and editorial review | `test_explicit_pre_race_expectation_is_compared_descriptively`; human review pending | Automated pass; manual pending |
| REQ-010 | Unsupported causality is rejected | Automated/manual | Adversarial phrase and scope tests | `test_rejected_stale_unknown_and_causal_claims_cannot_publish`; human review pending | Automated pass; manual pending |
| REQ-011 | Publication contains three to five purposeful figures without padding | Automated/manual | Selection, redundancy, and visual tests | `test_dry_weekend_is_deterministic_traceable_and_exportable`; visual review pending | Automated pass; manual pending |
| REQ-012 | Review, freshness, and readiness remain authoritative | Automated | Lifecycle and concurrency tests | `test_workbench_api_persists_composes_inspects_and_exports_atomically` | Pass |
| REQ-013 | Export is portable, exact, and traceable | Automated/manual | Parity, containment, and package review | `test_dry_weekend_is_deterministic_traceable_and_exportable`; package review pending | Automated pass; manual pending |
| REQ-014 | Weekend inspection is bounded and navigable | Automated/manual | UI/API tests and browser review | Bounded/API tests plus desktop and 390x844 Story/Evidence/Preview/Export browser review | Pass |
| REQ-015 | Dry, disrupted, and mixed weekends are validated | Automated/manual | Three end-to-end packages and human verdict | Synthetic deterministic fixtures pass; application packages and verdicts pending | Partial |
| REQ-016 | Standalone session behavior is unchanged | Automated/inspection | Full regression and compatibility suite | Full unittest discovery: 189 tests passed | Pass |
| NFR-001 | Identical inputs produce identical synthesis | Automated | Repeated-run hash comparison | `test_dry_weekend_is_deterministic_traceable_and_exportable` | Pass |
| NFR-002 | Report is concise and non-repetitive | Automated/manual | Structure checks and editorial rubric | Three-summary cap and canonical placement automated; human rubric pending | Automated pass; manual pending |
| NFR-003 | Output is accessible and responsive | Automated/manual | Frontend gates and 390x844 review | Frontend typecheck/build; 1280 desktop and 390x844 browser checks, no overflow or console errors | Pass |
| NFR-004 | Synthesis cost excludes source loading | Automated | Dependency and performance tests | Dependency-boundary test and persisted-record API test | Pass |
| SEC-001 | Combined package remains contained and sanitised | Automated | Path and injection tests | `_contained_source`, `_safe_text`, export relocation test | Pass |
| SEC-002 | Workflow remains local | Inspection | Dependency/API review | Local filesystem export and local FastAPI routes; no external dependency | Pass |
| DATA-001 | Weekend record is versioned and migration-safe | Automated | Schema and compatibility tests | Schema/policy assertions in weekend tests and workspace persistence test | Pass |
| DATA-002 | Claim provenance is complete and acyclic | Automated | Graph and freshness tests | Traceability assertions and evidence-fingerprint concurrency test | Pass |
| DATA-003 | Expectation pairs retain provenance and lifecycle | Automated | Schema and lifecycle tests | `test_explicit_pre_race_expectation_is_compared_descriptively` | Pass |
| API-001 | Weekend operations are typed, atomic, and stale-safe | Automated | API/concurrency tests | `test_workbench_api_persists_composes_inspects_and_exports_atomically` | Pass |
| API-002 | Inspection is bounded and read-only | Automated | Contract and payload tests | `test_bounded_inspection_enforces_payload_limit` and API inspection assertion | Pass |
| UX-001 | Weekend target and coverage are clear | Automated/manual | Component and browser checks | Weekend Story/Evidence/Preview/Export reviewed at 1280 and 390x844 | Pass |
| UX-002 | Claim provenance is keyboard-navigable | Automated/manual | Navigation and keyboard checks | Evidence disclosure opened with Enter at 390x844; no overflow or console errors | Pass |
| UX-003 | Four or five figures remain focused and readable | Automated/manual | Selection and visual review | Three-to-five selection automated; responsive Weekend views passed browser review | Pass |
| UX-004 | Preview and export are equivalent | Automated/manual | Parity and package checks | Markdown/export parity assertion and Workbench Preview/Export browser review | Pass |

## Test plan

### Unit tests

- Standard-weekend event identity, accepted session combinations, cancelled
  Practice, and explicit rejection of every Sprint-format session.
- Source eligibility across current, stale, accepted, rejected, unavailable,
  unknown, confounded, and integrity-blocked states.
- Dependency spies proving no FastF1 gateway or session provider call.
- Exact scalar and formatted-value parity with source results.
- Session inventory ordering, missing phases, and duplicate inputs.
- Claim identity, normalization, equivalence, reference union, progression,
  disagreement, conflict, and one-placement validation.
- Expectation timing, review, provenance, subject/basis matching, descriptive
  states, and no-expectation omission.
- Causal, predictive, intent, counterfactual, and retrospective phrasing
  rejection.
- Figure eligibility, primary-result redundancy, count boundaries, caption,
  alt text, copying, and asset integrity.
- Freshness propagation from source fingerprint, result, review, framing,
  expectation, placement, and asset changes.

### Integration and API tests

- Create a weekend synthesis from persisted source analyses without mutating or
  rerunning them.
- Save, reload, refresh, review, preview, and export without identity loss.
- Reject stale writes and preserve accepted unchanged review state under the
  existing authority.
- Prove a source-session blocker remains effective in weekend readiness.
- Resolve every rendered claim and selected figure through the package evidence
  graph after relocation.
- Reopen and rerun existing Practice, Qualifying, and Race analyses and report
  packages unchanged.

### Frontend and visual tests

- Weekend Story, Evidence, Preview, and Export at desktop and 390x844.
- Keyboard navigation, focus return, accessible names, non-colour readiness,
  session-aware captions, and chart alt text.
- Multi-source navigation for merged and progression claims.
- Three-, four-, and five-figure layouts without overflow or redundant visual
  hierarchy.
- Explicit Sprint unsupported state, source blockers, unknowns, conflicts, and
  no-expectation omission.
- Exact preview/export structure and content parity.

### Acceptance packages

- One dry standard weekend with accepted Practice, Qualifying, and Race
  evidence and three to five purposeful figures.
- One disrupted standard weekend with a source-recorded red flag, safety car,
  virtual safety car, suspension, shortened session, or cancellation.
- One mixed-condition standard weekend with accepted wet and dry condition
  evidence within or across included sessions and appropriately qualified
  comparisons.
- Record event/session identities, source fingerprints, provider and policy
  versions, weekend policy version, package hash, validation commands,
  screenshots, and human verdict for each.
- Apply one rubric: accurate chronology, no recomputation, accepted evidence
  only, one placement per claim, expectation/outcome discipline, no unsupported
  causality, three to five purposeful figures without padding, mobile
  readability, and complete claim-to-session/result traceability.

### Expected completion commands

- `python scripts/validate_governance.py`
- `python scripts/validate_specs.py`
- `python scripts/validate_drift.py`
- `python -m unittest discover -s tests -p "test_*.py"`
- Frontend typecheck and production build using the configured package manager.
- `git diff --check`

## Rollback plan

- Keep weekend schemas, synthesis policy, UI branches, and export rendering
  behind Standard Weekend dispatch.
- Do not migrate or reinterpret stored Practice, Qualifying, or Race results.
- If the weekend policy or evidence graph is defective, mark only dependent
  weekend plans and exports stale and require regeneration after correction.
- Roll back weekend registration and UI exposure together; source session
  reports remain independently reviewable and exportable.
- Preserve source packages as immutable inputs throughout rollback.

## Open questions

None. Exact dry, disrupted, and mixed-condition fixture events may be selected
during implementation planning if they satisfy REQ-015 and are recorded as
acceptance evidence; fixture identity does not change product behavior.

## Human decisions required

- [x] Approve SPEC-013 as written before implementation begins. Approval must
      confirm the standard-weekend-only boundary, reuse-without-recomputation
      rule, explicit-expectation contract, deduplication semantics,
      three-to-five figure policy, and mandatory dry/disrupted/mixed acceptance
      packages.

- **Human approval reference:** Nelson Jeanrenaud approved SPEC-013 in Codex on
  2026-08-25 and authorised implementation.

## Conflict check

- SPEC-009 remains authoritative for result ownership, findings, deterministic
  synthesis, review, freshness, and evidence. SPEC-013 composes accepted claims
  across sessions and does not create a competing analytical authority.
- SPEC-010 remains authoritative for Race analytics and reader publication.
  Its single-Race boundary is not changed; Race values, claims, and figures are
  referenced as immutable source evidence.
- SPEC-011 remains authoritative for standard Qualifying and explicitly leaves
  full-weekend synthesis out of scope. SPEC-013 depends on that output and does
  not generalize Qualifying or add Sprint semantics.
- SPEC-012 remains authoritative for individual FP1/FP2/FP3 reports and
  prohibits automatic prediction from Practice. SPEC-013 therefore requires an
  explicit reviewed expectation and never derives one from Practice pace.
- Shared publication, review, preview, and export components overlap by design
  and are declared in `depends_on`. No blocking conflict or supersession is
  identified.

## Traceability table

| Requirement ID | Design / component | Implementation (file/function) | Test | Status |
| -------------- | ------------------ | ------------------------------ | ---- | ------ |
| REQ-001 through REQ-016 | Standard Weekend synthesis, publication, review, export, and Workbench flow | `analysis/weekend.py`, `analysis/workspace.py`, `ui/server.py`, Workbench page | `test_weekend_synthesis.py`, dependency/full regression suites | In Implementation; manual acceptance pending |
| NFR-001 through NFR-004 | Determinism, editorial economy, responsive accessibility, bounded cost | Deterministic hashes, three-summary cap, bounded persisted-record composer, responsive Workbench components | Weekend tests, dependency boundary, frontend gates | In Implementation; responsive review pending |
| SEC-001 through SEC-002 | Existing sanitisation, containment, and local export | `_contained_source`, `_safe_text`, local export/API | Weekend export tests and inspection | Implemented |
| DATA-001 through DATA-003 | Weekend record, evidence graph, and expectation pairs | Versioned Pydantic weekend models and persisted workspace state | Weekend schema, traceability, expectation, persistence tests | Implemented |
| API-001 through API-002 | Typed workflow and bounded inspection | `AnalysisService.compose_weekend/inspect_weekend/export_weekend`, `/api/analysis/weekend*` | Workbench API and bounded-payload tests | Implemented |
| UX-001 through UX-004 | Weekend Story, provenance navigation, focused figures, and exact Preview/Export | `WeekendRecordPanel`, rebuilt embedded frontend | Typecheck/build and export parity; browser review pending | In Implementation |

## Implementation notes

- Human approval was recorded on 2026-08-25. The spec moved to
  `docs/specs/approved/` before product-code implementation began.
- Prefer a weekend-specific composer behind existing result, publication,
  review, and export extension points. Do not refactor the three session
  providers into a generic hierarchy unless a later approved amendment defines
  that larger change.
- Persist source identities and reference accepted artifacts; do not copy
  session calculations into a new provider.
- Implementation sequence:
  1. Add versioned weekend input, inventory, claim, expectation, plan,
     readiness, and package models plus a deterministic weekend composer.
  2. Add persisted Analysis Workbench operations and bounded API inspection
     without invoking source gateways or analytical providers.
  3. Extend reader/export rendering and the Workbench Story, Evidence, Preview,
     and Export surfaces behind Standard Weekend dispatch.
  4. Add dry, disrupted, and mixed-condition fixtures, targeted contract and
     parity tests, regression coverage, and requirement traceability.
- Fixture selection will use deterministic persisted-record fixtures owned by
  the weekend tests: dry, disrupted by a recorded safety-car context, and mixed
  wet/dry conditions. These fixtures exercise synthesis only and do not reload
  source datasets.
- Assumption: the approval message authorises the clerical lifecycle update
  from `In Review` to `In Implementation`; no behavioral requirement changed.
- Verification checkpoint, 2026-08-25:
  - `python -m unittest discover -s tests -p "test_*.py"`: passed, 189 tests.
  - `npm run typecheck` from `frontend/`: passed.
  - `npm run build` from `frontend/`: passed; existing chunk-size warning only.
  - The initial root-level `npm run typecheck; npm run build` attempt failed
    because the repository root has no `package.json`; both commands passed
    when rerun from the configured frontend directory.
  - Desktop 1280 and mobile 390x844 browser verification passed for Story,
    Evidence, Preview, and Export with no final overflow or console errors.
    Two mobile containment defects (fingerprints and export paths) were found
    and corrected; provenance disclosure was verified with the Enter key.
  - Application-generated real-session acceptance packages and human editorial
    verdicts remain required before completion.

## Spec amendments

### AMEND-001: Compose from explicit Analysis scopes and use a guided workflow

- **Date:** 2026-08-27
- **Reason:** SPEC-009 AMEND-001 rejects treating all loaded session results as
  the narrative scope, and product review found the Story/Evidence split hard to
  understand.
- **Changed requirements:** REQ-001 through REQ-006, REQ-009 through REQ-016,
  DATA-001 through DATA-004, API-001 through API-003, UX-001 through UX-004.
- **Behavioral impact:** Weekend composition consumes the chart-scoped findings
  and explicit foundational context of its source analyses. Loading or including
  a source session does not automatically promote all of its analytical results.
  The user workflow is Scope, Findings, Story, Preview, and Export, with source
  sessions and charts visible before composition and a persistent current-state
  and next-action summary. Existing cross-session evidence, chronology,
  non-causality, conflict, readiness, and provenance safeguards remain
  authoritative.
- **Test impact:** Add mixed-scope weekend fixtures, source chart changes,
  excluded result checks, stage navigation, and preview/export parity tests.
- **Human approval reference:** Nelson Jeanrenaud approved the review feedback
  and direct implementation in the Codex task conversation on 2026-08-27.

## Review checklist

- [x] spec_id is unique and follows the SPEC-XXX format.
- [x] Every requirement has an ID, statement, rationale, acceptance criteria,
      verification method, and evidence location.
- [x] Non-goals are listed.
- [x] Open questions are resolved or explicitly deferred.
- [x] Verification matrix covers every requirement.
- [x] Conflict check completed.
- [x] Human approval recorded before status set to Approved.
