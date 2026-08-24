# SPEC-012 Acceptance Evidence

## Status

Automated implementation and verification are complete as of 2026-08-24.
Human editorial acceptance remains pending. All three real-session packages are
intentionally blocked only because the configured FastF1 source does not expose
a current official Practice classification; recorded laps are not substituted
for official order.

SPEC-012 AMEND-001 is effective: representative laps apply SPEC-008's explicit
exclusions only. No statistical outlier-removal rule is applied.

## Real-session packages

| Category | Session | Snapshot fingerprint | Results | Runs | Comparisons | Context | Package SHA-256 |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| Dry | 2024 Bahrain FP2 | `fa1f5e3f30e2a856b4c852b068c46f5b1ed148a9b5d3aaf6130d7460243a08c2` | 261 | 20 long, 2 sustained | 151 comparable, 39 unknown | dry; no interruption | `900a82cec16d37cb628a9fd9186f2e3bd3ff693f2bcacdff7a48832ff165ccd7` |
| Interrupted | 2023 Netherlands FP2 | `4f918179557512e32a4e11e9ffcb730678ce8d21ec2a83b8bdd163efda6d4094` | 234 | 17 long, 14 sustained | 13 comparable, 8 unknown, 115 confounded | dry; 1 recorded interruption | `812273e1a73306ca96d30843365eac1213454237a177d7e35b748f3fec3b92d9` |
| Wet | 2022 Japan FP2 | `6339efe9138968028182c3d88fe415ecd7b76702b18aacec53c69cc0ebe510f9` | 48 | 5 long, 6 sustained | 9 comparable, 1 unknown | mixed or wet; no interruption | `9d3737519b1b9669b6ec5c800228c95370545634716ab8333ac253abe29892e7` |

The corresponding `.zip` and `.acceptance.json` files are under
`review-packages/`. The acceptance JSON records session identity, source,
snapshot, policy versions, package hash, typed fixture metrics, readiness,
blockers, rubric, and pending human verdict.

## Automated evidence

- `tests/test_practice_report.py` covers scope, official-order non-
  reconstruction, explicit exclusions only, sustained/long-run thresholds,
  auditable samples, paired tyre-age comparability, independent context
  fingerprints, deterministic publication selection, language safety, chart
  economy, article structure, and all three chart families.
- `tests/test_fastf1_gateway.py` covers recorded tyre age and Practice
  classification mapping from source results.
- The existing workspace, findings, report, reader, API, security, and Race/
  Qualifying regression suites exercise the shared authority and export path.
- `scripts/generate_spec012_acceptance.py` creates all three packages through
  the application workflow and asserts each fixture's required material state.

## Browser and visual check

The compiled Workbench opened the dry acceptance analysis and exact current
Preview at desktop and 390x844. The preview used the Practice article order,
contained no inherited `At a Glance`, Race, or Qualifying section, and rendered
two selected 4800x2700 charts with nonempty descriptive alt text. At 390x844,
the document client and scroll widths were both 375 pixels, so no horizontal
overflow was present. The long-run chart used horizontal IQR bars, median
markers, and inverted labelled run rows.

## Validation

All commands completed successfully on 2026-08-24:

- `python scripts/validate_governance.py`
- `python scripts/validate_specs.py`
- `python scripts/validate_drift.py`
- `python -m unittest discover -s tests -p "test_*.py"` — 181 tests passed
- `npm --prefix frontend run typecheck`
- `npm --prefix frontend run build`

The drift validator retained one pre-existing non-blocking warning for
implemented SPEC-009 having no amendment entry. The production build retained
the existing Vite chunk-size advisory.

## Human acceptance

Verdict: pending.

The reviewer should apply the common rubric recorded in each acceptance JSON:
official-order handling, transparent samples, compatible comparison basis,
non-causal and non-predictive language, useful non-duplicative charts, mobile
readability, and claim-to-lap traceability. A source that supplies current
official Practice classification is also required before readiness can pass.
