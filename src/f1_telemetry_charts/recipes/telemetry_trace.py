"""Telemetry trace chart recipe."""

from __future__ import annotations

from f1_telemetry_charts.charts.models import ChartSpec, SeriesSpec
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import SessionDataset


class TelemetryTraceRecipe:
    recipe_id = "telemetry_trace"

    def build_spec(
        self, dataset: SessionDataset, config: ChartRecipeConfig
    ) -> ChartSpec:
        if not dataset.telemetry:
            raise ValueError("telemetry_trace requires telemetry samples")

        driver_codes = [driver.abbreviation for driver in dataset.drivers]
        series: list[SeriesSpec] = []
        for driver_code in driver_codes:
            samples = sorted(
                [sample for sample in dataset.telemetry if sample.driver == driver_code],
                key=lambda sample: (sample.lap_number, sample.distance_m),
            )
            x_values = [sample.distance_m for sample in samples if sample.speed_kph is not None]
            y_values = [sample.speed_kph for sample in samples if sample.speed_kph is not None]
            if x_values and y_values:
                series.append(SeriesSpec(label=driver_code, x=x_values, y=y_values))

        if not series:
            raise ValueError("telemetry_trace could not build any speed series")

        metadata = dataset.metadata
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=config.title
            or f"Speed Trace - {metadata.season} {metadata.event} {metadata.session}",
            x_label="Distance (m)",
            y_label="Speed (km/h)",
            series=series,
            selected_drivers=driver_codes,
            source_session={
                "season": metadata.season,
                "event": metadata.event,
                "session": metadata.session,
            },
            metadata={"metric": "speed_kph"},
        )
