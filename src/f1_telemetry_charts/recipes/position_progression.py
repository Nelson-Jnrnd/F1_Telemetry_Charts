"""Position progression chart recipe."""

from __future__ import annotations

from f1_telemetry_charts.charts.models import ChartSpec, SeriesSpec
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import SessionDataset


class PositionProgressionRecipe:
    recipe_id = "position_progression"

    def build_spec(
        self, dataset: SessionDataset, config: ChartRecipeConfig
    ) -> ChartSpec:
        driver_codes = [driver.abbreviation for driver in dataset.drivers]
        series: list[SeriesSpec] = []

        for driver_code in driver_codes:
            laps = sorted(
                [
                    lap
                    for lap in dataset.laps
                    if lap.driver == driver_code and lap.position is not None
                ],
                key=lambda lap: lap.lap_number,
            )
            if laps:
                series.append(
                    SeriesSpec(
                        label=driver_code,
                        x=[float(lap.lap_number) for lap in laps],
                        y=[float(lap.position or 0) for lap in laps],
                    )
                )

        if not series:
            raise ValueError("position_progression requires lap position data")

        metadata = dataset.metadata
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=config.title
            or f"Position Progression - {metadata.season} {metadata.event} {metadata.session}",
            x_label="Lap",
            y_label="Position",
            series=series,
            selected_drivers=driver_codes,
            source_session={
                "season": metadata.season,
                "event": metadata.event,
                "session": metadata.session,
            },
            metadata={"lower_position_is_better": True},
        )
