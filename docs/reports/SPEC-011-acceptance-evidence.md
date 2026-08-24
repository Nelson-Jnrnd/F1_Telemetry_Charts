# SPEC-011 Acceptance Evidence

Summary: Review round five closes the remaining output-quality and provenance
gaps without changing analytical coverage. Bahrain and Belgium are
publication-ready; Austria correctly fails deleted-lap integrity and remains a
blocked QA package.

## Packages

| Category | Session | Source snapshot SHA-256 | Package SHA-256 | Automated state | Human verdict |
| --- | --- | --- | --- | --- | --- |
| Dry | 2024 Bahrain Qualifying | `7576bc2313b69aa0e45e4ad6542e16af64205fece2a28fd0b978bc40527f67f9` | `47ac00e87331c7e8c95f42594fce9969dd466972c2cb4993b93d20ec45dcc3fc` | Ready; S1 conclusion and two purposeful charts | Accepted |
| Interrupted | 2022 Austria Qualifying | `f2c972fa4d4f6d3793d19408ee674eb6ef35da26d542e5152a025c97e3846b4e` | `0afea9dbaa1dcd68a0a7e5f0b842be6edaf9aee8bd7042d3cce27ba09eb2aa13` | Blocked as expected: `Deleted lap integrity` | Accepted as the required QA block; not publishable |
| Wet | 2021 Belgium Qualifying | `5f02906ed31138f0fa85635fa01d0445db415a6403aa3666462b12cf497b3e57` | `4719182e6a638ee9f75dbf2a308df236ad1ebfa456f1103f14c981393db32910` | Ready; directional sector reversal and wet Q3 sequence | Accepted |

Package metadata records `qualifying-publication-selection:v4`, qualifying
result schema version 1, temporal-evolution policy version 2, source identity,
readiness, and the shared acceptance rubric.

## Review-round corrections

- Qualifying loads race-control messages so ordinary deleted laps and reasons
  reach the normalized lap model.
- Official segment times are reconciled against unflagged lap timing. Austria
  identifies Pérez's faster final Q2 lap and two Q3 timed laps as unresolved
  integrity conflicts and blocks readiness rather than claiming no deletions.
- Session-control timing identifies two Q3 suspensions in Austria and one in
  Belgium.
- Austria names Hamilton's Turn 7 crash and Russell's final-corner crash as the
  causes of the two Q3 red flags while retaining the Pérez integrity block.
- Belgium leads with Norris topping Q1/Q2, the wet-to-intermediate evolution,
  intensified Q3 rain, Norris's no-time crash, the long red flag, the
  intermediate restart, Russell's provisional pole, and Verstappen's 0.321s
  response. The 344-lap count remains audit metadata.
- Bahrain states the conclusion: Verstappen gained 0.227 seconds in S1 while
  Leclerc was effectively level over S2 and S3 combined.
- Progression uses session time, running bests, the competitive/cutoff
  benchmark, compound markers, rain state, and red-flag regions. Belgium's
  42-minute Q3 stoppage is compressed to a labelled two-minute display band.
- Deleted laps and integrity conflicts use separate labels, colours, and
  markers.
- Pole/cutoff margins are labelled findings; the weak separately scaled margin
  chart is not selected automatically. At a Glance contains actual findings.
- Raw traffic-proximity counts remain audit-only unless tied to a specific
  compromised valid attempt.
- Reader copy no longer contains selection/support meta-language.
- Absolute qualifying laps use motorsport `M:SS.mmm` formatting in reader and
  analyst prose while JSON evidence retains seconds.
- Belgium preserves the sector reversal: Russell gains 0.257s in S1 before
  Verstappen recovers 0.269s in S2 and 0.309s in S3.
- Source-backed Session Context is one edited canonical claim, eliminating the
  repeated Belgium paragraph and carrying Hamilton/Russell attribution into
  Austria's analyst report.
- Every package exposes editorial URLs, publication policy v4, and export
  contract v3. Ready exports include `publication-plan.json` and a manifest
  pointer; the blocked Austria QA package exposes the same metadata.
- Progression chart axes format absolute lap times as `M:SS.mmm`; chart and
  analytical metadata retain numeric seconds.

## Automated verification

- `python -m unittest discover -s tests -p "test_*.py"`: passed, 168 tests.
- `pnpm --dir frontend exec tsc --noEmit`: passed.
- `pnpm --dir frontend build`: passed; Vite emitted only the existing bundle-size
  warning.
- `python scripts/validate_governance.py`: passed.
- `python scripts/validate_specs.py`: passed for all 11 specs.
- `python scripts/validate_drift.py`: passed with the pre-existing SPEC-009
  amendment warning.
- `git diff --check`: passed with line-ending notices only.

## Browser and visual verification

- Story used qualifying-only ledes and terminology for the wet package.
- Evidence exposed the reviewed publishable claims, their comparison basis,
  chart links, and accounting for all nine independently owned results.
- Preview rendered the exported article structure at 390x844 with no horizontal
  overflow (`scrollWidth == clientWidth`).
- All three selected preview images used non-empty accessible alt text and the
  package-scoped asset route.
- Progression and sector charts were visually inspected. Progression separates
  Q1/Q2/Q3 on session time with running benchmarks and condition/interruption
  context, and the broken-axis treatment keeps Spa's competitive running
  readable; sector bars use a signed zero baseline and reconcile to the
  displayed lap margin.

## Human acceptance verdict

Nelson Jeanrenaud approved the qualifying analysis architecture on 2026-08-14
and directed closure after the final chart-axis formatting correction. Bahrain
and Belgium satisfy the shared publication rubric. Austria satisfies the
interrupted-session acceptance purpose by refusing publication on the known
Pérez deletion-integrity conflict. SPEC-011 is complete.
