"""Position progression chart recipe."""

from __future__ import annotations

from f1_telemetry_charts.charts.models import ChartSpec, SeriesSpec
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import SessionDataset
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


class PositionProgressionRecipe:
    recipe_id = "position_progression"

    def build_spec(
        self, dataset: SessionDataset, config: ChartRecipeConfig
    ) -> ChartSpec:
        driver_codes = selected_driver_codes(dataset, config)
        box_policy = box_lap_policy(config, default="exclude_in_and_out_laps")
        invert_position_axis = bool(
            parameter_value(
                config,
                "invert_position_axis",
                section_name="presentation",
                default=True,
            )
        )
        line_mode = str(
            parameter_value(
                config,
                "line_mode",
                section_name="presentation",
                default="step",
            )
        )
        if line_mode not in {"step", "line"}:
            raise ValueError(f"position_progression unsupported line_mode: {line_mode}")
        series: list[SeriesSpec] = []
        lap_result = apply_lap_filters(
            dataset.laps,
            config,
            box_policy=box_policy,
        )
        if lap_result.diagnostics.errors:
            raise ValueError(lap_result.diagnostics.errors[0]["message"])
        diagnostics = lap_result.diagnostics
        policy = missing_series_policy(config)

        for driver_code in driver_codes:
            laps = sorted(
                [
                    lap
                    for lap in lap_result.laps
                    if lap.driver == driver_code and lap.position is not None
                ],
                key=lambda lap: lap.lap_number,
            )
            if laps:
                y_values = [float(lap.position or 0) for lap in laps]
                series.append(
                    SeriesSpec(
                        label=driver_code,
                        x=[float(lap.lap_number) for lap in laps],
                        y=y_values,
                        color=series_color(config, driver_code),
                        render_mode=line_mode,
                    )
                )
            else:
                series_policy_action(
                    diagnostics,
                    field_name="missing_series_policy",
                    message=f"{driver_code} has no position progression series",
                    policy=policy,
                )

        if diagnostics.errors:
            raise ValueError(diagnostics.errors[0]["message"])
        if not series:
            raise ValueError("position_progression requires lap position data")

        metadata = dataset.metadata
        chart_title = parameter_value(config, "title", section_name="chart")
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=chart_title
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
            warnings=[warning["message"] for warning in diagnostics.warnings],
            y_axis_inverted=invert_position_axis,
            metadata={
                "lower_position_is_better": True,
                "invert_position_axis": invert_position_axis,
                "include_pit_laps": box_policy == "include_all",
                "box_lap_policy": box_policy,
                "lap_range": effective_lap_range(config),
                **effective_configuration_metadata(
                    dataset,
                    config,
                    selected_drivers=driver_codes,
                    box_policy=box_policy,
                    diagnostics=diagnostics,
                    filters=lap_result.effective,
                    extra_effective={
                        "analysis": {
                            "position_source": "lap_end_running_position",
                            "line_mode": line_mode,
                            "missing_series_policy": policy,
                        }
                    },
                ),
            },
        )
