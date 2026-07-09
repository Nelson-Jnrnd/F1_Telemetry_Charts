---
doc_type: spec
spec_id:
title:
status:
owner:
related_issue:
related_prs: []
affected_components: []
affected_interfaces: []
supersedes: []
superseded_by:
depends_on: []
conflicts_with: []
last_verified_at:
---

<!--
HOW TO USE THIS TEMPLATE
- Copy this file to docs/specs/active/SPEC-XXX-short-slug.md.
- Fill in the frontmatter. spec_id must be unique (format: SPEC-001).
- status must be one of: Draft, In Review, Approved, In Implementation,
  Implemented, Superseded, Archived, Rejected.
- Requirement IDs: REQ-001 (functional), NFR-001 (non-functional),
  SEC-001 (security/privacy), UX-001 (user experience), DATA-001 (data),
  API-001 (API).
- Every requirement needs: ID, statement, rationale, acceptance criteria,
  verification method, evidence location.
- Once status is Approved, behavioral changes require a Spec Amendments entry.
  Typos and formatting may be fixed without an amendment; meaning may not.
-->

# <SPEC-XXX>: <Title>

## Summary

One paragraph. What this spec proposes and why, understandable from a phone.

## Context

Background needed to understand the problem. Link related specs, issues, prior
art. Do not introduce new requirements here.

## Problem statement

The specific problem being solved, in plain language.

## Goals

- What this spec intends to achieve.

## Non-goals

- What is explicitly out of scope. Be concrete — non-goals prevent scope creep.

## Users or actors

Who or what interacts with this change (end users, other systems, agents).

## Functional requirements

> Each requirement uses the full structure below. Copy the block per requirement.

### REQ-001: <short name>

- **Statement:** <what the system must do — testable, unambiguous>
- **Rationale:** <why this is required>
- **Acceptance criteria:** <observable conditions that prove it is met>
- **Verification method:** <automated test | script | manual check | inspection>
- **Evidence location:** <path to test / command / report, filled at implementation>

## Non-functional requirements

### NFR-001: <short name>

- **Statement:**
- **Rationale:**
- **Acceptance criteria:**
- **Verification method:**
- **Evidence location:**

## Security and privacy considerations

Use SEC-XXX IDs for any security or privacy requirement.

### SEC-001: <short name>

- **Statement:**
- **Rationale:**
- **Acceptance criteria:**
- **Verification method:**
- **Evidence location:**

## Data model impact

Describe new or changed data structures. Use DATA-XXX for data requirements.

### DATA-001: <short name>

- **Statement:**
- **Rationale:**
- **Acceptance criteria:**
- **Verification method:**
- **Evidence location:**

## API impact

Describe new or changed interfaces. Use API-XXX for API requirements.

### API-001: <short name>

- **Statement:**
- **Rationale:**
- **Acceptance criteria:**
- **Verification method:**
- **Evidence location:**

## UI or UX impact

Describe user-facing changes. Use UX-XXX for UX requirements.

### UX-001: <short name>

- **Statement:**
- **Rationale:**
- **Acceptance criteria:**
- **Verification method:**
- **Evidence location:**

## Configuration impact

New or changed configuration, defaults, environment variables, feature flags.

## Error handling

Expected error conditions and how the system should respond.

## Edge cases

Boundary and unusual conditions that must be handled.

## Acceptance criteria

Spec-level acceptance criteria: the conditions under which this spec as a whole
is considered satisfied. Individual requirements also carry their own criteria.

## Verification matrix

| Requirement ID | Acceptance criterion | Verification method | Test / command / manual check | Evidence location | PR reference |
| -------------- | -------------------- | ------------------- | ----------------------------- | ----------------- | ------------ |
| REQ-001        |                      |                     |                               |                   |              |

## Test plan

How the change will be tested: unit, integration, manual, and any data or
fixtures required.

## Rollback plan

How to revert this change safely if it causes problems.

## Open questions

- [ ] Question that must be answered before or during implementation.

## Human decisions required

- [ ] Decisions that only the human owner can make (with space for the answer).

## Conflict check

Does this spec overlap with or contradict any other spec? List affected
components and any related specs. If a conflict exists, record it in the
`conflicts_with` frontmatter and resolve via supersession or human decision.

## Traceability table

| Requirement ID | Design / component | Implementation (file/function) | Test | Status |
| -------------- | ------------------ | ------------------------------ | ---- | ------ |
| REQ-001        |                    |                                |      |        |

## Implementation notes

Notes captured during implementation: decisions, trade-offs, deviations (each
deviation must trace to an assumption or amendment).

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

- [ ] spec_id is unique and follows the SPEC-XXX format.
- [ ] Every requirement has an ID, statement, rationale, acceptance criteria,
      verification method, and evidence location.
- [ ] Non-goals are listed.
- [ ] Open questions are resolved or explicitly deferred.
- [ ] Verification matrix covers every requirement.
- [ ] Conflict check completed.
- [ ] Human approval recorded before status set to Approved.
