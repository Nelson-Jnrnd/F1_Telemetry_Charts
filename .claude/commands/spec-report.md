---
description: Report the state of all specs and the project roadmap.
---

# /spec-report

Summarize every specification and the roadmap. Read the frontmatter of each
file under `docs/specs/**` (and `docs/SPEC_INDEX.md`) to build the report.
Optionally run `python scripts/validate_specs.py` to surface structural issues.

## What to gather

For each spec, read `status`, `spec_id`, `title`, open questions, and whether a
verification matrix is filled in. Then group:

- **Draft** — status `Draft`.
- **In review** — status `In Review`.
- **Approved** — status `Approved`.
- **In implementation** — status `In Implementation`.
- **Implemented** — status `Implemented`.
- **Needs human decision** — specs with unresolved "Human decisions required"
  or open questions.
- **Missing verification** — specs whose verification matrix is empty or has
  requirements without a verification method.
- **Potential blockers** — specs with `conflicts_with` set, unresolved
  `depends_on`, or blocked status noted.

## Output format

```
Spec report

Draft:
In review:
Approved:
In implementation:
Implemented:
Needs human decision:
Missing verification:
Potential blockers:
```

List spec IDs (and short titles) under each heading. Write `none` where empty.
