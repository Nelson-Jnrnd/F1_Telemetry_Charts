# Chart Recipe Usage

This page is derived documentation. Authoritative requirements live in
`docs/specs/implemented/SPEC-001-f1-analysis-framework.md`.

## Render The First Fixture-Backed Chart

```python
from pathlib import Path

from f1_telemetry_charts.charts.renderers import MatplotlibRenderer
from f1_telemetry_charts.config.models import ChartRecipeConfig, ThemeConfig
from f1_telemetry_charts.data import SessionQuery
from f1_telemetry_charts.data.gateways import FixtureSessionGateway
from f1_telemetry_charts.recipes.lap_time_delta import LapTimeDeltaRecipe

dataset = FixtureSessionGateway(
    "tests/fixtures/2023_bahrain_race_dataset.json"
).load_session(
    SessionQuery(
        season=2023,
        event="Bahrain Grand Prix",
        session="Race",
        drivers=["VER", "PER", "ALO"],
    )
)

spec = LapTimeDeltaRecipe().build_spec(
    dataset,
    ChartRecipeConfig(recipe_id="lap_time_delta"),
)

artifact = MatplotlibRenderer().render(
    spec,
    theme=ThemeConfig(),
    output_dir=Path("runs/example/charts"),
    artifact_id="lap_time_delta",
)
```

The renderer writes a PNG chart and a JSON metadata file. Batch package
orchestration and full manifests are implemented in a later MVP slice.

## Strategy templates

The seven strategy templates share the public
`f1_telemetry_charts.strategy` derivation service. Every generated strategy
artifact records schema and method versions, representative and excluded
samples, source coverage, analytical value category, warnings, and
limitations. Plugins may import this package without depending on UI or
Matplotlib modules.

`tyre_strategy` is the stable recipe id for Strategy Timeline v2. Legacy
`stint_bars` parameters map directly; the former `compound_steps` layout maps
to the timeline with an explicit migration warning.

Strategy Timeline uses one labelled row per driver, compound-coloured stint
segments, row-local pit markers, and subtle coalesced Safety Car/VSC bands. Its
compact legend orders compounds Soft, Medium, Hard and includes one triangle
key for all pit stops plus applicable race context once. Unknown compound and
source-backed retirement use distinct hatches, retirement carries a `RET`
endpoint, and missing active-stint data remains an unfilled gap. Optional
position, gap, weather, and tyre-age layers are never enabled by default.

Default strategy-template titles put the session first, for example
`2023 Bahrain GP Race Strategy`. An explicit chart title still takes priority.

Stint Pace defaults to a selected-stint-relative x-axis (`stint_progress`) and
offers tyre age or race lap as explicit alternatives. Its progression view
uses compact driver-stint labels, distinct line/marker treatments, direct
endpoint labels, and a compact in-chart count/median/IQR/median-advantage
summary. Excluded laps retain driver marker identity in a separate hollow-grey
strip, so they do not affect the representative y-axis scale. The shared
`Hollow marker = excluded lap` legend key states this convention directly;
per-lap exclusion reasons remain in artifact metadata rather than static chart
copy. Exported charts retain both direct labels and the compact legend.
Race-control bands appear only in race-lap mode when they intersect a selected
stint. Median lines, trend lines, delta panels, and extra analytical annotations
are not part of the default template.

Race-Time Delta requires explicit focal and comparator drivers; generation is
blocked when either is absent. Its default derived view is a cumulative paired
pace difference normalized to zero at the first comparison point. Measured
race-time gap change remains a separate explicit mode. Both identify the pair,
subtraction direction, sign convention, coverage breaks, pit stops, and race-
control context without exposing internal segment numbers. A thin zero line and
the concrete normalization lap make the baseline explicit. Pit markers remain
small and neutral. Artifact metadata classifies every rendered break as
`coverage_loss` or `excluded_comparison_window` and retains per-lap exclusion
reasons when available.

Pit-Cycle Comparison requires an explicit focal driver, rival, and focal
pit-in lap. It focuses on that one stop only: the title identifies its ordinal,
the primary panel compares the direct gap at the pre-stop and first eligible
post-stop reference laps, and labelled boundaries identify the references,
pit-in, and pit-out. The lower strip contains driver-labelled compound rows for
the same window with a compact compound legend. Race-control context appears
only when it intersects the focal window. If any required timing input is
missing, the primary panel shows a typed unavailable or partial state with the
exact reason; it never presents a silent empty plot or fabricates a gap.
Available results show two observed endpoints with a light dotted connector;
the connector represents endpoint-to-endpoint change, not observed intermediate
gap samples. The headline states who gained or lost relative time. Confounding
conditions remain specific warnings in metadata, and observed gap change must
not be interpreted as evidence that the pit stop caused that change.
The measured panel scales to its two endpoint values with proportional padding
and does not repeat their identity in a legend.

Driver Battle uses exactly two selected drivers and one aligned race-lap
window. Its header names the pair and reports the observed start gap, end gap,
and relative change. Representative pace lines use compact driver legend keys
plus direct endpoint labels. The middle panel always represents the absolute
direct focal-minus-rival timing gap; missing numeric paired timing produces a
typed unavailable state and never a position fallback. The lower panel uses
driver-labelled rows, one legend key per compound, stint labels with available
tyre-age ranges, and the same explicit pit markers as the other panels.

Compound Comparison uses named compound categories rather than numeric sample
positions. Each representative sample is a lightly jittered compound-coloured
point; black marks show median and IQR, and exact median, IQR, and `n` values
appear beside each category. Driver/stint identities remain in metadata rather
than the static legend. Comparable-window modes show a compound headline only
when their typed result supplies a valid scalar difference. Unrestricted or
unavailable results are labelled `Descriptive only`, making unequal sample
sizes visible without implying equal evidential weight or a compound delta.

Measured race-time gap change, derived cumulative pace difference, descriptive
compound comparisons, and reserved future estimates are different typed results.
Pit-cycle output never produces a counterfactual no-stop estimate.
