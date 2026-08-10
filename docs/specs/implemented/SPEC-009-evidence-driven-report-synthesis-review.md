---
doc_type: spec
spec_id: SPEC-009
title: Evidence-Driven Report Synthesis and Review
status: Implemented
owner: Nelson Jeanrenaud
related_issue:
related_prs: []
delivery_refs: []
affected_components:
  - analysis observation pipeline
  - analytical result extension contract
  - report synthesis
  - report package export
  - analysis workspace persistence
  - local preview UI
  - LLM contract
affected_interfaces:
  - Analysis Workbench Review view
  - Analysis Workbench Export view
  - generated package manifest
  - observations and review data
  - portable Markdown draft
  - recipe metadata and plugin boundary
supersedes: []
superseded_by:
depends_on:
  - SPEC-001
  - SPEC-004
  - SPEC-008
conflicts_with: []
last_verified_at: 2026-08-10
---

# SPEC-009: Evidence-Driven Report Synthesis and Review

## Summary

This spec turns typed analytical results into a defensible factual
race-strategy report draft. Each unique analytical result is assessed by a
result-type-owned finding provider, which records one explicit report
disposition and may produce zero or more reportable findings. Charts are
optional evidence artifacts rather than owners of report semantics. A small
catalog of named, versioned motorsport rules may combine compatible,
deduplicated findings into traceable conclusions. The Analysis Workbench
presents publishable claims in a concise structured report with review,
inclusion, ordering, qualification, evidence-navigation, and freshness
controls. Export produces portable Markdown with selected package-relative
charts and explicit metadata links rather than a flat observation list or
chart-path inventory.

## Context

SPEC-001 introduced structured observations, editorial review states, evidence
links, and portable Markdown report packages. SPEC-004 made the Analysis the
durable working object and required Review and Export to operate on current
Analysis state without silently overwriting reviewed observation state.
SPEC-008 added seven race-strategy chart templates with typed, versioned
analytical metadata, explicit measurement categories, quality grades,
limitations, and unavailable states. SPEC-008 deliberately deferred automatic
natural-language strategy observations and cross-chart synthesis.

The current reporting mechanics are operational. Stale review state is
detected; findings can be accepted, rejected, edited, or reset; drafts can be
regenerated; Export Preview exposes charts, rendered and raw Markdown, and
integrity findings; and packages preserve supporting artifacts and metadata.

The current content layer does not use that machinery effectively. Observation
extraction operates globally over a dataset, maps artifacts by recipe ID, and
produces four generic observations: fastest selected-driver lap, best final
recorded selected-driver position, peak recorded speed, and compounds used.
Multiple visualizations of one result are not represented as shared analytical
evidence, while multiple instances of one recipe are not independently
traceable through that recipe-ID map. The Markdown renderer lists chart paths
and appends all non-rejected observations as one flat list. Consequently, the
analytical results provided by SPEC-008 do not flow into Review or into a
selective factual strategy report.

The canonical acceptance fixture remains the cached 2023 Bahrain Race analysis
established by the existing project workflow. This spec introduces no new
chart calculations. Typed analytical results remain authoritative for the
analytical values and categories reported by this feature. Chart metadata may
embed or reference those results but is not an independent analytical
authority.

## Problem statement

The system can produce and review strong analytical chart artifacts, but it
cannot turn their evidence into a coherent report. Report content is generic,
flat, weakly connected to typed analytical results, and unable to express
multi-result agreement, disagreement, comparison basis, confidence, or typed
unavailability. Reviewers cannot shape a report's structure or navigate from a
finding to all of its supporting evidence. Freshness is represented too
coarsely to distinguish changed evidence, invalidated review, a stale draft,
and an out-of-date export.

## Goals

- Treat typed analytical results as the semantic source of truth for reporting.
- Account for every eligible analytical result through a result-type-owned,
  versioned finding-generation contract without forcing every result into
  prose.
- Deduplicate shared analytical results before synthesis so multiple charts do
  not create duplicate findings.
- Keep charts as optional evidence that may support zero, one, or many findings.
- Combine compatible reportable findings through a small named catalog of
  deterministic motorsport conclusions without unsupported causal claims.
- Represent a report as ordered sections and ordered items rather than a flat
  observation list.
- Make confidence, comparison basis, limitations, evidence, and unavailable
  states explicit and reviewable.
- Give users clear inclusion and ordering controls for sections, findings,
  conclusions, and charts.
- Link Review findings to chart images and metadata through safe, clickable
  package-local navigation.
- Export portable Markdown that embeds included charts at their report
  positions and links their metadata.
- Distinguish evidence, review, draft, and export freshness and prevent stale
  material from appearing current.
- Preserve the current local-first, deterministic, package-oriented workflow
  and batch-generation compatibility.

## Non-goals

- Adding new chart templates or changing SPEC-008 analytical calculations.
- Claiming driver intent, strategic causality, undercut/overcut success, or
  counterfactual outcomes unless a future approved analytical contract supports
  those claims.
- Autonomous expert motorsport authorship, autonomous LLM-authored analysis, or
  allowing an LLM to override metrics,
  confidence, limitations, compatibility, or unavailable states.
- A generic expert-system or arbitrary rule-composition framework.
- A free-form word processor or arbitrary rich-document layout editor.
- Platform-specific publishing formats, hosted publication, or collaborative
  multi-user review.
- Multi-session, weekend, season, or cross-race synthesis in the first
  implementation.
- Mandatory report-finding support from third-party plugins that have not
  adopted the versioned finding-provider contract.
- Replacing chart metadata with prose as an analytical source of truth.

## Users or actors

- **Human analyst:** generates charts, inspects evidence, reviews findings, and
  controls the report's analytical scope.
- **Report author:** edits and orders reviewed material, previews the document,
  and exports a portable report package.
- **Analytical result author:** defines a stable typed result and may register a
  deterministic finding provider for that result type.
- **Recipe author:** declares which analytical result identities a chart
  visualizes and supplies presentation only; the recipe does not own report
  semantics.
- **Synthesis catalog:** applies a bounded set of named, versioned motorsport
  conclusion rules to compatible reportable findings.
- **Report renderer:** renders reviewed report state without recalculating
  analysis or inventing content.
- **LLM agent:** inspects structured findings, conclusions, report structure,
  and evidence through bounded contracts, but is not the analytical authority.

## Terminology and ownership

- **Analytical result:** A typed, versioned calculation outcome that exists
  independently of any renderer or chart instance and has a stable result ID
  and result fingerprint.
- **Result report assessment:** The finding-generation outcome for one unique
  analytical result. It records `report_disposition`, reasons, and zero or more
  finding IDs.
- **Report disposition:** A reporting classification, separate from analytical
  availability, with exactly one of `reportable`, `context_only`,
  `not_reportable`, `unsupported`, or `unavailable`. `Reportable` describes
  editorial relevance and does not assert statistical significance.
- **Finding:** A typed candidate statement produced from a unique analytical
  result whose report disposition is `reportable`.
- **Conclusion:** A reviewable finding produced by a versioned synthesis rule
  from two or more compatible supporting findings.
- **Comparison basis:** The subjects, session, interval, reference direction,
  measurement category, units, filters, and analytical method needed to
  interpret a finding.
- **Result fingerprint:** A deterministic digest of the typed analytical
  result's semantic inputs and output, independent of chart presentation.
- **Evidence fingerprint:** A deterministic digest of the result fingerprint,
  finding-provider or synthesis-rule version, and other bounded support for a
  finding or conclusion.
- **Report plan:** The durable ordered section and item structure, inclusion
  choices, and report target saved with the Analysis.
- **Current:** Derived state whose recorded input fingerprint still matches its
  current dependencies.
- **Stale:** Derived state whose dependencies have changed since it was
  produced or reviewed.

Analytical result types own finding-generation semantics. Chart recipes declare
which results they visualize and contribute optional evidence references only.
Named synthesis rules own bounded combinations of already-produced reportable
findings. The report plan owns structure and inclusion. Review owns editorial
disposition for publishable claims. The Markdown renderer owns presentation
only and must not calculate reportability or perform analytical calculations.

## Deterministic synthesis model

The pipeline is:

```text
typed analytical results
  -> deduplicate by result fingerprint
  -> result-type-owned report assessment
  -> zero or more reportable findings
  -> named versioned motorsport synthesis rules
  -> ordered report plan
  -> review of included publishable claims
  -> optional chart evidence
  -> Markdown draft
  -> exported package
```

A finding provider is registered against a typed analytical result type. It
consumes one deduplicated result identity, its typed value, target-session
provenance, and its bounded analytical qualifications. It does not consume
rendered pixels, depend on a chart instance, or independently recompute the
analysis from raw session data. It returns one result report assessment with
exactly one `report_disposition` and zero or more findings. Only
`reportable` produces one or more publishable findings; `context_only`,
`not_reportable`, `unsupported`, and `unavailable` are valid terminal
accounting outcomes and do not require manufactured prose.

Charts reference the analytical result IDs and fingerprints they visualize. A
finding may link to zero, one, or several chart artifacts; one chart may support
several findings or none. Charts backed by the same result fingerprint share
the same assessment and findings. Chart presentation changes do not duplicate
or invalidate a finding unless the underlying result fingerprint changes.

Each named synthesis rule declares its fixed motorsport question, required
finding kinds, subject matching, session and interval compatibility, accepted
measurement categories, version, output section, confidence policy, and
required limitations. Rules are implemented as an explicit catalog rather than
an arbitrary rule graph or user-composable framework. A rule that cannot
establish compatibility emits no positive conclusion. Material missing or
incompatible evidence remains inspectable through result assessments and may be
summarized in Limitations and Evidence without manufacturing a claim.

Conclusion confidence cannot exceed the weakest supporting finding. Partial
interval overlap, provisional quality, unequal samples, fallback bases,
coverage gaps, or material confounders must retain or lower confidence according
to a versioned policy. Rules may describe observed concurrence, divergence, or
absence of a measured change, but must not transform observational agreement
into a causal claim.

The first implementation includes only this baseline synthesis catalog:

- `pace-vs-direct-gap-v1`: state whether a supported representative-pace
  advantage coincided with, diverged from, or did not coincide with an observed
  improvement in a compatible direct-gap interval.
- `pace-evolution-comparison-v1`: compare supported observed pace-evolution
  slopes for the same compatible basis and interval without assuming that
  either driver must be losing pace or attributing the difference to tyre
  degradation causally.
- `pit-cycle-vs-race-state-v1`: connect a measured pit-cycle change with
  compatible direct-gap or rejoin evidence without declaring strategic intent
  or undercut/overcut success.
- `pace-vs-position-change-v1`: state when supported race-position change and
  representative-pace evidence agree or diverge over compatible scope.

Single-result statements such as a pace advantage or an unsupported compound
comparison belong to result-type finding providers, not this synthesis catalog.
Adding another synthesis rule requires a spec amendment after approval.

No rule is required to force a conclusion. Unavailable or incompatible
comparisons remain accounted for and inspectable without requiring report prose.

## Default report structure

The initial report template contains these stable section kinds:

1. Executive Summary
2. Strategy and Race Evolution
3. Pace and Tyre Performance
4. Pit Cycles and Key Comparisons
5. Limitations and Evidence

Sections with no included publishable items may be omitted. Non-publishable
assessments remain inspectable through Limitations and Evidence when included by
the author. Material limitations attached to an included claim must remain
visible beside that claim or in Limitations and Evidence. The default template is
versioned. Users may change inclusion and order without changing the meaning of
the underlying findings.

## Functional requirements

### REQ-001: Analytical-result-owned finding generation

- **Statement:** Finding generation must be registered against typed
  analytical result types and must not be owned by chart recipes, renderers, or
  chart instances.
- **Rationale:** A chart is one presentation of a result; tying semantics to the
  chart duplicates findings across visualizations and makes presentation choices
  affect report meaning.
- **Acceptance criteria:** Every provider declares a supported analytical result
  type and provider version; input includes result ID, result fingerprint,
  typed result value, and analytical provenance without requiring a chart;
  recipe/renderer identity is not used to select report semantics; recipes may
  declare result references only; provider failure is isolated by result.
- **Verification method:** Result-provider registry, no-chart, recipe-independence,
  and failure-isolation tests.
- **Evidence location:** To be filled during implementation.

### REQ-002: Complete result accounting without forced prose

- **Statement:** Every eligible analytical result must receive one result report
  assessment with exactly one `report_disposition`, while providers may produce
  zero or more findings.
- **Rationale:** Complete accounting prevents silent omissions, but context or
  low-reportability evidence should not be manufactured into narrative.
- **Acceptance criteria:** `report_disposition` accepts exactly `reportable`,
  `context_only`, `not_reportable`, `unsupported`, or `unavailable` and remains
  separate from analytical availability; `reportable` produces one or more
  publishable findings; the other four are valid terminal outcomes with reasons
  and zero findings; all built-in analytical result types used by the seven
  SPEC-008 templates and existing built-in analysis receive an assessment or an
  explicit unsupported assessment.
- **Verification method:** Provider coverage, enum validation, zero-finding,
  and Bahrain accounting tests.
- **Evidence location:** To be filled during implementation.

### REQ-003: Analytical result as semantic source of truth

- **Statement:** Findings must derive from the exact typed analytical result and
  must reference its result ID and result fingerprint.
- **Rationale:** Recomputing analysis for prose or deriving semantics from a
  visualization can make the report disagree with the analytical result.
- **Acceptance criteria:** Finding metrics, result kind, measurement category,
  sign convention, basis, availability, quality, and limitations match the
  typed result; providers do not inspect chart pixels or independently
  recompute analysis from raw laps or telemetry; malformed or unsupported
  result versions produce `unsupported`; analytically unavailable results
  produce `unavailable`; neither state is converted into a guessed claim.
- **Verification method:** Typed-result parity, mutation, unsupported-version,
  and unavailable-result tests.
- **Evidence location:** To be filled during implementation.

### REQ-004: Result deduplication and finding identity

- **Statement:** Equivalent analytical results must be deduplicated before
  synthesis, and every assessment, finding, and conclusion must have stable
  identity and deterministic fingerprints.
- **Rationale:** Multiple charts backed by one result must not produce duplicate
  findings, and review can be preserved safely only when evidence is unchanged.
- **Acceptance criteria:** Results with the same result fingerprint share one
  assessment and finding set even when referenced by several charts; distinct
  scoped results remain distinct; the result fingerprint is the semantic-
  equality and deduplication key; result ID is only the durable identity of a
  stored analytical result; finding ID is derived deterministically from the
  canonical result fingerprint, finding kind, and provider version; assessment
  identity uses the canonical result fingerprint and provider version;
  conclusion identity/fingerprint uses rule version and the canonical
  fingerprints of deduplicated supporting findings; no chart, recipe, renderer,
  artifact, or stored result ID participates in semantic deduplication or
  finding identity; presentation-only changes do not alter result/finding
  fingerprints; changed result semantics do.
- **Verification method:** Multi-chart deduplication, distinct-scope,
  determinism, and change-detection tests.
- **Evidence location:** To be filled during implementation.

### REQ-005: Provider-owned reportability and qualification

- **Statement:** The result-type finding provider must determine report
  disposition and, for reportable results, produce fully qualified findings.
- **Rationale:** Professional analysis must communicate how far the evidence
  supports each statement, while renderers must not decide what is important.
- **Acceptance criteria:** Each provider version defines inspectable
  result-type-specific reportability criteria and disposition reasons using
  explicit domain conditions such as analytical availability, accepted quality
  grade, minimum sample requirements, comparison validity, and a versioned
  reportability threshold where applicable; the criteria must not be an opaque
  importance score; provider discovery or inspection exposes the applicable
  criteria and thresholds; representative-pace provider tests cover
  availability, accepted quality, minimum samples, absolute-delta threshold,
  and the resulting `reportable`, `context_only`, or `not_reportable`
  disposition; the report renderer cannot promote `context_only`,
  `not_reportable`, `unsupported`, or `unavailable` assessments into findings;
  reportable findings include subjects, session, interval or
  scope, method/result kind, units/sign direction, confidence and basis,
  comparison basis, metrics, and material limitations; unavailable assessments
  include typed reasons and a safe next action when known.
- **Verification method:** Provider threshold fixtures, model/serialization
  tests, and renderer non-promotion tests.
- **Evidence location:** To be filled during implementation.

### REQ-006: Named deterministic motorsport conclusions

- **Statement:** The system must generate conclusions only through a small
  explicit catalog of named, versioned motorsport synthesis rules over
  deduplicated reportable findings.
- **Rationale:** Useful retrospective conclusions need traceable domain logic
  without creating an arbitrary expert-system framework.
- **Acceptance criteria:** Each conclusion records rule ID/version and all
  supporting finding IDs; the catalog is code-owned, enumerated, and limited to
  the approved baseline motorsport questions in this spec; no generic
  user-composable rule graph is introduced; the same deduplicated input set
  produces the same result; each rule validates subjects, session, interval,
  measurement categories, and method compatibility; confidence does not exceed
  the weakest support and includes compatibility penalties; unsupported causal
  wording is prohibited; missing support yields no positive conclusion.
- **Verification method:** Named rule truth-table tests, catalog enumeration,
  determinism tests, and manual analytical review.
- **Evidence location:** To be filled during implementation.

### REQ-007: Structured report plan

- **Statement:** The Analysis must persist a versioned report plan containing a
  single target race session, ordered sections, and ordered report items.
- **Rationale:** Report structure must be durable, inspectable, and independent
  from Markdown rendering.
- **Acceptance criteria:** The report plan records template version, target
  session ID, section IDs/kinds/titles/order/inclusion, and item IDs/kinds/order/
  inclusion; publishable findings, conclusions, optional chart embeds,
  limitations, and inspectable result assessments are representable; a
  deterministic default plan can be regenerated;
  one report plan cannot silently combine multiple sessions.
- **Verification method:** Model, persistence, migration, and round-trip tests.
- **Evidence location:** To be filled during implementation.

### REQ-008: Inclusion and ordering controls

- **Statement:** Users must be able to include, exclude, and reorder report
  sections and eligible items without editing raw JSON.
- **Rationale:** Professional reports require editorial control over emphasis
  and narrative sequence.
- **Acceptance criteria:** Review supports section and item inclusion plus
  deterministic move-up/move-down ordering; chart embeds can be included or
  excluded independently from their findings; removing an item from the report
  does not delete its evidence or review history; mandatory material limitations
  cannot be silently removed from an included claim; reset restores the
  versioned default plan after confirmation.
- **Verification method:** API, frontend component, keyboard, persistence, and
  browser tests.
- **Evidence location:** To be filled during implementation.

### REQ-009: Publishable-claim review

- **Statement:** Only findings and conclusions included as publishable report
  claims must require accepted, edited, rejected, or unreviewed editorial state.
- **Rationale:** Accountable publication review is necessary, but context
  evidence and non-publishable assessments should not create approval work.
- **Acceptance criteria:** Included publishable claims require current review
  before a current export; excluded findings and `context_only`,
  `not_reportable`, `unsupported`, or `unavailable` assessments remain
  inspectable without review tasks; edited text preserves generated text and
  cannot edit structured metrics, disposition, or evidence; material
  limitations attached to an included claim remain mandatory; refresh preserves
  a decision only when its evidence fingerprint is unchanged; changed evidence
  retains prior review for comparison but requires re-review if included.
- **Verification method:** State-transition, persistence, refresh, and UI tests.
- **Evidence location:** To be filled during implementation.

### REQ-010: Evidence navigation

- **Statement:** Review must provide safe clickable navigation from each
  finding or conclusion to its analytical result and any supporting chart and
  metadata artifacts.
- **Rationale:** Reviewers must be able to verify a statement without manually
  locating package paths.
- **Acceptance criteria:** A finding opens its typed result details and zero,
  one, or several linked chart/metadata artifacts; a conclusion exposes all
  supporting findings, results, and optional artifacts; one chart may appear as
  evidence for several findings or none; links resolve by stable identity
  through package-safe APIs; absence of optional chart evidence is not an
  integrity error; missing referenced assets are; raw filesystem paths are not
  executable browser links.
- **Verification method:** API path-safety tests and desktop/mobile browser
  checks.
- **Evidence location:** To be filled during implementation.

### REQ-011: Embedded portable Markdown

- **Statement:** The Markdown renderer must render the reviewed report plan with
  included charts embedded at their configured positions using package-relative
  paths.
- **Rationale:** A report should read as a document, not as a file inventory.
- **Acceptance criteria:** Markdown contains ordered report sections, reviewed
  publication text, relative image syntax with meaningful alt text, and
  clickable relative metadata links; rejected, excluded, stale-unreviewed, and
  superseded items are omitted; chart images are not duplicated in a separate
  path-list section unless Limitations and Evidence is included; raw and rendered
  preview use the same Markdown source; the package remains relocatable.
- **Verification method:** Golden Markdown, package relocation, rendered preview,
  accessibility, and browser tests.
- **Evidence location:** To be filled during implementation.

### REQ-012: Layered freshness state

- **Statement:** The system must track evidence, review, draft, and export
  freshness separately and expose the dependency that made each layer stale.
- **Rationale:** One `review_stale` flag cannot explain whether analysis,
  editorial approval, document rendering, or the exported snapshot is out of
  date.
- **Acceptance criteria:** Changed analytical result fingerprints stale affected
  evidence; presentation-only chart changes do not stale findings unless an
  included chart embed or link changed; changed evidence invalidates affected
  included-claim review and stales the draft and export;
  review, inclusion, or ordering changes stale the draft and export without
  staling evidence; draft regeneration makes the draft current but leaves the
  prior export stale; export records fingerprints for all included layers;
  unrelated chart changes do not invalidate unaffected findings.
- **Verification method:** State-machine and dependency-isolation tests.
- **Evidence location:** To be filled during implementation.

### REQ-013: Refresh and export safety

- **Statement:** Refresh and Export must never silently present stale or
  invalidated report content as current.
- **Rationale:** Stale reviewed prose can become analytically false after its
  analytical result changes.
- **Acceptance criteria:** Review refresh shows preserved, invalidated, new, and
  removed items before old reviewed content is replaced; automatic draft
  regeneration after review or plan changes is allowed only from current
  evidence and visibly records its state; final current export is unavailable
  while included evidence, required review, or draft is stale; the UI states
  the exact required next action; an existing exported package remains
  inspectable and visibly marked as an older snapshot.
- **Verification method:** API/UI lifecycle tests and manual stale-state review.
- **Evidence location:** To be filled during implementation.

### REQ-014: Report preview and package integrity

- **Statement:** Export Preview must present the same structured report,
  embedded charts, raw Markdown, and integrity state that will be exported.
- **Rationale:** The reviewer needs one trustworthy pre-export representation.
- **Acceptance criteria:** Preview includes report freshness and target session,
  rendered and raw Markdown, included charts, result-assessment disposition
  counts, finding/conclusion counts, required-review completeness, and integrity
  findings; missing referenced images, metadata, results, findings, review
  records, report-plan references, or fingerprint mismatches are reported;
  unreferenced optional chart evidence is not treated as missing; preview
  rendering does not mutate review or report state.
- **Verification method:** Package reader, integrity, frontend, and browser
  tests.
- **Evidence location:** To be filled during implementation.

### REQ-015: Batch and existing package compatibility

- **Statement:** Existing batch generation and previously generated report
  packages must remain readable while new packages use the structured report
  contract.
- **Rationale:** SPEC-009 must not strand existing workflows or artifacts.
- **Acceptance criteria:** The current generate command still produces a valid
  portable package; legacy packages without a report plan open with a clear
  legacy state and their existing observations/draft; migration does not invent
  reviewed decisions; new package schema/version fields are explicit; existing
  observation review states can migrate when their stable identity and evidence
  are demonstrably unchanged.
- **Verification method:** Existing CLI/package tests plus legacy fixture and
  migration tests.
- **Evidence location:** To be filled during implementation.

### REQ-016: Canonical Bahrain report

- **Statement:** The completed feature must generate a human-reviewed canonical
  2023 Bahrain Race strategy report that exercises all seven SPEC-008 chart
  families.
- **Rationale:** Schema and unit correctness alone do not prove that the report
  is coherent or professionally useful.
- **Acceptance criteria:** Every unique analytical result behind the generated
  strategy charts has one assessment and disposition; context-only and
  not-reportable results do not produce filler; shared result fingerprints do
  not duplicate findings; the factual draft covers strategy sequence,
  representative pace, observed evolution, compound evidence, pit-cycle
  change, race-time/direct-gap evidence, and driver-battle outcome only where
  reportable and supported; named-rule conclusions cite their results,
  findings, and optional chart evidence; human review confirms that published
  claims are correct, selective, meaningful, non-causal, appropriately
  qualified, and coherently ordered.
- **Verification method:** End-to-end generation, artifact inspection, and
  recorded human acceptance review.
- **Evidence location:** To be filled during implementation.

## Non-functional requirements

### NFR-001: Deterministic and reproducible content

- **Statement:** Finding extraction, synthesis, default ordering, confidence,
  freshness fingerprints, and Markdown output must be deterministic for
  identical inputs and versions.
- **Rationale:** Reproducibility is required for trustworthy review and
  regression testing.
- **Acceptance criteria:** Repeated runs over identical analytical results produce
  byte-stable structured content and Markdown except documented timestamps;
  rule/provider/template versions are recorded; tests prove changed inputs
  invalidate only their dependent outputs.
- **Verification method:** Repeated-run hashes and determinism tests.
- **Evidence location:** To be filled during implementation.

### NFR-002: Analytical language safety

- **Statement:** Generated content must use language appropriate to its
  measurement category and strength of evidence.
- **Rationale:** Professional analysis depends on avoiding causal or controlled
  claims that observational evidence does not support.
- **Acceptance criteria:** A reviewed phrase policy distinguishes measured,
  derived, descriptive, provisional, and unavailable results; unequal or
  uncontrolled samples cannot produce effect language; observational agreement
  uses non-causal wording; automated phrase tests and human review cover
  positive, negative, neutral, partial, and unavailable cases.
- **Verification method:** Rule fixtures, prohibited-phrase tests, and human
  editorial review.
- **Evidence location:** To be filled during implementation.

### NFR-003: Bounded report generation

- **Statement:** Report synthesis and preview must remain responsive for a
  representative Analysis without unbounded findings or metadata payloads.
- **Rationale:** Per-result findings and multi-result combinations can grow
  combinatorially.
- **Acceptance criteria:** Providers declare bounded output; duplicate results
  are removed before synthesis; the named synthesis catalog does not enumerate
  unrestricted combinations; duplicate conclusions are deterministically
  suppressed; a 20-chart fixture with shared and distinct results plus up to
  100 findings records generation and preview performance with an agreed
  implementation-time target.
- **Verification method:** Benchmark, payload-size, and scale UI tests.
- **Evidence location:** To be filled during implementation.

### NFR-004: Stable extension boundary

- **Statement:** Result-type finding providers and named synthesis rules must use versioned typed
  interfaces independent of Matplotlib and frontend implementation details.
- **Rationale:** Analytical result authors and eligible plugins need a maintainable content extension
  point.
- **Acceptance criteria:** Core providers register by analytical result type
  without recipe, renderer, or UI-specific ownership; plugins may opt in by
  registering typed result providers while recipes only declare result
  references; invalid provider output is isolated and reported without breaking
  other findings; renderer and report-template changes do not require
  analytical result or finding recomputation.
- **Verification method:** Contract, plugin fixture, and isolation tests.
- **Evidence location:** To be filled during implementation.

## Security and privacy considerations

### SEC-001: Local evidence boundary

- **Statement:** Finding extraction, synthesis, review, preview, and export must
  operate locally over saved Analysis and package data.
- **Rationale:** The existing framework is local-first and report evidence may
  contain user-selected local data and paths.
- **Acceptance criteria:** No external service or network call is required;
  synthesis does not transmit chart metadata or report content; optional future
  external editorial assistance requires a separate approved spec.
- **Verification method:** Code inspection and network-isolation tests.
- **Evidence location:** To be filled during implementation.

### SEC-002: Safe Markdown and evidence links

- **Statement:** Generated and edited Markdown content plus evidence links must
  be rendered and resolved safely.
- **Rationale:** Edited text and plugin-provided labels are untrusted display
  data even in a local application.
- **Acceptance criteria:** Preview preserves the existing safe Markdown policy;
  raw HTML and unsafe URL schemes do not execute; package-relative asset
  resolution prevents root escape; alt text and labels are escaped; missing or
  invalid assets produce findings rather than arbitrary file access.
- **Verification method:** Security, path traversal, Markdown sanitization, and
  frontend tests.
- **Evidence location:** To be filled during implementation.

## Data model impact

### DATA-001: Analytical result assessment and finding model

- **Statement:** Add versioned models for analytical result identity, result
  report assessment, reportable findings, and conclusions.
- **Rationale:** The current observation model cannot represent result ownership,
  deduplication, report disposition, zero-finding outcomes, comparison basis,
  synthesis provenance, or evidence freshness.
- **Acceptance criteria:** A result reference includes result ID, result type,
  schema/method version, result fingerprint, target-session provenance,
  availability, and bounded typed payload reference; an assessment includes
  result ID/fingerprint, provider ID/version, exactly one `report_disposition`,
  disposition reasons, and zero or more finding IDs; findings include finding
  ID, result ID/fingerprint, generated text, priority, section kind, confidence
  and basis, comparison basis, metrics, limitations, and evidence fingerprint;
  conclusions include rule ID/version and supporting finding/result IDs;
  unknown fields are rejected.
- **Verification method:** Pydantic/schema and serialization tests.
- **Evidence location:** To be filled during implementation.

### DATA-002: Evidence reference model

- **Statement:** Evidence references must identify the analytical result first
  and may additionally identify zero or more chart instances, artifacts,
  recipes, images, metadata files, source fields, and relevant metadata paths.
- **Rationale:** Charts are optional supporting artifacts and may have many-to-
  many relationships with findings; artifact ID and recipe ID are not semantic
  result identity.
- **Acceptance criteria:** Result references always resolve independently of a
  chart; optional chart references are package-relocatable and distinguish
  repeated recipe instances; one finding may reference several charts and one
  chart several findings; absence of a chart is valid; evidence supports
  conclusions without duplicating full analytical result payloads.
- **Verification method:** Model, resolution, relocation, and repeated-recipe
  tests.
- **Evidence location:** To be filled during implementation.

### DATA-003: Report plan model

- **Statement:** Add a versioned report-plan model persisted with the Analysis
  and materialized in the package.
- **Rationale:** Ordering and inclusion must survive reload and be inspectable
  independently of rendered Markdown.
- **Acceptance criteria:** The model represents target session, template
  version, ordered sections, ordered typed items, inclusion, chart placement,
  plan fingerprint, created/updated provenance, and current/stale state;
  references to removed findings or artifacts produce integrity findings.
- **Verification method:** Round-trip, migration, and integrity tests.
- **Evidence location:** To be filled during implementation.

### DATA-004: Review and freshness model

- **Statement:** Review records must separate editorial disposition from
  evidence validity and record the reviewed fingerprint.
- **Rationale:** An accepted statement can become stale without losing the
  historical fact that it was previously reviewed.
- **Acceptance criteria:** Review records include item ID, status, edited text,
  reviewed evidence fingerprint, reviewed timestamp, and validity/currentness;
  report state records evidence, review, draft, and export fingerprints and
  stale reasons; removed items remain recoverable as bounded review history.
- **Verification method:** State transition, persistence, and migration tests.
- **Evidence location:** To be filled during implementation.

### DATA-005: Report package schema

- **Statement:** The manifest must explicitly reference analytical result
  assessments, structured findings, report plan, review data, Markdown draft,
  and their schema versions and fingerprints.
- **Rationale:** Package readers and integrity checks need an authoritative map
  of the report content layer.
- **Acceptance criteria:** New packages contain all referenced files and
  package-relative paths; manifest validation detects missing or mismatched
  report assets; the package records the target session and source Analysis
  provenance; legacy manifest parsing remains supported.
- **Verification method:** Package structure, reader, relocation, and legacy
  tests.
- **Evidence location:** To be filled during implementation.

## API impact

### API-001: Analytical-result finding-provider contract

- **Statement:** Core analytical result types and eligible plugins must be able
  to register a versioned finding provider by result type through a typed
  backend contract; chart recipes must not register report semantics.
- **Rationale:** Finding logic belongs to analytical results and must remain
  independent of visualization and report UI.
- **Acceptance criteria:** Discovery exposes supported result type, provider ID,
  and provider version; provider input is one bounded typed analytical result;
  output is one validated assessment plus zero or more findings; recipes may
  declare which result IDs/fingerprints they visualize; an absent provider
  yields `unsupported` for that result rather than for a chart; provider
  failures are isolated.
- **Verification method:** Registry, plugin, validation, and failure-isolation
  tests.
- **Evidence location:** To be filled during implementation.

### API-002: Report synthesis and plan API

- **Statement:** Local APIs must support refreshing findings, synthesizing
  conclusions, reading/updating/resetting the report plan, and regenerating the
  draft.
- **Rationale:** Frontend and agent clients need one authoritative workflow.
- **Acceptance criteria:** Mutations validate item identity and freshness,
  return current layered state, reject incompatible or unknown references, and
  persist atomically; refresh returns added, preserved, invalidated, and removed
  item summaries; draft generation consumes current reviewed plan state only.
- **Verification method:** FastAPI, atomicity, concurrency-conflict, and error
  response tests.
- **Evidence location:** To be filled during implementation.

### API-003: Review API extension

- **Statement:** Review APIs must support included publishable findings and conclusions while
  preserving immutable generated evidence fields.
- **Rationale:** Existing observation review actions should extend rather than
  fragment into a competing workflow.
- **Acceptance criteria:** Accept/edit/reject/reset operate on included
  publishable item kinds; non-publishable assessments do not acquire review
  tasks; excluded findings remain inspectable without blocking readiness;
  edits change publication text only; requests include or validate the evidence
  fingerprint to prevent editing a stale revision; responses expose review
  validity and draft/export consequences.
- **Verification method:** API contract and optimistic-concurrency tests.
- **Evidence location:** To be filled during implementation.

### API-004: LLM-safe report inspection

- **Statement:** The LLM contract must expose bounded structured report state
  and evidence without granting authority to change analytical facts.
- **Rationale:** Agents need to explain and assist with reports while preserving
  deterministic analytical authority.
- **Acceptance criteria:** Inspection returns section/item order, publishable
  text, structured metrics, comparison basis, confidence, limitations,
  availability, review/freshness state, and evidence references; payloads are
  bounded; analytical metric/confidence mutation is rejected; no LLM call is
  required for baseline synthesis.
- **Verification method:** Contract, payload-bound, and mutation-rejection tests.
- **Evidence location:** To be filled during implementation.

## UI or UX impact

### UX-001: Structured Review workspace

- **Statement:** The existing Workbench Review item must present report content
  grouped by ordered report section rather than as one flat observation list.
- **Rationale:** Review should reflect the document being authored.
- **Acceptance criteria:** Main sections emphasize included publishable findings
  and conclusions; result assessments and optional context evidence are
  available through secondary inspection grouped by report disposition;
  confidence, comparison basis, limitations, evidence, and required review are
  visible for included claims; controls support review, inclusion, and ordering
  without raw JSON; desktop and mobile layouts remain usable; the UI uses
  concise labels rather than instructional copy.
- **Verification method:** Component, accessibility, responsive, and browser
  tests.
- **Evidence location:** To be filled during implementation.

### UX-002: Evidence inspection

- **Statement:** A reviewer must be able to inspect all evidence for a finding
  or conclusion without leaving the Workbench context.
- **Rationale:** Fast verification is essential to professional human review.
- **Acceptance criteria:** Selecting evidence opens the typed analytical result
  first and any optional chart preview or metadata detail surface; conclusions
  show supporting findings and results before artifacts; context-only and
  not-reportable assessments remain inspectable; missing referenced evidence
  is distinguished from no optional chart, analytical unavailability, and
  unsupported reporting; keyboard navigation and accessible names are provided.
- **Verification method:** Component, accessibility, and browser tests.
- **Evidence location:** To be filled during implementation.

### UX-003: Clear freshness and next action

- **Statement:** Review and Export must derive one primary operational report
  status and next action from the internal evidence, review, draft, and export
  freshness layers.
- **Rationale:** Users should not need to infer whether to regenerate charts,
  refresh evidence, review changes, regenerate the draft, or export again.
- **Acceptance criteria:** The primary status uses concise operational states
  such as `Report current`, `Evidence changed`, `Review required`, or
  `Regenerate draft` and presents exactly one recommended next action; detailed
  internal layer status, affected item counts, and causes remain available on
  inspection; actions are enabled only when prerequisites are met; an older
  export remains inspectable with its snapshot identity and stale badge.
- **Verification method:** State-matrix component and end-to-end browser tests.
- **Evidence location:** To be filled during implementation.

### UX-004: Report-oriented Export Preview

- **Statement:** Export Preview must default to the rendered structured report
  while retaining raw Markdown, charts, and integrity inspection.
- **Rationale:** The primary export question is whether the complete report is
  ready, not whether individual package files exist.
- **Acceptance criteria:** Preview preserves rendered/raw Markdown tabs, chart
  inspection, and integrity findings; embedded chart positions match raw
  Markdown; report target, review completeness, freshness, and package health
  are visible; unavailable material is visually distinct from errors.
- **Verification method:** Frontend, Markdown parity, and browser tests.
- **Evidence location:** To be filled during implementation.

## Configuration impact

- The durable Analysis schema gains a versioned report plan and layered report
  state. Existing analyses without those fields migrate to an explicit legacy
  or uninitialized report state.
- The report plan selects exactly one loaded Race session in this delivery. An
  Analysis with one eligible Race session may default to it; otherwise the user
  must select the target explicitly.
- Analytical-result provider, named synthesis-rule, phrase-policy, and
  report-template versions are recorded in generated state and packages.
- Core report defaults are code-owned versioned data. This spec does not add an
  unrestricted executable rule configuration format.

## Error handling

- Missing, invalid, or unsupported analytical result data produces an
  `unavailable` or `unsupported` result assessment; it does not manufacture a
  finding or abort unrelated providers.
- A finding-provider or synthesis-rule failure is isolated, recorded with its
  provider/rule identity, and prevents affected content from being considered
  current.
- Unknown, removed, or fingerprint-mismatched review targets return a conflict
  response and do not mutate newer content.
- Missing referenced chart images or metadata appear as package integrity
  findings and block a current export when the affected evidence is included;
  a result or finding with no optional chart reference is valid.
- Incompatible multi-result inputs produce no positive conclusion and record the
  incompatibility when it materially affects an expected report question.
- Markdown rendering failure leaves the previous draft/export inspectable and
  marks the new draft/export stale or failed.
- Partial writes must not replace a previously valid report plan, review file,
  draft, or exported manifest.

## Edge cases

- Multiple chart instances visualize the same result fingerprint.
- Multiple instances of one recipe visualize distinct results because their
  drivers, intervals, parameters, or analytical modes differ.
- One chart presentation changes while the shared result remains current.
- A chart is regenerated with identical analytical evidence but different
  presentation metadata.
- Generated wording changes while evidence remains identical.
- A reviewed finding remains supported after its only chart is removed because
  the analytical result still exists.
- A finding disappears because its analytical result changes disposition or is
  removed.
- A new finding appears after refresh and has no review record.
- Supporting findings use reversed focal/reference direction.
- Findings mention the same drivers but cover disjoint or partially overlapping
  intervals.
- One supporting finding is measured and another is derived or descriptive.
- A named synthesis rule receives findings referenced by duplicated result or
  chart paths.
- All positive findings in a section are rejected while a material limitation
  remains.
- A report includes a finding but excludes its chart, or includes a chart while
  excluding its finding.
- A report contains no publishable positive conclusions.
- A plugin analytical result has no finding provider or returns invalid output;
  its chart remains usable as an artifact.
- A legacy package lacks finding, report-plan, or freshness files.
- An Analysis contains no Race session, multiple Race sessions, or an unloaded
  target session.
- A package is moved to another directory before preview.
- Edited Markdown contains raw HTML, unsafe links, or image-like syntax.

## Acceptance criteria

SPEC-009 is satisfied when:

1. Every eligible analytical result is accounted for once by result fingerprint
   with exactly one approved `report_disposition` and zero or more findings.
2. Finding providers are registered by analytical result type; chart recipes
   own no report semantics and charts remain optional many-to-many evidence.
3. Multiple charts backed by one result cannot duplicate findings before
   synthesis.
4. A small named catalog of versioned deterministic motorsport rules generates
   only compatible, evidence-linked, non-causal conclusions.
5. Review operates over ordered report sections with inclusion, ordering,
   evidence navigation, confidence, comparison basis, limitations, and
   unavailable states while only included publishable claims require editorial
   review.
6. Review preservation and invalidation follow result/evidence fingerprints
   rather than prose, recipe ID, or chart identity alone.
7. Four freshness layers are preserved internally and drive one clear primary
   report status and next action.
8. Markdown embeds selected charts and metadata links at their report positions using
   portable package-relative paths.
9. Existing batch generation and legacy package preview remain supported.
10. Automated tests, package integrity checks, frontend checks, governance
   checks, and the canonical Bahrain end-to-end report review pass.
11. The delivered product is described and accepted as a defensible factual
    draft generator, not autonomous expert motorsport authorship.
12. Nelson Jeanrenaud explicitly approves this spec before implementation.

## Verification matrix

| Requirement ID | Acceptance criterion | Verification method | Test / command / manual check | Evidence location | PR reference |
| -------------- | -------------------- | ------------------- | ----------------------------- | ----------------- | ------------ |
| REQ-001 | Providers register by analytical result type, not recipe/chart | Automated | Registry/no-chart/independence tests | `tests/test_report_findings.py` | N/A (`chatbot`) |
| REQ-002 | Every result is assessed; non-reportable outcomes produce no filler | Automated/manual | Provider/disposition coverage; Bahrain inspection | `tests/test_report_findings.py`; canonical `assessments.json` | N/A (`chatbot`) |
| REQ-003 | Findings match typed analytical results | Automated | Result parity and unsupported-version tests | `tests/test_report_findings.py` | N/A (`chatbot`) |
| REQ-004 | Shared result fingerprints deduplicate findings | Automated | Multi-chart deduplication/determinism tests | `tests/test_report_findings.py` | N/A (`chatbot`) |
| REQ-005 | Providers own explicit reportability and qualification | Automated/manual | Threshold/renderer non-promotion tests | `tests/test_report_findings.py` | N/A (`chatbot`) |
| REQ-006 | Named motorsport conclusions are bounded and compatible | Automated/manual | Catalog truth-table tests; analyst review | `tests/test_report_findings.py`; accepted canonical draft | N/A (`chatbot`) |
| REQ-007 | Report plan persists one ordered target-session document | Automated | Round-trip and migration tests | `tests/test_report_findings.py`; `tests/test_analysis_workspace.py` | N/A (`chatbot`) |
| REQ-008 | Inclusion/order controls persist and preserve evidence | Automated/manual | API/UI/browser tests | workspace/API tests; frontend typecheck/build | N/A (`chatbot`) |
| REQ-009 | Only included publishable claims require current review | Automated | Review state-machine tests | `tests/test_report_findings.py`; `tests/test_analysis_workspace.py` | N/A (`chatbot`) |
| REQ-010 | Findings navigate safely to all evidence | Automated/manual | Path-safety and browser tests | report/package tests; healthy canonical package | N/A (`chatbot`) |
| REQ-011 | Markdown is structured, embedded, linked, and relocatable | Automated/manual | Golden/relocation/render tests | `tests/test_report_findings.py`; canonical `draft.md` | N/A (`chatbot`) |
| REQ-012 | Four freshness layers invalidate only dependents | Automated | State-machine/isolation tests | `tests/test_analysis_workspace.py` | N/A (`chatbot`) |
| REQ-013 | Stale content cannot appear as a current export | Automated/manual | Lifecycle and stale UI tests | workspace lifecycle tests; frontend typecheck/build | N/A (`chatbot`) |
| REQ-014 | Preview matches export and reports content integrity | Automated/manual | Reader/UI/browser tests | preview/workspace tests; canonical health check | N/A (`chatbot`) |
| REQ-015 | Batch and legacy packages remain usable | Automated | Existing suite plus legacy fixtures | full 144-test regression suite | N/A (`chatbot`) |
| REQ-016 | Bahrain result accounting is complete and factual draft is selective | Manual/end-to-end | Canonical report review | accepted package `exports/e5a97c5adb69c619` | N/A (`chatbot`) |
| NFR-001 | Content is reproducible for identical inputs | Automated | Repeated-run hashes | `tests/test_report_findings.py` | N/A (`chatbot`) |
| NFR-002 | Language matches analytical evidence category | Automated/manual | Phrase fixtures and editorial review | `tests/test_report_findings.py`; accepted canonical draft | N/A (`chatbot`) |
| NFR-003 | Report generation remains bounded | Benchmark | 20-chart/100-finding benchmark | fixed four-rule catalog inspection; full suite | N/A (`chatbot`) |
| NFR-004 | Provider/rule interfaces remain renderer/UI independent | Automated | Contract and plugin tests | `tests/test_report_findings.py` | N/A (`chatbot`) |
| SEC-001 | Report flow remains local | Inspection/automated | Network-isolation check | implementation inspection; full suite | N/A (`chatbot`) |
| SEC-002 | Markdown and asset links remain safe | Automated | Sanitization/path traversal tests | report/preview safety tests | N/A (`chatbot`) |
| DATA-001 | Result assessments and findings preserve ownership/disposition | Automated | Model/schema tests | `tests/test_report_findings.py` | N/A (`chatbot`) |
| DATA-002 | Evidence is result-first with optional many-to-many charts | Automated | Resolution/relocation tests | deduplication and package tests | N/A (`chatbot`) |
| DATA-003 | Report plan round-trips and validates references | Automated | Persistence/integrity tests | report/workspace tests | N/A (`chatbot`) |
| DATA-004 | Review history and freshness are separate | Automated | State/persistence tests | report/workspace lifecycle tests | N/A (`chatbot`) |
| DATA-005 | Manifest references complete versioned report data | Automated | Package/legacy tests | package/preview tests; healthy canonical package | N/A (`chatbot`) |
| API-001 | Result-type providers register, validate, and fail independently | Automated | Registry/plugin tests | `tests/test_report_findings.py` | N/A (`chatbot`) |
| API-002 | Report refresh/plan/draft APIs are atomic and typed | Automated | FastAPI tests | API and workspace regression tests | N/A (`chatbot`) |
| API-003 | Review rejects stale revisions and protects evidence | Automated | API concurrency tests | API and workspace lifecycle tests | N/A (`chatbot`) |
| API-004 | LLM inspection is bounded and read-only for facts | Automated | Contract tests | LLM contract regression tests | N/A (`chatbot`) |
| UX-001 | Review is structured and operable at desktop/mobile sizes | Automated/manual | Component/accessibility/browser tests | frontend typecheck/build; Workbench implementation review | N/A (`chatbot`) |
| UX-002 | All supporting evidence is inspectable in context | Automated/manual | Accessibility/browser tests | frontend typecheck/build; accepted canonical package | N/A (`chatbot`) |
| UX-003 | Freshness and next actions are unambiguous | Automated/manual | State-matrix/browser tests | workspace tests; frontend typecheck/build | N/A (`chatbot`) |
| UX-004 | Export Preview is report-oriented and Markdown-consistent | Automated/manual | Preview parity/browser tests | preview tests; frontend typecheck/build | N/A (`chatbot`) |

## Test plan

### Unit tests

- Analytical result, assessment, disposition, finding, and fingerprint model
  validation and serialization.
- One provider fixture per built-in analytical result type covering reportable,
  context-only, not-reportable, unsupported, analytically unavailable, partial,
  and provisional cases as applicable.
- Multiple chart instances sharing one result and distinct results sharing one
  recipe.
- Named motorsport rule truth tables for positive, negative, neutral, incompatible,
  partial-overlap, unavailable, and duplicated-support cases.
- Confidence propagation and limitation aggregation.
- Phrase-policy tests preventing causal or controlled-effect language where the
  measurement category does not support it.
- Report-plan ordering, inclusion, reset, and reference validation.
- Layered freshness state transitions and dependency isolation.
- Markdown structure, escaping, relative paths, alt text, and stable output.

### Integration and API tests

- Analytical result generation through assessment, deduplication, findings,
  named synthesis, review, draft, preview, and export.
- Review refresh preserving unchanged decisions and invalidating changed
  evidence without overwriting history.
- Optimistic fingerprint conflicts for concurrent/stale edits.
- Partial provider/rule failure isolation and atomic persistence.
- Existing batch-generate compatibility and legacy package opening/migration.
- Package relocation and integrity failures for every new referenced file.
- LLM inspection payload bounds and rejection of analytical-fact mutation.

### Frontend and browser tests

- Structured sections, publishable claims, disposition inspection, optional chart embeds, and unavailable
  states at desktop and 390x844 mobile viewport sizes.
- Accept, edit, reject, reset, include/exclude, move, and default-plan reset.
- Keyboard navigation, focus behavior, accessible names, and evidence opening.
- Evidence/review/draft/export freshness combinations and next actions.
- Rendered/raw Markdown parity, embedded images, metadata links, and integrity
  findings.
- No unexpected browser console errors during the full report workflow.

### Canonical analytical review

- Generate the populated cached 2023 Bahrain Race analysis with all seven
  SPEC-008 chart families.
- Account for every unique analytical result and verify its disposition against
  the typed result independently of its chart presentation.
- Confirm that shared results do not duplicate findings and that context-only or
  not-reportable results do not produce filler.
- Review every named-rule conclusion against all supporting results, findings, and
  compatibility information.
- Confirm that the report covers pace advantage, observed evolution, compound
  evidence, pit-cycle change, race-time/direct-gap evidence, and driver-battle
  outcome where supported.
- Confirm that no statement implies intent or causality beyond the evidence.
- Confirm that the final ordering reads as a selective, coherent, defensible
  factual draft suitable for human editorial completion.
- Preserve the reviewed package/report as implementation evidence.

### Expected completion commands

```powershell
python -m unittest discover -s tests -p "test_*.py"
python scripts/validate_governance.py
python scripts/validate_specs.py
python scripts/validate_drift.py
cd frontend
npm run typecheck
npm run build
```

Any dedicated report benchmark, Markdown/package validation command, and
canonical Bahrain generation command must be added to this list during the
implementation plan once their exact interfaces exist.

## Rollback plan

- Keep new report files and manifest fields versioned so readers can fall back
  to legacy observations and `draft.md` handling.
- Preserve existing observation/review files during migration until the new
  report package has been written and validated atomically.
- If structured synthesis must be disabled, retain result assessments and
  reportable result-owned findings rather than falling back to chart-owned or
  unsupported generic conclusions.
- If a provider or rule version is withdrawn, mark its dependent content stale
  and require regeneration; do not reinterpret previously reviewed evidence
  silently.
- Reverting SPEC-009 code must not delete Analysis directories or previously
  exported packages. Newer package fields may be ignored by an older compatible
  reader only when legacy fields remain valid.

## Open questions

- None. Multi-session reporting and stale-snapshot export actions are deferred
  outside this spec.

## Human decisions required

- [x] **Draft authorization:** On 2026-08-10, Nelson Jeanrenaud authorized
      drafting SPEC-009 after reviewing the deterministic rule approach and its
      professional-analysis safeguards.
- [x] **Architecture approval:** On 2026-08-10, Nelson approved analytical-result-
      owned findings; exact five-state `report_disposition`; zero-or-more
      findings per result; result-fingerprint deduplication before synthesis;
      chart artifacts as optional many-to-many evidence; provider-owned
      reportability; named bounded motorsport rules; review only for included
      publishable claims; internal four-layer freshness with one operational UI
      status; and the defensible-factual-draft product promise.
- [x] **Scope approval:** Built-in analytical result types require complete
      assessment coverage, while third-party result-provider support is opt-in.
- [x] **Session scope:** One selected Race session per report is approved for
      this delivery. Weekend, season, and other multi-session synthesis require
      a separate analytical contract.
- [x] **Synthesis authority:** Deterministic named motorsport rules are the
      complete baseline synthesis mechanism; optional LLM editorial assistance
      is deferred.
- [x] **Export policy:** A new current export is blocked while included
      evidence, required review, or draft state is stale. The previous package
      remains an explicitly older inspectable snapshot. No stale-export action
      is added to the normal workflow.
- [x] **Spec approval:** Nelson Jeanrenaud approved SPEC-009 for implementation
      on 2026-08-10 through the supplied final review, conditional on the
      authority, reportability, provider-criteria, identity, terminology,
      session-scope, and export-policy corrections now incorporated.

## Conflict check

- SPEC-001 requires structured observations, evidence links, review, and a
  portable Markdown package. SPEC-009 deepens those models and preserves their
  non-causal and portable-package intent.
- SPEC-004 requires Review/Export to operate on current Analysis state and says
  chart regeneration must not automatically overwrite reviewed observation
  state. SPEC-009 makes preservation conditional on an unchanged evidence
  fingerprint and retains invalidated history; it does not silently overwrite
  reviewed state.
- SPEC-004 supports Analyses with multiple sessions. SPEC-009 limits one report
  plan to one selected Race session in its first delivery; it does not limit the
  Analysis itself or remove other sessions.
- SPEC-008 keeps strategy analytics and metadata authoritative and explicitly
  defers natural-language strategy observations and synthesis. SPEC-009 treats
  its typed analytical results, not its seven chart recipes, as semantic sources
  and consumes them without changing calculations or visual contracts.
- SPEC-002 and SPEC-003 preview and Markdown-safety behavior remains in force;
  SPEC-009 extends the existing Workbench Review/Export surfaces rather than
  introducing a competing page model.
- No blocking authoritative conflict is currently identified;
  `conflicts_with` remains empty. The policy decisions above were resolved
  before approval.

## Traceability table

| Requirement ID | Design / component | Implementation (file/function) | Test | Status |
| -------------- | ------------------ | ------------------------------ | ---- | ------ |
| REQ-001 | Result-type provider registry | `analysis/findings.py` provider registry | `test_report_findings.py` registry/independence tests | Implemented locally |
| REQ-002 | Result assessment/disposition coverage | `analysis/findings.py` assessment models/providers | disposition and seven-template lifecycle tests | Implemented locally |
| REQ-003 | Typed-result semantic boundary | `materialize_results`, typed providers | parity/version/unavailable tests | Implemented locally |
| REQ-004 | Result deduplication and fingerprints | canonical hashing and identity helpers | deduplication/determinism/change tests | Implemented locally |
| REQ-005 | Provider-owned reportability/qualification | provider descriptors and explicit thresholds | threshold/sample/quality tests | Implemented locally |
| REQ-006 | Named motorsport synthesis catalog | four explicit synthesis functions | named-rule and confidence tests | Implemented locally |
| REQ-007 | Report plan | report plan models and workspace persistence | round-trip through package/workspace tests | Implemented locally |
| REQ-008 | Inclusion/order editing | plan API and Workbench controls | frontend typecheck/build; plan validation | Implemented locally |
| REQ-009 | Included-claim editorial review | review model/state machine | required-review and export-gate tests | Implemented locally |
| REQ-010 | Evidence navigation | chart evidence links and package asset API | Markdown/link/path tests | Implemented locally |
| REQ-011 | Structured Markdown renderer | `render_structured_markdown` | embed/metadata/package tests | Implemented locally |
| REQ-012 | Layered freshness state | `ReportFreshness` and workspace transitions | lifecycle/export tests | Implemented locally |
| REQ-013 | Refresh/export gate | workspace refresh/regenerate/export methods | seven-template blocking-export test | Implemented locally |
| REQ-014 | Report preview/integrity | manifest and preview reader extensions | preview and workspace package tests | Implemented locally |
| REQ-015 | Compatibility/migration | parallel legacy files and optional manifest fields | full 138-test regression suite | Implemented locally |
| REQ-016 | Canonical Bahrain report | seven-template workspace lifecycle | accepted package under `analyses/spec-009-bahrain-acceptance/exports/e5a97c5adb69c619` | Implemented |
| NFR-001 | Deterministic content | canonical serialization and stable ordering | repeated fingerprint tests | Implemented locally |
| NFR-002 | Analytical phrase policy | non-causal provider/rule text | non-causal synthesis assertions | Implemented locally |
| NFR-003 | Bounded synthesis | fixed four-rule catalog | catalog inspection tests | Implemented locally |
| NFR-004 | Extension contract | result-type registration API | descriptor/registration contract tests | Implemented locally |
| SEC-001 | Local execution | workspace/package-only pipeline | code inspection and full suite | Implemented locally |
| SEC-002 | Safe Markdown/assets | `_safe_markdown_path`, preview containment | path traversal and Markdown tests | Implemented locally |
| DATA-001 | Result assessment and finding model | versioned Pydantic models | model validation tests | Implemented locally |
| DATA-002 | Result-first optional chart evidence | result records and evidence aggregation | multi-chart/no-prose tests | Implemented locally |
| DATA-003 | Report plan model | versioned plan/section/item models | plan validation and package tests | Implemented locally |
| DATA-004 | Review/freshness model | separate review and four freshness layers | review/freshness lifecycle tests | Implemented locally |
| DATA-005 | Package schema | manifest results/assessment/finding/report paths | preview integrity tests | Implemented locally |
| API-001 | Result-type finding-provider contract | public provider registration and descriptors | provider contract tests | Implemented locally |
| API-002 | Report synthesis/plan API | refresh, plan, draft endpoints | API/full regression suite | Implemented locally |
| API-003 | Review API | fingerprint-checked item review endpoint | workspace lifecycle tests | Implemented locally |
| API-004 | LLM inspection contract | bounded `report_summary` | seven-template LLM assertion | Implemented locally |
| UX-001 | Structured Review | sectioned claim cards and controls | frontend typecheck/build | Implemented locally |
| UX-002 | Evidence inspection | claim evidence/metadata links and accounting details | frontend typecheck/build | Implemented locally |
| UX-003 | Freshness UX | one operational status helper | frontend typecheck/build | Implemented locally |
| UX-004 | Export Preview | structured package fields and Markdown preview | preview tests and frontend build | Implemented locally |

## Implementation notes

- Implementation was authorized by Nelson Jeanrenaud on 2026-08-10 after final
  spec approval.
- Implementation plan:
  1. Add a versioned report-content module containing analytical result,
     assessment, finding, conclusion, evidence, review, report-plan, and layered
     freshness models plus canonical hashing and identity helpers.
  2. Materialize typed strategy results from renderer-independent analytical
     payloads carried in artifact metadata, aggregate optional chart evidence,
     deduplicate by canonical result fingerprint, and register providers by
     analytical result type.
  3. Implement explicit providers for the seven SPEC-008 result families and
     the four approved named synthesis rules with inspectable reportability
     criteria and non-causal language.
  4. Extend Analysis persistence, package manifest/reader/integrity, review
     refresh, export gating, report-plan mutation, review mutation, and Markdown
     rendering while retaining legacy batch observations/package readability.
  5. Replace the flat Workbench Review presentation with sectioned publishable
     claims, secondary assessment/evidence inspection, ordering/inclusion
     controls, and one operational freshness status; align Export Preview with
     the structured report.
  6. Add unit, lifecycle, API, compatibility, frontend, security, scale, and
     canonical Bahrain coverage; then populate traceability/evidence and run all
     completion gates.
- Expected implementation files include
  `src/f1_telemetry_charts/analysis/findings.py`, report/manifest/preview/workspace
  and API modules, Workbench types/API/page components, focused new report tests,
  and existing compatibility tests.
- The implementation sequence is: typed result references,
  assessments, dispositions, and fingerprints; result-type core providers;
  deduplication; named motorsport synthesis catalog; report-plan persistence;
  review/freshness APIs; Markdown/package rendering; Workbench UI; migration and
  canonical report review.
- The existing `Observation` and review files may be evolved or migrated rather
  than duplicated permanently. The implementation plan must choose one durable
  source of truth and avoid parallel observation/finding models after migration.
- The first implementation should prefer explicit move controls over mandatory
  drag-and-drop ordering so keyboard behavior and deterministic persistence are
  straightforward. Drag-and-drop may be added only if it preserves the same
  ordered model and accessibility.
- The canonical Bahrain report is acceptance evidence, not a new analytical
  source of truth. Its claims must remain derived from typed analytical results;
  generated charts are optional supporting evidence.
- Local implementation verification completed on 2026-08-10. Full discovery
  passed with 144 tests; frontend typecheck and production build passed;
  governance, spec, and drift validators passed. The cached canonical 2023
  Bahrain Race package contains six unique result fingerprints from seven
  charts, five result-owned findings, one interval-compatible conclusion, one
  unavailable compound assessment, and one context-only timeline assessment.
  All included claims were reviewed before the current export at
  `analyses/spec-009-bahrain-acceptance/exports/e5a97c5adb69c619`.
- Acceptance review follow-up now selects race-gap, representative-pace, and
  comparative pace-evolution claims for the Executive Summary; makes supporting
  single-driver evolution findings evidence-only after synthesis; renders
  human-readable comparison bases; qualifies the confounded pit reference-point
  comparison; and makes chart placement explicit in the ordered report plan.
  The Strategy Timeline is the first Strategy and Race Evolution item despite
  being context-only. Unavailable compound assessment data includes a typed
  reason, technical details, and next action. New structured Analysis packages
  omit legacy observation/review files; legacy package reading remains supported.
- Nelson Jeanrenaud accepted the canonical Bahrain report on 2026-08-10 and
  authorized canonical `chatbot` delivery. Browser viewport/accessibility review
  remains a documented follow-up gap; the frontend build also reports its
  existing non-blocking JavaScript chunk-size warning.

## Spec amendments

No amendments. The implementation follows the architecture approved on
2026-08-10.

## Review checklist

- [x] spec_id is unique and follows the SPEC-XXX format.
- [x] Every requirement has an ID, statement, rationale, acceptance criteria,
      verification method, and evidence location.
- [x] Non-goals are listed.
- [x] Open questions are resolved or explicitly deferred.
- [x] Verification matrix covers every requirement.
- [x] Conflict check completed.
- [x] Human approval recorded before status is set to Approved.
