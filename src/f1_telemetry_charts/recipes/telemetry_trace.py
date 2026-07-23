"""Telemetry trace chart recipe."""

from __future__ import annotations

from f1_telemetry_charts.charts.models import ChartSpec, SeriesSpec
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import SessionDataset
from f1_telemetry_charts.recipes.parameters import (
    apply_lap_filters,
    filter_telemetry,
    effective_configuration_metadata,
    effective_lap_range,
    missing_series_policy,
    numeric_range_contains,
    parameter_value,
    selected_driver_codes,
    series_policy_action,
    series_color,
    telemetry_gap_policy,
)


METRIC_LABELS = {
    "speed_kph": ("Speed (km/h)", "speed_kph"),
    "throttle_percent": ("Throttle (%)", "throttle_percent"),
    "brake": ("Brake", "brake"),
    "gear": ("Gear", "gear"),
}


class TelemetryTraceRecipe:
    recipe_id = "telemetry_trace"

    def build_spec(
        self, dataset: SessionDataset, config: ChartRecipeConfig
    ) -> ChartSpec:
        if not dataset.telemetry:
            raise ValueError("telemetry_trace requires telemetry samples")

        metric = str(parameter_value(config, "metric", section_name="analysis", default="speed_kph"))
        if metric not in METRIC_LABELS:
            raise ValueError(f"telemetry_trace unsupported metric: {metric}")
        gap_policy = telemetry_gap_policy(config, metric)
        y_label, attribute = METRIC_LABELS[metric]
        distance_range = parameter_value(config, "distance_range_m", section_name="analysis")
        driver_codes = selected_driver_codes(dataset, config)
        lap_result = apply_lap_filters(dataset.laps, config)
        if lap_result.diagnostics.errors:
            raise ValueError(lap_result.diagnostics.errors[0]["message"])
        diagnostics = lap_result.diagnostics
        policy = missing_series_policy(config)
        allowed_laps = {
            (lap.driver, lap.lap_number)
            for lap in lap_result.laps
            if lap.driver in driver_codes
        }
        telemetry = [
            sample
            for sample in filter_telemetry(dataset.telemetry, config)
            if (sample.driver, sample.lap_number) in allowed_laps
        ]
        series: list[SeriesSpec] = []
        for driver_code in driver_codes:
            samples = sorted(
                [
                    sample
                    for sample in telemetry
                    if sample.driver == driver_code
                    and numeric_range_contains(
                        sample.distance_m,
                        distance_range,
                        parameter_name="distance_range_m",
                    )
                ],
                key=lambda sample: (sample.lap_number, sample.distance_m),
            )
            x_values: list[float] = []
            y_values: list[float] = []
            for sample in samples:
                raw_value = getattr(sample, attribute)
                if raw_value is None:
                    continue
                x_values.append(sample.distance_m)
                y_values.append(float(raw_value))
            if x_values and y_values:
                series.append(
                    SeriesSpec(
                        label=driver_code,
                        x=x_values,
                        y=y_values,
                        color=series_color(config, driver_code),
                    )
                )
            else:
                series_policy_action(
                    diagnostics,
                    field_name="missing_series_policy",
                    message=f"{driver_code} has no telemetry series for {metric}",
                    policy=policy,
                )

        if diagnostics.errors:
            raise ValueError(diagnostics.errors[0]["message"])
        if not series:
            raise ValueError(f"telemetry_trace could not build any {metric} series")

        metadata = dataset.metadata
        chart_title = parameter_value(config, "title", section_name="chart")
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=chart_title
            or f"{y_label} Trace - {metadata.season} {metadata.event} {metadata.session}",
            x_label="Distance (m)",
            y_label=y_label,
            series=series,
            selected_drivers=driver_codes,
            source_session={
                "season": metadata.season,
                "event": metadata.event,
                "session": metadata.session,
            },
            warnings=[warning["message"] for warning in diagnostics.warnings],
            metadata={
                "metric": metric,
                "lap_range": effective_lap_range(config),
                "distance_range_m": distance_range,
                **effective_configuration_metadata(
                    dataset,
                    config,
                    selected_drivers=driver_codes,
                    diagnostics=diagnostics,
                    filters=lap_result.effective,
                    extra_effective={
                        "analysis": {
                            "metric": metric,
                            "telemetry_gap_policy": gap_policy,
                            "missing_series_policy": policy,
                        }
                    },
                ),
            },
        )
