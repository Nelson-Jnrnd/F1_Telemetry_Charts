"""Tyre strategy chart recipe."""

from __future__ import annotations

from f1_telemetry_charts.charts.models import ChartSpec, SeriesSpec
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import SessionDataset


COMPOUND_ORDER = {
    "HARD": 1.0,
    "MEDIUM": 2.0,
    "SOFT": 3.0,
    "INTERMEDIATE": 4.0,
    "WET": 5.0,
}


class TyreStrategyRecipe:
    recipe_id = "tyre_strategy"

    def build_spec(
        self, dataset: SessionDataset, config: ChartRecipeConfig
    ) -> ChartSpec:
        driver_codes = [driver.abbreviation for driver in dataset.drivers]
        series: list[SeriesSpec] = []
        warnings: list[str] = []

        for driver_code in driver_codes:
            laps = sorted(
                [lap for lap in dataset.laps if lap.driver == driver_code],
                key=lambda lap: lap.lap_number,
            )
            x_values: list[float] = []
            y_values: list[float] = []
            for lap in laps:
                if lap.compound is None:
                    warnings.append(f"{driver_code} lap {lap.lap_number} has no compound")
                    continue
                compound_value = COMPOUND_ORDER.get(lap.compound.upper())
                if compound_value is None:
                    warnings.append(
                        f"{driver_code} lap {lap.lap_number} has unknown compound {lap.compound}"
                    )
                    continue
                x_values.append(float(lap.lap_number))
                y_values.append(compound_value)
            if x_values:
                series.append(SeriesSpec(label=driver_code, x=x_values, y=y_values))

        if not series:
            raise ValueError("tyre_strategy requires lap compound data")

        metadata = dataset.metadata
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=config.title
            or f"Tyre Strategy - {metadata.season} {metadata.event} {metadata.session}",
            x_label="Lap",
            y_label="Compound index",
            series=series,
            selected_drivers=driver_codes,
            source_session={
                "season": metadata.season,
                "event": metadata.event,
                "session": metadata.session,
            },
            warnings=warnings,
            metadata={"compound_mapping": COMPOUND_ORDER},
        )
