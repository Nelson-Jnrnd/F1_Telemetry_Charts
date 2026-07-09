<!--
Fill every section. The governance workflow and human reviewer expect this
structure. Keep the summary phone-friendly.
-->

## Phone-friendly summary

<!-- 2-4 plain sentences: what changed and why. Readable on a phone. -->

## Linked issue

<!-- Closes #NN -->

## Linked spec

- **Spec:** <!-- SPEC-XXX, path in docs/specs/ -->
- **Spec status:** <!-- Approved / Implemented -->

## Requirement IDs implemented

<!-- List each requirement this PR satisfies, e.g. REQ-001, NFR-002. -->

## Files changed by category

- **Specs / docs:**
- **Source:**
- **Tests:**
- **Tooling / CI:**

## Tests or checks run

<!-- Every command run and its real result. Include governance scripts. -->

```
python scripts/validate_governance.py
python scripts/validate_specs.py
python scripts/validate_drift.py
```

## Verification evidence

<!-- For each requirement ID, where is the proof? Link tests/output/matrix rows. -->

## Documentation updates

<!-- What docs changed, or "none needed" with a reason. -->

## Risks

<!-- What could go wrong. -->

## Rollback plan

<!-- How to revert safely. -->

## Known limitations

<!-- What this PR intentionally does not do. -->

## Agent self-review checklist

- [ ] References an approved spec and lists requirement IDs.
- [ ] Change is minimal and scoped — no opportunistic refactors.
- [ ] No unrelated files changed.
- [ ] Traceability updated (verification matrix + traceability table).
- [ ] Governance scripts run and passing (output above).
- [ ] No failing tests suppressed; no failed commands hidden.
- [ ] Assumptions recorded.
- [ ] Summary is phone-friendly.

## Human review checklist

- [ ] Spec scope matches what was approved.
- [ ] Verification evidence is convincing.
- [ ] Risks and rollback are acceptable.
- [ ] No scope creep.
