"""Tyre strategy chart recipe."""

from __future__ import annotations

from typing import Any

from f1_telemetry_charts.charts.models import (
    ChartSpec,
    HorizontalBarSpec,
    SeriesSpec,
    VerticalMarkerSpec,
)
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import SessionDataset
from f1_telemetry_charts.recipes.parameters import (
    apply_lap_filters,
    effective_configuration_metadata,
    effective_lap_range,
    first_diagnostic_error,
    missing_series_policy,
    parameter_value,
    resolve_compound_style,
    resolve_driver_style,
    selected_driver_codes,
    series_policy_action,
    validate_coverage_bounds,
)


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
        driver_codes = selected_driver_codes(dataset, config)
        selected_compounds = parameter_value(config, "compounds", section_name="analysis")
        layout = str(parameter_value(config, "layout", section_name="analysis", default="stint_bars"))
        if layout not in {"stint_bars", "compound_steps"}:
            raise ValueError(f"tyre_strategy unsupported layout: {layout}")
        compound_filter = (
            {str(compound).upper() for compound in selected_compounds}
            if isinstance(selected_compounds, list) and selected_compounds
            else None
        )
        show_pit_markers = bool(
            parameter_value(config, "show_pit_markers", section_name="presentation", default=True)
        )
        unknown_policy = str(
            parameter_value(
                config,
                "unknown_compound_policy",
                section_name="analysis",
                default="warn_skip",
            )
        )
        series: list[SeriesSpec] = []
        horizontal_bars: list[HorizontalBarSpec] = []
        vertical_markers: list[VerticalMarkerSpec] = []
        warnings: list[str] = []
        pit_marker_laps: dict[str, list[int]] = {}
        lap_result = apply_lap_filters(dataset.laps, config)
        coverage = validate_coverage_bounds(
            dataset,
            config,
            selected_drivers=driver_codes,
            diagnostics=lap_result.diagnostics,
        )
        if lap_result.diagnostics.errors:
            raise ValueError(first_diagnostic_error(lap_result.diagnostics))
        diagnostics = lap_result.diagnostics
        policy = missing_series_policy(config)
        style_sources: dict[str, dict[str, Any]] = {"drivers": {}, "compounds": {}}

        for driver_index, driver_code in enumerate(driver_codes, start=1):
            driver_style = resolve_driver_style(dataset, config, driver_code, diagnostics)
            style_sources["drivers"][driver_code] = driver_style.as_metadata()
            laps = sorted(
                [lap for lap in lap_result.laps if lap.driver == driver_code],
                key=lambda lap: lap.lap_number,
            )
            x_values: list[float] = []
            y_values: list[float] = []
            stint_start: int | None = None
            stint_compound: str | None = None
            for lap in laps:
                if show_pit_markers and (lap.is_pit_in_lap or lap.is_pit_out_lap):
                    pit_marker_laps.setdefault(driver_code, []).append(lap.lap_number)
                    vertical_markers.append(
                        VerticalMarkerSpec(
                            x=float(lap.lap_number),
                            color=driver_style.color,
                            alpha=0.25,
                        )
                    )
                if lap.compound is None:
                    warnings.append(f"{driver_code} lap {lap.lap_number} has no compound")
                    continue
                if compound_filter is not None and lap.compound.upper() not in compound_filter:
                    continue
                compound_value = COMPOUND_ORDER.get(lap.compound.upper())
                if compound_value is None:
                    series_policy_action(
                        diagnostics,
                        field_name="unknown_compound_policy",
                        message=f"{driver_code} lap {lap.lap_number} has unknown compound {lap.compound}",
                        policy=unknown_policy,
                    )
                    continue
                compound_key = lap.compound.upper()
                if compound_key not in style_sources["compounds"]:
                    compound_style = resolve_compound_style(
                        dataset,
                        config,
                        compound_key,
                        diagnostics,
                    )
                    style_sources["compounds"][compound_key] = (
                        compound_style.as_metadata()
                    )
                x_values.append(float(lap.lap_number))
                y_values.append(compound_value)
                if layout == "stint_bars":
                    if stint_compound is None:
                        stint_start = lap.lap_number
                        stint_compound = lap.compound.upper()
                    elif stint_compound != lap.compound.upper():
                        if stint_start is not None:
                            horizontal_bars.append(
                                _stint_bar(
                                    driver_index=driver_index,
                                    driver_code=driver_code,
                                    start=stint_start,
                                    end=lap.lap_number - 1,
                                    compound=stint_compound,
                                    color=str(style_sources["compounds"][stint_compound]["color"]),
                                )
                            )
                        stint_start = lap.lap_number
                        stint_compound = lap.compound.upper()
            if layout == "stint_bars" and stint_start is not None and stint_compound is not None:
                horizontal_bars.append(
                    _stint_bar(
                        driver_index=driver_index,
                        driver_code=driver_code,
                        start=stint_start,
                        end=laps[-1].lap_number,
                        compound=stint_compound,
                        color=str(style_sources["compounds"][stint_compound]["color"]),
                    )
                )
            if x_values:
                if layout == "compound_steps":
                    series.append(
                        SeriesSpec(
                            label=driver_code,
                            x=x_values,
                            y=y_values,
                            color=driver_style.color,
                            render_mode="step",
                        )
                    )
            else:
                series_policy_action(
                    diagnostics,
                    field_name="missing_series_policy",
                    message=f"{driver_code} has no tyre strategy series",
                    policy=policy,
                )

        if diagnostics.errors:
            raise ValueError(first_diagnostic_error(diagnostics))
        if not series and not horizontal_bars:
            raise ValueError("tyre_strategy requires lap compound data")
        warnings.extend(warning["message"] for warning in diagnostics.warnings)

        metadata = dataset.metadata
        chart_title = parameter_value(config, "title", section_name="chart")
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=chart_title
            or f"Tyre Strategy - {metadata.season} {metadata.event} {metadata.session}",
            x_label="Lap",
            y_label="Driver" if layout == "stint_bars" else "Compound index",
            series=series,
            selected_drivers=driver_codes,
            source_session={
                "season": metadata.season,
                "event": metadata.event,
                "session": metadata.session,
            },
            warnings=warnings,
            vertical_markers=vertical_markers if show_pit_markers else [],
            horizontal_bars=horizontal_bars if layout == "stint_bars" else [],
            metadata={
                "compound_mapping": COMPOUND_ORDER,
                "layout": layout,
                "compounds": sorted(compound_filter) if compound_filter is not None else None,
                "show_pit_markers": show_pit_markers,
                "pit_marker_laps": pit_marker_laps if show_pit_markers else {},
                "lap_range": effective_lap_range(config),
                "y_axis_labels": {
                    str(index): driver for index, driver in enumerate(driver_codes, start=1)
                },
                **effective_configuration_metadata(
                    dataset,
                    config,
                    selected_drivers=driver_codes,
                    diagnostics=diagnostics,
                    filters=lap_result.effective,
                    coverage=coverage,
                    style_sources=style_sources,
                    extra_effective={
                        "analysis": {
                            "layout": layout,
                            "unknown_compound_policy": unknown_policy,
                            "missing_series_policy": policy,
                        }
                    },
                ),
            },
        )


def _stint_bar(
    *,
    driver_index: int,
    driver_code: str,
    start: int,
    end: int,
    compound: str,
    color: str | None,
) -> HorizontalBarSpec:
    return HorizontalBarSpec(
        y=float(driver_index),
        x_start=float(start),
        x_end=float(end + 1),
        label=f"{driver_code} {compound}",
        color=color,
    )
