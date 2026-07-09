# Specification Index

This is the catalog of all specifications in this repository. It is **derived**
documentation: it summarizes specs but does not introduce requirements. If this
index conflicts with a spec, the spec wins.

Specs live under `docs/specs/` and move between lifecycle folders as their
status changes:

- `docs/specs/active/` — Draft and In Review specs being worked on.
- `docs/specs/approved/` — Approved specs, ready to implement.
- `docs/specs/implemented/` — Implemented specs.
- `docs/specs/archived/` — Archived, Superseded, or Rejected specs.

## How to add a spec

1. Copy `docs/specs/SPEC_TEMPLATE.md` to
   `docs/specs/active/SPEC-XXX-short-slug.md`.
2. Pick the next unused `SPEC-XXX` id.
3. Fill in the frontmatter and requirements.
4. Add a row to the table below.

## Spec statuses

`Draft` → `In Review` → `Approved` → `In Implementation` → `Implemented`.
Terminal alternatives: `Superseded`, `Archived`, `Rejected`.

## Index

| Spec ID | Title | Status | Owner | Related issue | Related PRs | Location |
| ------- | ----- | ------ | ----- | ------------- | ----------- | -------- |
| _(none yet)_ | | | | | | |

> Keep this table in sync with the frontmatter of each spec. `/spec-report` and
> `scripts/validate_drift.py` help detect drift between this index and the
> actual spec files.
