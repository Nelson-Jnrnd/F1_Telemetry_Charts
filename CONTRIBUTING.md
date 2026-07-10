# Contributing

This is a solo personal project using a specification-first, AI-agent-led
workflow. Contributions from humans or agents follow the same lightweight
process.

## Process

1. Intent: describe the requested change.
2. Spec: write or update a verifiable spec when behavior changes.
3. Approval: implementation starts only after spec approval.
4. Implement: change only the approved scope.
5. Verify: run governance scripts and relevant tests.
6. PR: link the spec, requirement IDs, and verification evidence.

## Rules That Matter

- Requirements live only in specs.
- Keep changes minimal and scoped.
- Do not suppress failing tests.
- Do not hide failed commands.
- Approved specs need a Spec Amendments entry for behavioral changes.
- If authoritative documents conflict, stop and ask for a human decision.

## Build And Test Commands

```powershell
python -m pip install -e .
python -m unittest discover -s tests -p "test_*.py"
python scripts/benchmark_mvp.py
python scripts/validate_governance.py
python scripts/validate_specs.py
python scripts/validate_drift.py
```

CI runs the same unit and governance checks in `.github/workflows/ci.yml`.
With a populated FastF1 smoke cache, run
`python scripts/benchmark_fastf1_cache.py --cache-dir .cache\fastf1-smoke` for
cache-only FastF1 performance evidence.
