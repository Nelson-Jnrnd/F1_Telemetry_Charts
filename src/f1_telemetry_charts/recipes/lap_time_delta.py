"""Lap time delta chart recipe."""

from __future__ import annotations

from collections import defaultdict

from f1_telemetry_charts.charts.models import ChartSpec, SeriesSpec
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import LapRecord, SessionDataset
from f1_telemetry_charts.recipes.parameters import (
    apply_lap_filters,
    box_lap_allowed,
    box_lap_policy,
    effective_configuration_metadata,
    effective_lap_range,
    missing_series_policy,
    parameter_value,
    selected_driver_codes,
    series_policy_action,
    series_color,
)


class LapTimeDeltaRecipe:
    recipe_id = "lap_time_delta"

    def build_spec(
        self, dataset: SessionDataset, config: ChartRecipeConfig
    ) -> ChartSpec:
        box_policy = box_lap_policy(config, default="exclude_in_and_out_laps")
        baseline_mode = str(
            parameter_value(
                config,
                "baseline_mode",
                section_name="analysis",
                default="fastest_selected_per_lap",
            )
        )
        delta_mode = str(
            parameter_value(
                config,
                "delta_mode",
                section_name="analysis",
                default="single_lap_delta",
            )
        )
        if delta_mode not in {"single_lap_delta", "cumulative_filtered_pace_delta"}:
            raise ValueError(f"lap_time_delta unsupported delta_mode: {delta_mode}")
        driver_codes = selected_driver_codes(dataset, config)
        lap_result = apply_lap_filters(
            dataset.laps,
            config,
            require_lap_time=True,
            box_policy=box_policy,
        )
        if lap_result.diagnostics.errors:
            raise ValueError(lap_result.diagnostics.errors[0]["message"])
        diagnostics = lap_result.diagnostics
        policy = missing_series_policy(config)
        laps = [
            lap
            for lap in lap_result.laps
            if lap.driver in driver_codes
        ]

        reference_driver = parameter_value(config, "reference_driver", section_name="analysis")
        if baseline_mode == "reference_driver":
            if not isinstance(reference_driver, str) or not reference_driver:
                raise ValueError("reference_driver is required when baseline_mode is reference_driver")
            if reference_driver not in driver_codes:
                raise ValueError("reference_driver must be one of the selected drivers")
        elif baseline_mode != "fastest_selected_per_lap":
            raise ValueError(f"lap_time_delta unsupported baseline_mode: {baseline_mode}")

        laps_by_number: dict[int, list[LapRecord]] = defaultdict(list)
        for lap in laps:
            if lap.lap_time_seconds is not None:
                laps_by_number[lap.lap_number].append(lap)

        if not laps_by_number:
            raise ValueError("lap_time_delta requires laps with lap_time_seconds")

        baseline_by_lap = {
            lap_number: min(laps, key=lambda lap: lap.lap_time_seconds or float("inf"))
            for lap_number, laps in laps_by_number.items()
        }
        if baseline_mode == "reference_driver":
            baseline_by_lap = {
                lap.lap_number: lap
                for lap in laps
                if lap.driver == reference_driver and lap.lap_time_seconds is not None
            }

        series: list[SeriesSpec] = []
        for driver_code in driver_codes:
            driver_laps = [
                lap
                for lap in laps
                if lap.driver == driver_code and lap.lap_time_seconds is not None
            ]
            if not driver_laps:
                series_policy_action(
                    diagnostics,
                    field_name="missing_series_policy",
                    message=f"{driver_code} has no lap-time delta series",
                    policy=policy,
                )
                continue
            x_values: list[float] = []
            y_values: list[float] = []
            cumulative_delta = 0.0
            for lap in sorted(driver_laps, key=lambda item: item.lap_number):
                baseline = baseline_by_lap.get(lap.lap_number)
                if baseline is None or baseline.lap_time_seconds is None:
                    continue
                lap_delta = round((lap.lap_time_seconds or 0) - baseline.lap_time_seconds, 3)
                if delta_mode == "cumulative_filtered_pace_delta":
                    cumulative_delta = round(cumulative_delta + lap_delta, 3)
                x_values.append(float(lap.lap_number))
                y_values.append(
                    cumulative_delta
                    if delta_mode == "cumulative_filtered_pace_delta"
                    else lap_delta
                )
            if x_values:
                series.append(
                    SeriesSpec(
                        label=driver_code,
                        x=x_values,
                        y=y_values,
                        color=series_color(config, driver_code),
                    )
                )

        if diagnostics.errors:
            raise ValueError(diagnostics.errors[0]["message"])
        if not series:
            raise ValueError("lap_time_delta could not build any driver series")

        metadata = dataset.metadata
        chart_title = parameter_value(config, "title", section_name="chart")
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=chart_title
            or f"Lap Time Delta - {metadata.season} {metadata.event} {metadata.session}",
            x_label="Lap",
            y_label=(
                "Cumulative filtered pace delta (s)"
                if delta_mode == "cumulative_filtered_pace_delta"
                else "Delta to baseline (s)"
            ),
            series=series,
            selected_drivers=driver_codes,
            source_session={
                "season": metadata.season,
                "event": metadata.event,
                "session": metadata.session,
            },
            warnings=[warning["message"] for warning in diagnostics.warnings],
            metadata={
                "baseline_mode": baseline_mode,
                "delta_mode": delta_mode,
                "reference_driver": reference_driver if baseline_mode == "reference_driver" else None,
                "include_pit_laps": box_policy == "include_all",
                "box_lap_policy": box_policy,
                "lap_range": effective_lap_range(config),
                "calculation": "lap_time_seconds minus selected baseline on same lap",
                **effective_configuration_metadata(
                    dataset,
                    config,
                    selected_drivers=driver_codes,
                    box_policy=box_policy,
                    diagnostics=diagnostics,
                    filters=lap_result.effective,
                    extra_effective={
                        "analysis": {
                            "baseline_mode": baseline_mode,
                            "delta_mode": delta_mode,
                            "missing_series_policy": policy,
                        }
                    },
                ),
            },
        )
