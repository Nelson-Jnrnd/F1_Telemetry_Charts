---
doc_type: spec
spec_id: SPEC-010
title: Publication-Ready Race Session Reports
status: Implemented
owner: Nelson Jeanrenaud
related_issue:
related_prs: []
delivery_refs:
  - 63f2fc5
affected_components:
  - analytical result providers
  - report plan and review
  - publication selection and rendering
  - analysis workspace persistence
  - report package export
  - local preview UI
affected_interfaces:
  - Analysis Workbench Story view
  - Analysis Workbench Evidence view
  - Analysis Workbench Preview view
  - Analysis Workbench Export view
  - generated package manifest
  - portable Markdown publication package
supersedes: []
superseded_by:
depends_on:
  - SPEC-001
  - SPEC-004
  - SPEC-008
  - SPEC-009
conflicts_with: []
last_verified_at: 2026-08-13
---

# SPEC-010: Publication-Ready Race Session Reports

## Summary

This spec turns one reviewed Race analysis into a publication-ready online
article draft. It extends SPEC-009 rather than creating a parallel narrative
system: measured session-spine facts and existing strategy results are typed
analytical results, enter the same assessment and finding architecture, and
remain governed by one reviewed report authority. That authority produces an
analyst evidence rendering and a selective reader-facing publication rendering.
The publication draft combines a current race chronology, reviewed analytical
claims, purposeful charts, and structured human framing while keeping internal
provenance in an evidence sidecar. A validated readiness state means a competent
motorsport editor can improve tone and emphasis without reconstructing the race,
replacing analytical claims, removing duplicated evidence, or restructuring the
article.

## Context

SPEC-001 introduced portable Markdown packages, evidence-linked observations,
and human review. SPEC-004 made the Analysis the durable workspace and defined
staged generation, review, freshness, and export. SPEC-008 added typed,
versioned race-strategy and pace results with explicit limitations and degraded
states. SPEC-009 made typed analytical results the sole reporting authority,
deduplicated results before finding generation, introduced explicit report
dispositions, bounded deterministic synthesis, structured report planning,
claim review, and stale-safe export.

The SPEC-009 canonical Bahrain report is analytically defensible but still
behaves like an evidence dossier. Claims repeat between the Executive Summary
and body, internal confidence and limitation scaffolding is reader-facing, six
charts support four substantive claims, and the report does not establish the
measured chronology before discussing pace and strategy. A publication author
must reconstruct classification, movement, pit sequence, neutralisation, and
major race intervals manually.

SPEC-010 addresses publication quality only. It does not add another general
analysis surface or broaden reporting to non-Race sessions.

## Problem statement

The application can produce and review defensible analytical findings, but it
cannot yet produce a coherent Race session article. It lacks a typed session
spine, deterministic editorial economy, structured human framing, clean
reader-facing rendering, and an enforceable definition of publication
readiness. Exported Markdown therefore requires structural rewriting and
evidence cleanup before publication.

## Goals

- Represent race chronology through typed analytical results inside the
  SPEC-009 result, finding, evidence, and review architecture.
- Preserve one reviewed report authority with analyst and publication
  renderings.
- Select a small, compatible, non-duplicative set of claims and charts.
- Support structured human framing without building a document editor.
- Export clean portable Markdown, web-ready assets, and an evidence sidecar.
- Define and enforce an explicit Publication draft ready state.
- Validate publication quality across ordinary dry, materially neutralised,
  and wet or mixed-condition Race sessions.

## Non-goals

- Qualifying, practice, sprint, or multi-session weekend reports.
- New analytical chart families.
- A rich-text, block, or general-purpose document editor.
- Autonomous LLM ghostwriting or creation of analytical facts.
- Direct WordPress, Ghost, Substack, or other CMS publication.
- External news, quotations, paddock reporting, or manually sourced context.
- Live-session reporting.
- Automatic claims about strategic intent, causality, or what was decisive.
- Fuel-corrected degradation, counterfactual no-stop modelling, or new
  estimated strategy models.
- Social-media graphics or promotional asset generation.

## Users or actors

- A motorsport analyst who generates and reviews evidence.
- A publication author who selects the story and supplies human framing.
- A motorsport editor who reviews the final draft.
- The local Analysis Workbench and package exporter.
- Optional read-only LLM consumers of bounded report summaries.

## Authoritative concepts

### One authority, two renderings

The reviewed report authority remains the only source for selected analytical
claims, chart placement, editorial fields, and publication state. The analyst
rendering exposes assessment, confidence, basis, limitations, unavailable
material, provenance, and evidence. The publication rendering exposes only the
selected reader-facing story, charts, captions, and compact methods material.

### Measurement taxonomy

Measured, derived, descriptive, and estimated are measurement categories, not
an evidence-strength hierarchy. Selection considers measurement category,
availability, confidence or quality, materiality, compatibility, and editorial
relevance together. A well-supported derived result may be stronger than a
poorly covered measured result. Estimated material is excluded by default and
requires explicit editorial opt-in.

### Canonical detailed placement

Each included claim has one canonical detailed placement. A summary may
reference that claim in shorter non-numeric language, but may not introduce a
second numerical or analytical assertion.

### Session spine

The session spine is a set of typed analytical results, assessments, and
findings. It is not a separate narrative engine. It answers what happened
before selected strategy and pace findings answer what was analytically
notable.

## Functional requirements

### REQ-001: Extend the SPEC-009 reporting authority

- **Statement:** Publication selection, human editorial content, rendering, and
  export must extend the existing SPEC-009 report authority and dependency
  graph; no parallel narrative or publication source of truth may be created.
- **Rationale:** Parallel models would duplicate review and freshness semantics.
- **Acceptance criteria:** One persisted authority controls analyst and
  publication renderings; changes are reflected in both; no independent
  publication claim store exists.
- **Verification method:** Model inspection, persistence tests, and end-to-end
  workspace tests.
- **Evidence location:** See the verification and traceability tables below.

### REQ-002: Materialise typed session-spine results

- **Statement:** For one selected Race, the analysis must materialise typed,
  versioned result types named race_classification,
  grid_to_finish_movement, pit_stop_sequence, neutralisation_periods,
  retirement_status, and position_change_interval.
- **Rationale:** A reader needs measured chronology before comparison.
- **Acceptance criteria:** Every result records session identity, subjects,
  boundaries, measurement category, provenance, coverage, quality, limitations,
  and explicit partial or unavailable states; missing data never becomes a
  guessed fact; a non-Race report target is rejected with an explicit
  unsupported-scope diagnostic.
- **Verification method:** Provider tests and complete/degraded fixtures.
- **Evidence location:** See the verification and traceability tables below.

### REQ-003: Use result-provider ownership for the session spine

- **Statement:** Session-spine types must register with the SPEC-009 provider
  contract and receive the same disposition, fingerprint, deduplication,
  finding ownership, and evidence treatment as existing analytical results.
- **Rationale:** Chronology must not bypass analytical governance.
- **Acceptance criteria:** Each unique spine result has one assessment; only
  reportable results produce findings; repeated references do not duplicate
  results or findings.
- **Verification method:** Registry, fingerprint, and deduplication tests.
- **Evidence location:** See the verification and traceability tables below.

### REQ-004: Preserve measurement taxonomy

- **Statement:** Selection and rendering must preserve measured, derived,
  descriptive, and estimated categories without ranking them as a hierarchy.
- **Rationale:** Category alone does not determine evidence strength.
- **Acceptance criteria:** Selection combines category, availability,
  confidence or quality, materiality, compatibility, and editorial relevance;
  estimated claims are excluded by default; renderers never strengthen the
  recorded category.
- **Verification method:** Selection truth tables and language assertions.
- **Evidence location:** See the verification and traceability tables below.

### REQ-005: Generate deterministic publication selection

- **Statement:** A named, versioned deterministic policy must propose sections,
  canonical detailed claims, summary references, and chart placements from
  current reviewed evidence.
- **Rationale:** Editorial economy must be repeatable without factual invention.
- **Acceptance criteria:** Identical authority state produces identical
  proposals; unsupported, unavailable, estimated, low-confidence, and
  materially confounded claims are excluded by default; estimated or
  confounded inclusion requires explicit review.
- **Verification method:** Determinism and selection tests.
- **Evidence location:** See the verification and traceability tables below.

### REQ-006: Enforce canonical detailed claim placement

- **Statement:** Each included claim must have one canonical detailed article
  placement; At a Glance may contain a shortened reference but no separate
  numerical or analytical assertion.
- **Rationale:** Summaries need concise references without duplicated evidence.
- **Acceptance criteria:** Two detailed placements are rejected; summary
  references resolve to canonical claims; summary copy contains no new metric.
- **Verification method:** Plan validation and Markdown tests.
- **Evidence location:** See the verification and traceability tables below.

### REQ-007: Use the approved article structure

- **Statement:** The plan must support, in order, Headline, Standfirst, At a
  Glance, How the Race Developed, Pace and Strategy, optional Key Comparison,
  Conclusion, and Methods and Evidence.
- **Rationale:** The structure moves from chronology to analytical significance.
- **Acceptance criteria:** Empty sections disappear; Key Comparison is absent
  by default unless supported; the system does not manufacture a duel,
  pit-cycle story, or decisive-event label.
- **Verification method:** Structure and degraded-evidence tests.
- **Evidence location:** See the verification and traceability tables below.

### REQ-008: Support structured human framing

- **Statement:** Authors must be able to supply headline, standfirst, section
  ledes, chart captions, chart alt text, and an optional conclusion through
  structured fields.
- **Rationale:** Human framing is required, but a document editor is not.
- **Acceptance criteria:** Fields are marked human-authored, cannot be mistaken
  for findings, survive evidence refresh, and become review-required rather
  than deleted when referenced evidence changes.
- **Verification method:** Persistence, provenance, and refresh tests.
- **Evidence location:** See the verification and traceability tables below.

### REQ-009: Enforce chart economy and purpose

- **Statement:** Each included chart must have editorial purpose, placement,
  caption, alt text, and result or finding references. The default must select
  two to four charts when at least two useful charts exist and must not
  automatically select two charts backed primarily by the same result.
- **Rationale:** A publication draft must not resemble an exported dashboard.
- **Acceptance criteria:** Redundant automatic selections are rejected; zero or
  one chart remains valid when evidence supports only that count; more than
  four requires explicit inclusion; context-only charts require a purpose.
- **Verification method:** Selection, validation, and browser tests.
- **Evidence location:** See the verification and traceability tables below.

### REQ-010: Render clean publication Markdown

- **Statement:** The publication renderer must omit internal IDs, fingerprints,
  serialized objects, raw metadata links, implementation terminology, and
  repetitive confidence scaffolding.
- **Rationale:** Internal traceability must not degrade the article.
- **Acceptance criteria:** Output contains human-readable bases and material
  qualifications only; internal detail stays in analyst rendering or the
  evidence sidecar; object values never render as '[object Object]'.
- **Verification method:** Golden Markdown, leakage, and escaping tests.
- **Evidence location:** See the verification and traceability tables below.

### REQ-011: Extend SPEC-009 freshness

- **Statement:** The existing dependency graph must extend through analytical
  evidence, analytical review, publication selection, human editorial content,
  publication rendering, and export.
- **Rationale:** Changed evidence must invalidate dependent publication state
  without creating parallel freshness concepts.
- **Acceptance criteria:** Changed evidence invalidates dependent claims,
  requires review, marks dependent human framing review-required without
  deleting it, and stales rendering and export; unrelated content stays current.
- **Verification method:** Dependency-transition tests.
- **Evidence location:** See the verification and traceability tables below.

### REQ-012: Validate publication readiness

- **Statement:** The application must compute an explicit readiness state and
  may report Publication draft ready only when every prerequisite passes.
- **Rationale:** Publication-ready must be validated, not promotional language.
- **Acceptance criteria:** Readiness requires a current session spine, no
  included stale evidence, all included claims reviewed, headline and
  standfirst, complete captions and alt text, no internal-format leakage, no
  duplicate detailed placement, no default-selected low-confidence or
  materially confounded claim, current preview, and valid package integrity.
- **Verification method:** Readiness truth-table and end-to-end tests.
- **Evidence location:** See the verification and traceability tables below.

### REQ-013: Expose actionable workflow states

- **Statement:** The UI must distinguish Evidence ready, Editorial work
  required, Review required, Publication draft ready, and Export current and
  show the next action.
- **Rationale:** Authors should not interpret internal freshness layers.
- **Acceptance criteria:** Every valid dependency combination maps to one
  primary state and next action; Export current never appears for stale or
  integrity-invalid output.
- **Verification method:** State mapping and browser tests.
- **Evidence location:** See the verification and traceability tables below.

### REQ-014: Export a portable publication package

- **Statement:** Export must produce clean article Markdown, publication plan
  metadata, web-ready chart assets, a machine-readable evidence sidecar, and a
  manifest containing package health and readiness state.
- **Rationale:** Publishing handoff should remain platform-neutral.
- **Acceptance criteria:** The package is relocatable; image links are relative
  and valid; captions and alt text are present; reader and analyst artifacts
  are distinct; users can copy Markdown and download the package locally.
- **Verification method:** Relocation, integrity, API, and browser tests.
- **Evidence location:** See the verification and traceability tables below.

## Non-functional requirements

### NFR-001: Deterministic output

- **Statement:** Spine results, assessments, findings, selection, readiness, and
  rendering must be deterministic for identical inputs and versions.
- **Rationale:** Review and freshness depend on stable identity.
- **Acceptance criteria:** Repeated generation produces stable fingerprints,
  ordering, selection, and Markdown apart from explicit export timestamps.
- **Verification method:** Repeated-run comparison tests.
- **Evidence location:** See the verification and traceability tables below.

### NFR-002: Analytical language safety

- **Statement:** Generated copy must not infer strategy intent, causality, or
  decisiveness beyond supported evidence.
- **Rationale:** Chronology and correlation do not establish cause.
- **Acceptance criteria:** Phrase-policy tests reject causal or intent language
  for measured, derived, descriptive, confounded, and estimated results unless
  a future approved result contract supports it.
- **Verification method:** Provider and renderer phrase-policy tests.
- **Evidence location:** See the verification and traceability tables below.

### NFR-003: Publication quality

- **Statement:** A ready draft must let a competent motorsport editor improve
  tone, style, and emphasis without reconstructing chronology, replacing
  claims, removing duplicated evidence, or restructuring the article.
- **Rationale:** This is the product definition of success.
- **Acceptance criteria:** Human acceptance passes for all three required Race
  categories using a recorded editorial rubric.
- **Verification method:** Multi-race human review.
- **Evidence location:** See the verification and traceability tables below.

### NFR-004: Responsive and accessible review

- **Statement:** Story, Evidence, Preview, and Export must remain operable at
  desktop and 390x844 mobile viewports with keyboard navigation and accessible
  labels.
- **Rationale:** Dense review must remain usable across supported viewports.
- **Acceptance criteria:** Controls, readiness, captions, and preview are
  readable and operable with no unexpected page overflow.
- **Verification method:** Browser, keyboard, and viewport checks.
- **Evidence location:** See the verification and traceability tables below.

## Security and privacy considerations

### SEC-001: Safe Markdown and package containment

- **Statement:** Markdown, frontmatter, captions, alt text, and asset paths must
  be escaped and contained within the package.
- **Rationale:** Human content and paths are untrusted inputs.
- **Acceptance criteria:** Raw HTML is disabled or sanitized; path traversal is
  rejected; output cannot reference files outside the package.
- **Verification method:** Injection and containment tests.
- **Evidence location:** See the verification and traceability tables below.

### SEC-002: Local-only publishing handoff

- **Statement:** SPEC-010 must not transmit content or assets to an external
  publishing service.
- **Rationale:** CMS publication and external transfer are out of scope.
- **Acceptance criteria:** Copy and download operate locally; no network
  publishing endpoint or credential field is introduced.
- **Verification method:** API and dependency inspection.
- **Evidence location:** See the verification and traceability tables below.

## Data model impact

### DATA-001: Versioned session-spine schemas

- **Statement:** Each spine result must have a typed payload with stable
  identity inputs, measurement category, provenance, coverage, quality, and
  degraded-state fields.
- **Rationale:** Findings and freshness require stable semantic results.
- **Acceptance criteria:** Required types serialize, validate, fingerprint, and
  migrate or fail explicitly by version.
- **Verification method:** Schema and compatibility tests.
- **Evidence location:** See the verification and traceability tables below.

### DATA-002: Publication plan and editorial provenance

- **Statement:** The authority must represent canonical claim placements,
  summary references, chart purpose and placement, structured editorial fields,
  author provenance, and dependency references.
- **Rationale:** Editing must stay traceable without duplicating facts.
- **Acceptance criteria:** The model rejects duplicate detailed placement,
  dangling references, missing chart fields, and analytical claims encoded as
  untyped editorial text.
- **Verification method:** Model and round-trip tests.
- **Evidence location:** See the verification and traceability tables below.

### DATA-003: Readiness and package metadata

- **Statement:** Readiness prerequisites, primary state, rendered paths,
  evidence-sidecar paths, and package health must be versioned in Analysis and
  export metadata.
- **Rationale:** Preview and export must agree on readiness and artifact identity.
- **Acceptance criteria:** Reloading or relocation preserves the snapshot and
  exposes stale or incompatible versions explicitly.
- **Verification method:** Persistence, relocation, and compatibility tests.
- **Evidence location:** See the verification and traceability tables below.

## API impact

### API-001: Publication workflow API

- **Statement:** Typed APIs must support proposal refresh, plan and editorial
  mutation, readiness inspection, preview regeneration, Markdown retrieval, and
  package export.
- **Rationale:** The UI must not mutate files or derive readiness independently.
- **Acceptance criteria:** Mutations validate fingerprints and dependencies,
  stale writes are rejected, failures are atomic, and responses return
  authoritative current state.
- **Verification method:** API concurrency and validation tests.
- **Evidence location:** See the verification and traceability tables below.

### API-002: Bounded read-only LLM inspection

- **Statement:** If exposed through the LLM contract, publication data may be
  inspected as bounded structure and evidence summaries but analytical facts or
  human editorial content may not be silently mutated.
- **Rationale:** Optional assistance must not bypass authority.
- **Acceptance criteria:** The contract is bounded, distinguishes human text,
  stays read-only for facts, and rejects unsupported mutation fields.
- **Verification method:** LLM contract tests.
- **Evidence location:** See the verification and traceability tables below.

## UI or UX impact

### UX-001: Story, Evidence, Preview, and Export

- **Statement:** The workflow must expose Story, Evidence, Preview, and Export
  as its four primary stages.
- **Rationale:** Authors need a story-first surface while analysts retain detail.
- **Acceptance criteria:** Story controls framing and placement; Evidence
  exposes analytical detail; Preview matches reader output; Export provides
  local handoff.
- **Verification method:** Component and browser tests.
- **Evidence location:** See the verification and traceability tables below.

### UX-002: Story completeness

- **Statement:** Story must expose headline, three main points, included
  sections, selected evidence, chart placement, and missing human framing.
- **Rationale:** Authors should not infer completeness from internal models.
- **Acceptance criteria:** Each item has concise status and action; serialized
  objects and internal IDs are not primary copy.
- **Verification method:** Browser and accessibility tests.
- **Evidence location:** See the verification and traceability tables below.

### UX-003: Evidence inclusion clarity

- **Statement:** Evidence must separate analytical acceptance from editorial
  inclusion and explain default exclusion.
- **Rationale:** A valid result is not automatically a suitable article claim.
- **Acceptance criteria:** Users can inspect exclusion reasons, explicitly opt
  in where allowed, and cannot mistake exclusion for analytical failure.
- **Verification method:** State and browser tests.
- **Evidence location:** See the verification and traceability tables below.

### UX-004: Exact publication preview

- **Statement:** Preview must render the exact structure, copy, captions, alt
  text, and assets that export will contain.
- **Rationale:** An approximation would undermine editorial review.
- **Acceptance criteria:** Preview and exported Markdown are structurally
  equivalent; stale preview cannot be Publication draft ready.
- **Verification method:** Preview/export parity tests.
- **Evidence location:** See the verification and traceability tables below.

## Configuration impact

No new global configuration format is required. Selection, editorial content,
chart placement, and optional portable frontmatter belong to the Analysis-local
authority. CMS credentials, publication tokens, and network destinations are
prohibited.

## Error handling

- Missing spine inputs produce typed partial, unavailable, or unsupported
  assessments without blocking unrelated results.
- Unsupported result or plan versions fail explicitly and preserve files.
- Duplicate placement, dangling references, missing captions or alt text, and
  redundant automatic chart selection produce plan validation errors.
- Stale evidence or review blocks Publication draft ready and current export
  without deleting prior exports.
- Failed preview or export writes are atomic.
- Internal-format leakage blocks Publication draft ready.

## Edge cases

- A race with no useful analytical chart may still produce a measured report.
- A race with fewer than two useful charts is not padded.
- A summary may reference a detailed claim without repeating its metric.
- Key Comparison disappears when no compatible evidence supports it.
- DNS, DNF, unclassified, and post-session classification states remain explicit.
- Neutralisation coverage may be partial or overlapping.
- Multiple charts may reference one result, but only one is automatically
  selected unless distinct purposes are explicitly reviewed.
- Changed evidence preserves human framing but makes it review-required.
- Estimated or confounded evidence requires explicit opt-in and review.
- Legacy SPEC-009 analyses remain readable and can initialise a proposal.

## Acceptance criteria

SPEC-010 is complete only when:

1. One Race produces typed spine results through SPEC-009 provider ownership.
2. Both renderings share one persisted authority.
3. Selection creates one detailed placement per claim and avoids redundant
   charts while permitting non-numeric summary references.
4. The approved structure omits empty or unsupported sections.
5. Human framing persists with provenance and correct freshness.
6. Publication readiness cannot pass while stale, incomplete, leaking internal
   format, or integrity-invalid.
7. Export produces relocatable Markdown, web-ready assets, and evidence sidecar.
8. All four stages pass desktop, mobile, keyboard, and parity review.
9. Dry, neutralised, and wet or mixed Race reports pass human acceptance.
10. An editor can improve voice without structural or analytical reconstruction.

## Verification matrix

| Requirement ID | Acceptance criterion | Verification method | Test / command / manual check | Evidence location | PR reference |
| -------------- | -------------------- | ------------------- | ----------------------------- | ----------------- | ------------ |
| REQ-001 | One authority produces both renderings | Automated/inspection | Persistence and architecture tests | `analysis/findings.py`; `test_publication_report.py` | |
| REQ-002 | Required spine types cover degraded states | Automated | Provider tests | `analysis/publication.py`; `test_publication_report.py` | |
| REQ-003 | Spine results use SPEC-009 ownership | Automated | Registry/fingerprint tests | `analysis/findings.py`; `test_publication_report.py` | |
| REQ-004 | Taxonomy and selection factors persist | Automated | Truth-table tests | `analysis/publication.py`; `test_publication_report.py` | |
| REQ-005 | Proposal is deterministic and safe by default | Automated | Selection tests | `propose_publication_plan`; `test_publication_report.py` | |
| REQ-006 | One detailed placement and bounded summary | Automated | Plan/render tests | `validate_publication_plan`; `test_publication_report.py` | |
| REQ-007 | Structure is ordered and optional | Automated | Structure snapshots | `PUBLICATION_SECTION_ORDER`; `test_publication_report.py` | |
| REQ-008 | Human fields persist with provenance | Automated | Refresh tests | `EditorialField`; workspace persistence tests | |
| REQ-009 | Charts are purposeful and non-redundant | Automated/manual | Selection/browser tests | `validate_publication_plan`; Story UI | |
| REQ-010 | Reader output has no internal leakage | Automated/manual | Golden Markdown | `render_publication_markdown`; leakage assertions | |
| REQ-011 | Freshness extends SPEC-009 dependencies | Automated | Transition matrix | `ReportFreshness`; workspace tests | |
| REQ-012 | Every prerequisite gates readiness | Automated | Readiness matrix | `evaluate_readiness`; `test_publication_report.py` | |
| REQ-013 | States and next actions are unambiguous | Automated/manual | Browser tests | `PublicationReadiness`; Workbench state badges | |
| REQ-014 | Package is complete and relocatable | Automated/manual | Integrity tests | `write_publication_export_package`; package tests | |
| NFR-001 | Identical inputs produce stable output | Automated | Repeated runs | `test_session_spine_materializes_six_typed_provenance_qualified_results`; selection equality | |
| NFR-002 | Generated language remains non-causal | Automated/manual | Phrase tests | session-spine provider and clean-render tests | |
| NFR-003 | Publication output needs no structural rewrite | Manual | Final human validation | Canonical Bahrain reviews and final holistic validation, 2026-08-13 | |
| NFR-004 | Workflow is responsive and accessible | Automated/manual | Viewport checks | Built UI: 1440x900 and 390x844, no overflow or console errors | |
| SEC-001 | Markdown and assets are safe | Automated | Injection/path tests | `_safe_reader_text`; `_safe_markdown_path`; package tests | |
| SEC-002 | No external publishing exists | Inspection | API inspection | Local-only FastAPI routes; no publishing client | |
| DATA-001 | Spine schemas validate and version | Automated | Schema tests | `AnalyticalResultRecord`; spine tests | |
| DATA-002 | Plan enforces references and provenance | Automated | Model tests | publication Pydantic models and plan validation | |
| DATA-003 | Readiness survives reload/relocation | Automated | Package tests | manifest/package reader/workspace tests | |
| API-001 | Mutations are typed, atomic, and stale-safe | Automated | API tests | `PublicationUpdateRequest`; stale API test | |
| API-002 | LLM inspection is bounded and read-only | Automated | Contract tests | `llm.contract._report_summary` | |
| UX-001 | Four-stage workflow operates | Automated/manual | Browser flow | Story/Evidence/Preview/Export Workbench views | |
| UX-002 | Story exposes completeness | Automated/manual | Browser review | Story readiness, fields, claims, and charts | |
| UX-003 | Acceptance and inclusion are distinct | Automated/manual | State tests | Evidence review vs Story inclusion controls | |
| UX-004 | Preview matches export | Automated/manual | Parity tests | `render_publication_markdown`; clean package reader/export tests | |

## Test plan

### Unit tests

- Spine schemas, versions, fingerprints, and degraded states.
- Provider dispositions, reportability, and deduplication.
- Taxonomy preservation and selection truth tables.
- Detailed placement and summary-reference validation.
- Default exclusion and explicit opt-in.
- Chart redundancy, purpose, caption, alt text, and count rules.
- Editorial provenance and freshness.
- Readiness truth table and renderer leakage.

### Integration and API tests

- Race data through spine, findings, selection, review, framing, preview, and
  export.
- Existing strategy results and spine results in one authority.
- Targeted invalidation and human-copy preservation.
- Atomic failure, stale mutation, package relocation, and legacy compatibility.
- Bounded read-only LLM inspection.

### Frontend and browser tests

- Story, Evidence, Preview, and Export at desktop and 390x844.
- Keyboard navigation, focus, labels, and actionable readiness.
- Structured editorial editing and evidence inclusion.
- Claim placement, chart purpose, and explicit override.
- Exact preview/export parity and no unexpected console errors.

### Three-race editorial acceptance

- One ordinary dry Race.
- One materially SC/VSC/red-flag-neutralised Race.
- One wet or mixed-condition Race.
- For each, account for chronology, claims, charts, omissions, and limitations.
- Record whether an editor can improve voice without structural reconstruction.

### Expected completion commands

    python -m unittest discover -s tests -p "test_*.py"
    python scripts/validate_governance.py
    python scripts/validate_specs.py
    python scripts/validate_drift.py
    cd frontend
    pnpm run typecheck
    pnpm run build

Dedicated multi-race and publication-package commands must be added during
implementation planning once their interfaces exist.

## Rollback plan

- Keep publication fields and paths versioned and optional.
- Never delete results, review history, human text, or prior exports.
- If publication features are disabled, retain the analyst rendering.
- Older readers may ignore optional fields when SPEC-009 data stays valid.
- Failed migration or export writes no partial current package.

## Open questions

- None. Non-Race reporting, CMS integration, new charts, autonomous writing,
  and social assets are explicitly deferred.

## Human decisions required

- [x] Race only; publication quality rather than new analytics.
- [x] One SPEC-009 authority with two renderings.
- [x] Session spine implemented as typed analytical results.
- [x] Measurement category is a taxonomy combined with quality factors.
- [x] One detailed placement; summaries may make non-numeric references.
- [x] Extend SPEC-009 freshness and preserve human copy.
- [x] Structured editorial fields, deterministic selection, human framing.
- [x] Estimated, low-confidence, and materially confounded evidence excluded by
      default.
- [x] Normally two to four purposeful, non-redundant charts.
- [x] Portable package before CMS integration.
- [x] Three-race acceptance and validated publication-readiness state.
- [x] Human approval of this written specification recorded from Nelson
      Jeanrenaud on 2026-08-11: "I validate it."

## Conflict check

- SPEC-001 portable Markdown and evidence review remain intact.
- SPEC-004 Analysis persistence and staged freshness remain authoritative.
- SPEC-008 calculations and measurement semantics are not recomputed.
- SPEC-009 typed-result authority, one-Race scope, review, and export safety are
  extended rather than replaced.
- No approved behavior is removed or contradicted. No blocking conflict exists.

## Traceability table

| Requirement ID | Design / component | Implementation (file/function) | Test | Status |
| -------------- | ------------------ | ------------------------------ | ---- | ------ |
| REQ-001 | Shared report authority | `analysis/report.py`, `analysis/workspace.py` | `test_publication_report.py`; `test_analysis_workspace.py` | Implemented |
| REQ-002 | Session-spine providers | `analysis/findings.py` spine providers | `test_publication_report.py` | Implemented |
| REQ-003 | Provider registry | `analysis/findings.py` provider catalog | `test_strategy_analysis.py` | Implemented |
| REQ-004 | Taxonomy semantics | `analysis/findings.py`, `analysis/publication.py` | `test_strategy_analysis.py`; `test_publication_report.py` | Implemented |
| REQ-005 | Selection policy | `analysis/publication.py::propose_publication_plan` | `test_publication_report.py` | Implemented |
| REQ-006 | Claim placement | `analysis/publication.py` | `test_publication_report.py` | Implemented |
| REQ-007 | Article structure | `analysis/report.py::render_publication_markdown` | `test_publication_report.py` | Implemented |
| REQ-008 | Editorial fields | `analysis/findings.py`, `analysis/workspace.py` | `test_analysis_workspace.py` | Implemented |
| REQ-009 | Chart selection | `analysis/publication.py` | `test_publication_report.py` | Implemented |
| REQ-010 | Publication renderer | `analysis/report.py` | `test_publication_report.py` | Implemented |
| REQ-011 | Freshness extension | `analysis/workspace.py` | `test_analysis_workspace.py` | Implemented |
| REQ-012 | Readiness validator | `analysis/publication.py::evaluate_readiness` | `test_publication_report.py` | Implemented |
| REQ-013 | Workflow states | `analysis/publication.py`, `analysis/workspace.py` | `test_analysis_workspace.py` | Implemented |
| REQ-014 | Package exporter | `analysis/report.py::write_publication_export_package` | `test_analysis_workspace.py` | Implemented |
| NFR-001 | Determinism | `analysis/publication.py` versioned policy | `test_publication_report.py` | Implemented |
| NFR-002 | Phrase policy | `analysis/findings.py`, `analysis/publication.py` | `test_publication_report.py` | Implemented |
| NFR-003 | Editorial rubric | `analysis/publication.py::evaluate_readiness` | canonical Bahrain human acceptance plus chronology-only readiness regression | Implemented |
| NFR-004 | Accessibility | caption/alt readiness checks | `test_publication_report.py`; 390x844 browser evidence | Implemented |
| SEC-001 | Markdown/path safety | `analysis/report.py` export writer | `test_analysis_workspace.py` | Implemented |
| SEC-002 | Local-only boundary | `analysis/workspace.py` atomic local export | `test_analysis_workspace.py` | Implemented |
| DATA-001 | Spine schemas | `analysis/findings.py`, `analysis/publication.py` | `test_publication_report.py`; `test_strategy_analysis.py` | Implemented |
| DATA-002 | Publication plan | `analysis/findings.py`, `analysis/publication.py` | `test_publication_report.py` | Implemented |
| DATA-003 | Readiness metadata | `analysis/findings.py`, `analysis/manifest.py` | `test_analysis_workspace.py` | Implemented |
| API-001 | Workflow endpoints | `ui/server.py` analysis endpoints | `AnalysisApiTests` | Implemented |
| API-002 | LLM inspection | `llm/contract.py` | `test_analysis_workspace.py` | Implemented |
| UX-001 | Four-stage workflow | `AnalysisWorkbenchPage.tsx` | frontend build; browser evidence | Implemented |
| UX-002 | Story completeness | `StoryEditor`, readiness validator | `test_publication_report.py`; browser evidence | Implemented |
| UX-003 | Inclusion clarity | `EvidenceEditor` | browser evidence | Implemented |
| UX-004 | Preview parity | `AnalysisWorkbenchPage.tsx::PublicationPreview`, `analysis/report.py`, `preview/reader.py` | export hash/package-reader verification | Implemented |

## Implementation notes

Nelson Jeanrenaud approved the complete written specification on 2026-08-11
with the explicit statement "I validate it." The Definition of Ready may be
evaluated; product implementation still requires an implementation plan.

Recommended sequence after approval:

1. Add versioned session-spine types and providers.
2. Extend the authority with publication plan and editorial provenance.
3. Implement selection, placement, and chart economy.
4. Extend freshness and readiness.
5. Add renderer, evidence sidecar, and package.
6. Rebuild the Workbench workflow.
7. Add three-race acceptance and human editorial review.

Implementation started on 2026-08-11 after Nelson Jeanrenaud explicitly
confirmed approval and authorised correction of the clerical approval-state
conflict. The automated product slice is implemented. Final holistic human
validation on 2026-08-13 closed the amended acceptance scope.

The Bahrain workflow and publication draft were accepted on 2026-08-11 after
AMEND-002 added the final exported claim-to-evidence bridge. Bahrain is the
canonical normal-race package. AMEND-004 later waived separate disrupted-race
and wet-or-mixed package production at final closeout.

Nelson Jeanrenaud gave final holistic validation on 2026-08-13 with "Perfect we
can close this spec it's all done I validate everything." AMEND-004 records
that decision, closes the remaining fixture-specific human gate, and completes
the lifecycle without claiming that separate disrupted and wet packages were
produced.

AMEND-005 corrections were fully verified with 154 backend tests, frontend
typecheck/build, governance, specification, drift, and whitespace checks. The
implementation was delivered in commit `63f2fc5` after Nelson Jeanrenaud
explicitly authorised the commit on 2026-08-13.

## Spec amendments

### AMEND-001: Require structural editorial completeness and a clean web package

- **Date:** 2026-08-11
- **Reason:** Human review accepted the SPEC-010 architecture, session-spine
  concept, Story/Evidence separation, and selection model, but rejected the
  first canonical Bahrain package because the deterministic draft still
  required structural reconstruction rather than voice editing.
- **Changed requirements:** REQ-005 through REQ-010, REQ-012 through REQ-014,
  NFR-002 through NFR-004, DATA-002, DATA-003, UX-002, and UX-004.
- **Behavioral impact:**
  - The deterministic Race proposal prioritises classification, the largest
    non-duplicated field recovery, and material neutralisation before pace and
    strategy evidence. Raw pit-event inventory counts, duplicated movement
    claims, generic summary references, and component claims already represented
    by an included synthesis are excluded by default.
  - At a Glance must contain concrete race takeaways that resolve to canonical
    claims. A generic report label or evidence-process statement is invalid.
  - Derived cumulative representative-lap pace must be labelled as derived and
    explicitly distinguished from elapsed race gap in the claim and methods
    copy.
  - Publication readiness requires a non-generic editorial headline, a
    publication standfirst, How the Race Developed and Pace and Strategy ledes,
    a conclusion, informative captions, and visual-description alt text. A
    chart title or repeated claim is insufficient caption or alt copy.
  - Mobile Story, Evidence, Preview, and Export prioritise the working surface;
    the desktop analysis inventory may not consume most of a 390x844 viewport.
  - The portable publication export is a clean handoff containing `article.md`,
    `article.json`, `evidence.json`, `manifest.json`, and web-oriented selected
    assets. Analyst-only and full-workbench artifacts remain available in the
    Analysis package but are not copied into the publication export.
- **Test impact:** Add deterministic Bahrain selection and golden article tests,
  derived-versus-measured language assertions, editorial-quality readiness
  cases, clean export contract and relocation tests, and 390x844 browser
  acceptance showing a readable article-width Preview.
- **Human approval reference:** Nelson Jeanrenaud's 2026-08-11 canonical
  Bahrain review: "Fix the editorial selection/output policy, the
  cumulative-delta labelling, captions and alt text, require enough human
  framing before declaring publication-ready, and repair mobile rendering."

### AMEND-002: Preserve publication claim placement in the portable export

- **Date:** 2026-08-11
- **Reason:** Human review accepted the architecture, workflow, readiness model,
  mobile rendering, package structure, and Bahrain draft quality, but found
  that the portable export contained article claims and evidence authority
  without an explicit machine-readable relationship between them.
- **Changed requirements:** REQ-006, REQ-010, REQ-014, DATA-002, DATA-003,
  NFR-001, and UX-004.
- **Behavioral impact:** `article.json` schema version 2 stores a canonical
  `claim_id` beside every published claim paragraph and At a Glance item.
  `evidence.json.publication_placements` records the same selected claim IDs,
  publication sections, publication paragraphs, and optional summary
  references. Every exported ID must resolve to a finding or conclusion in the
  same evidence sidecar; prose matching is not an authority mechanism. The
  rendered reader article continues to hide internal IDs.
- **Test impact:** Export tests must prove equality between the article claim-ID
  set and the publication-placement claim-ID set, and prove that every ID
  resolves inside `evidence.json.findings`.
- **Human approval reference:** Nelson Jeanrenaud's 2026-08-11 round-two review:
  "Canonical package: add explicit publication-claim-to-evidence mapping, then
  accept."

### AMEND-003: Type portable and source-analysis chart evidence references

- **Date:** 2026-08-13
- **Reason:** Final Bahrain acceptance found that evidence-sidecar chart paths
  retained Analysis-workspace `charts/` locations even when selected assets
  were exported under `assets/`. The paths looked package-relative but did not
  resolve in the portable package.
- **Changed requirements:** REQ-014, DATA-003, SEC-001, and UX-004.
- **Behavioral impact:** Evidence associated with an exported selected chart is
  emitted with `reference_scope: package` and remapped `assets/` image and
  metadata paths that must resolve inside the export. Evidence retained only
  as Analysis provenance is emitted with `reference_scope: source_analysis`
  and explicit `source_image_path` / `source_metadata_path` fields; it does not
  expose ambiguous package-style `image_path` or `metadata_path` fields. The
  publication export contract version advances to 3 so an older package cannot
  be reused for the same article fingerprint.
- **Test impact:** Export tests validate package-reference existence and prove
  source-analysis references are explicitly scoped and cannot be mistaken for
  portable paths.
- **Human approval reference:** Nelson Jeanrenaud's 2026-08-13 final Bahrain
  review accepted the canonical package and directed this immediate technical
  cleanup before moving to the disrupted-race fixture.

### AMEND-004: Close the remaining fixture-specific human acceptance gate

- **Date:** 2026-08-13
- **Reason:** After accepting the complete architecture, workflow, readiness,
  traceability, canonical dry-race package, and export-contract cleanup, the
  product owner explicitly validated everything and directed that SPEC-010 be
  closed rather than continuing with separate disrupted and wet fixture
  packages.
- **Changed requirements:** NFR-003 and the three-race editorial acceptance
  completion gate.
- **Behavioral impact:** None. This amendment changes only the remaining human
  verification scope. The canonical Bahrain package and automated degraded,
  neutralisation, freshness, safety, rendering, and export tests remain the
  recorded evidence. Separate disrupted-race and wet-or-mixed publication
  packages were not produced and are not claimed as completed artifacts.
- **Test impact:** None; final validation remains the 150-test suite, frontend
  typecheck/build, governance validators, browser acceptance, package-reader
  integrity, and human acceptance history recorded in this spec.
- **Human approval reference:** Nelson Jeanrenaud, 2026-08-13: "Perfect we can
  close this spec it's all done I validate everything."

### AMEND-005: Correct Race semantics and conditional editorial readiness

- **Date:** 2026-08-13
- **Reason:** Technical closeout review found four bounded correctness defects:
  recorded running order could masquerade as official classification, grid zero
  could enter movement arithmetic, lapped statuses could be treated as
  non-finishes, and an absent Pace and Strategy section still required a lede.
- **Changed requirements:** REQ-002, REQ-004, REQ-005, REQ-007, REQ-012,
  NFR-002, NFR-003, DATA-001, DATA-003, and UX-002.
- **Behavioral impact:** Classification entries record whether position comes
  from official classification or last recorded running order. Any substituted
  order is derived, medium-quality evidence and cannot use official winner/order
  language. Grid position zero is typed as pit-lane context and excluded from
  movement arithmetic. `Lapped` and general `+N Lap` / `+N Laps` statuses are
  classified as finishers. A section lede is required only when its section has
  an included claim or chart; empty sections disappear without blockers.
- **Test impact:** Four regressions cover classification provenance, pit-lane
  grid context, lapped-finisher normalization, and conditional section ledes.
  Full discovery passes with 154 tests.
- **Human approval reference:** Nelson Jeanrenaud's 2026-08-13 technical
  closeout verdict listing these four bounded correctness issues as required
  changes.

## Closeout

- **Final status:** Implemented in delivery commit `63f2fc5` after AMEND-005
  correction and verification.
- **Human acceptance:** Complete on 2026-08-13.
- **Canonical artifact:**
  `review-packages/SPEC-010-bahrain-canonical-v3.zip`.
- **Known limitation:** Separate disrupted-race and wet-or-mixed publication
  packages were waived at closeout and were not produced.
- **Rollback:** Preserve prior exports and disable or ignore the optional
  publication fields/contract-v3 sidecar; the SPEC-009 analyst rendering and
  evidence authority remain intact.

## Review checklist

- [x] spec_id is unique and follows the SPEC-XXX format.
- [x] Every requirement has an ID, statement, rationale, acceptance criteria,
      verification method, and evidence location.
- [x] Non-goals are listed.
- [x] Open questions are resolved or explicitly deferred.
- [x] Verification matrix covers every requirement.
- [x] Conflict check completed.
- [x] Human approval recorded before status set to Approved.
