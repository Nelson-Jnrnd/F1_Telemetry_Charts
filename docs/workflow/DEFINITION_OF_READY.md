# Definition of Ready

Implementation of a spec **must not start** unless all of the following are
true. This gate protects against building the wrong thing.

- [ ] A spec exists for the change.
- [ ] The spec has a unique `SPEC-XXX` id.
- [ ] The spec status is **Approved**.
- [ ] Every requirement has acceptance criteria.
- [ ] Every acceptance criterion has a verification method.
- [ ] Non-goals are listed.
- [ ] Open questions are resolved or explicitly deferred.
- [ ] Risks are listed (rollback plan and edge cases considered).
- [ ] Human approval is recorded (approval reference in the spec).

If any box is unchecked, the spec is **not ready**. Return it to the human with
a short note on what is missing.
