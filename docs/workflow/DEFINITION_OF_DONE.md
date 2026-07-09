# Definition of Done

Work is **not complete** unless all of the following are true. This gate
protects against half-finished or untraceable changes.

- [ ] The PR references an approved spec (`SPEC-XXX`).
- [ ] The change maps to specific requirement IDs (REQ/NFR/SEC/UX/DATA/API).
- [ ] Tests or verification evidence are provided for each requirement.
- [ ] Relevant checks pass (governance scripts and any project tests).
- [ ] Documentation is updated if the change affects it (no drift).
- [ ] Traceability is updated (spec verification matrix + traceability table).
- [ ] No unrelated files are changed.
- [ ] Known limitations are documented.
- [ ] Rollback notes are included.
- [ ] The final summary is understandable from a phone.

If any box is unchecked, the work is **not done**. Say so plainly rather than
claiming completion.
