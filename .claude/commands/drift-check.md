---
description: Detect documentation drift and conflicting specs. Stop and ask if blocking.
---

# /drift-check

Detect documentation drift and conflicting specs. Run
`python scripts/validate_drift.py` and also reason about the checks below that
the script cannot fully judge. See `docs/workflow/DOCUMENTATION_AUTHORITY.md`
for the rules.

## Checks

1. **Duplicate spec IDs** — the same `SPEC-XXX` used by more than one file.
2. **Duplicate requirement IDs** — the same REQ/NFR/SEC/UX/DATA/API id reused
   within a spec (or across specs where it would be ambiguous).
3. **Approved specs changed without amendment** — an Approved/Implemented spec
   whose requirements changed but has no matching `Spec amendments` entry.
4. **Requirements introduced outside specs** — requirement-shaped IDs appearing
   in reports, README, or code as if authoritative.
5. **Reports or README defining new requirements** — derived docs introducing
   truth.
6. **Overlapping specs** — specs affecting the same component without a
   `depends_on`, `supersedes`/`superseded_by`, or `conflicts_with` note.
7. **Implemented specs without PR evidence** — status `Implemented` but no
   `related_prs`.
8. **Conflicting status** — spec status disagrees with the PR or issue state.

## Output format

```
Drift check

Blocking issues:
Warnings:
Conflicting specs:
Untracked requirements:
Recommended fix:
```

## Rule

If there are **blocking issues** (especially conflicting authoritative
documents), **stop and ask the human to decide.** Do not resolve a conflict
between two authoritative documents on your own.
