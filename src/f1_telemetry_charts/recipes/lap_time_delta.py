"""Lap time delta chart recipe."""

from __future__ import annotations

from collections import defaultdict

from f1_telemetry_charts.charts.models import ChartSpec, SeriesSpec
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import LapRecord, SessionDataset


class LapTimeDeltaRecipe:
    recipe_id = "lap_time_delta"

    def build_spec(
        self, dataset: SessionDataset, config: ChartRecipeConfig
    ) -> ChartSpec:
        laps_by_number: dict[int, list[LapRecord]] = defaultdict(list)
        for lap in dataset.laps:
            if lap.lap_time_seconds is not None:
                laps_by_number[lap.lap_number].append(lap)

        if not laps_by_number:
            raise ValueError("lap_time_delta requires laps with lap_time_seconds")

        fastest_by_lap = {
            lap_number: min(laps, key=lambda lap: lap.lap_time_seconds or float("inf"))
            for lap_number, laps in laps_by_number.items()
        }

        driver_codes = [driver.abbreviation for driver in dataset.drivers]
        series: list[SeriesSpec] = []
        for driver_code in driver_codes:
            driver_laps = [
                lap
                for lap in dataset.laps
                if lap.driver == driver_code and lap.lap_time_seconds is not None
            ]
            if not driver_laps:
                continue
            x_values: list[float] = []
            y_values: list[float] = []
            for lap in sorted(driver_laps, key=lambda item: item.lap_number):
                fastest = fastest_by_lap.get(lap.lap_number)
                if fastest is None or fastest.lap_time_seconds is None:
                    continue
                x_values.append(float(lap.lap_number))
                y_values.append(round((lap.lap_time_seconds or 0) - fastest.lap_time_seconds, 3))
            if x_values:
                series.append(SeriesSpec(label=driver_code, x=x_values, y=y_values))

        if not series:
            raise ValueError("lap_time_delta could not build any driver series")

        metadata = dataset.metadata
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=config.title
            or f"Lap Time Delta - {metadata.season} {metadata.event} {metadata.session}",
            x_label="Lap",
            y_label="Delta to fastest on lap (s)",
            series=series,
            selected_drivers=driver_codes,
            source_session={
                "season": metadata.season,
                "event": metadata.event,
                "session": metadata.session,
            },
            warnings=[],
            metadata={
                "calculation": "lap_time_seconds minus fastest selected driver on same lap"
            },
        )
