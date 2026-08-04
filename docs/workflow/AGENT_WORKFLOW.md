# Agent Workflow

The standard lifecycle every change follows in this repository. This is
authoritative process documentation. It is deliberately lightweight — this is a
solo personal project — but the ordering is not optional.

## Lifecycle

The canonical delivery branch is `chatbot`. Verified work committed directly
to `chatbot` does not require a PR, a separate direct-delivery approval, or a
`delivery_refs` entry. Those delivery controls remain required when completing
work from any other branch.

1. **Intake** — A human gives an intent or task (issue, PR comment, or chat).
   The agent restates the request and identifies whether a spec is required. A
   spec is required for any feature or behavior change. Pure repository
   maintenance (docs, tooling, chores) is exempt.

2. **Spec draft** — The agent copies `docs/specs/SPEC_TEMPLATE.md` into
   `docs/specs/active/SPEC-XXX-slug.md`, assigns a unique `SPEC-XXX` id, and
   writes point-by-point, verifiable requirements. Status: `Draft`.

3. **Spec review** — The agent sets status to `In Review` and posts a
   phone-friendly summary. The human reviews requirement by requirement.

4. **Spec approval** — The human approves. The agent sets status to `Approved`,
   records the approval reference, and moves the file to
   `docs/specs/approved/`. See `DEFINITION_OF_READY.md`.

5. **Implementation plan** — The agent writes a short plan (steps, files,
   verification approach) in the spec's Implementation notes or the linked
   issue/PR. No product code yet.

6. **Implementation** — The agent implements **only** the approved scope. Status
   moves to `In Implementation`. No opportunistic refactors. Assumptions are
   recorded explicitly.

7. **Verification** — The agent runs governance scripts and any discoverable
   tests, fills the verification matrix with evidence locations, and updates the
   traceability table.

8. **Delivery creation** — On `chatbot`, proceed directly after verification.
   On another branch, open a PR using the template, linking the issue and spec,
   listing requirement IDs, and attaching verification evidence. The human may
   explicitly approve direct push from another branch instead; record that
   pushed commit under the spec's `delivery_refs`.

9. **Human review** — The human reviews using `HUMAN_REVIEW_GUIDE.md` during
   work on `chatbot`, through the PR on another branch, or by explicitly
   approving direct delivery from another branch. The agent responds to
   comments within the approved scope.

10. **Delivery** — After green checks, commit and push work on `chatbot`; on
    another branch, merge the PR or push the explicitly approved direct-delivery
    commit. The spec moves to `docs/specs/implemented/` with status
    `Implemented`. PR/direct-delivery references are recorded when delivery did
    not occur on `chatbot`.

11. **Handoff** — The agent runs `/handoff` to leave a clear state for the next
    session: branch, task, completed work, checks, assumptions, open decisions,
    and the next safe action.

## When to stop and ask

Stop and ask the human (do not guess) when:

- Two authoritative documents conflict.
- The requested change contradicts an approved spec without an amendment.
- A required human decision is unresolved.
- `/drift-check` reports a blocking issue.
