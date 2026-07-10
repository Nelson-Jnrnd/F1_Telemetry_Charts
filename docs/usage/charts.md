# Chart Recipe Usage

This page is derived documentation. Authoritative requirements live in
`docs/specs/approved/SPEC-001-f1-analysis-framework.md`.

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
