"""Thin chart recipes backed by the shared strategy-analysis contract."""

from __future__ import annotations

from collections import defaultdict
from statistics import median
from typing import Any, Literal

from f1_telemetry_charts.strategy import (
    compare_compounds,
    compare_pit_cycle,
    descriptive_statistics,
    derive_strategy_analysis,
    race_time_delta,
    strategy_metadata,
    strategy_policy_from_parameters,
)
from f1_telemetry_charts.strategy import StrategyAnalysisResult, StrategyLap
from f1_telemetry_charts.charts.models import (
    BoxSummarySpec,
    ChartSpec,
    HorizontalMarkerSpec,
    HorizontalBarSpec,
    InfoBlockSpec,
    PanelSpec,
    SeriesSpec,
    ShadedRegionSpec,
    TextAnnotationSpec,
    VerticalMarkerSpec,
)
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import SessionDataset
from f1_telemetry_charts.recipes.parameters import (
    ParameterDiagnostics,
    effective_configuration_metadata,
    effective_lap_range,
    parameter_value,
    resolve_compound_style,
    resolve_driver_style,
    selected_driver_codes,
)


STRATEGY_RECIPE_IDS = (
    "tyre_strategy",
    "stint_pace",
    "pace_evolution",
    "compound_comparison",
    "race_time_delta_evolution",
    "pit_cycle_comparison",
    "driver_battle",
)


class StrategyTimelineRecipe:
    """Strategy Timeline v2 under the stable legacy ``tyre_strategy`` id."""

    recipe_id = "tyre_strategy"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        context = _context(dataset, config, maximum_drivers=20)
        selected_compounds = parameter_value(
            config, "compounds", section_name="analysis", default=[]
        )
        compound_filter = (
            {str(value).upper() for value in selected_compounds}
            if isinstance(selected_compounds, list) and selected_compounds
            else None
        )
        laps = [
            lap
            for lap in context.laps
            if compound_filter is None or lap.compound in compound_filter
        ]
        bars: list[HorizontalBarSpec] = []
        compounds: dict[str, dict[str, Any]] = {}
        pit_marker_laps: dict[str, list[int]] = defaultdict(list)
        driver_index = {driver: index for index, driver in enumerate(context.drivers)}
        compound_legend_seen: set[str] = set()
        conflict_legend_seen = False
        for driver in context.drivers:
            driver_laps = sorted(
                (lap for lap in laps if lap.driver == driver),
                key=lambda lap: lap.lap_number,
            )
            for segment in _timeline_stint_segments(driver_laps):
                compound = segment[0].compound or "UNKNOWN"
                if compound not in compounds:
                    style = resolve_compound_style(
                        dataset, config, compound, context.diagnostics
                    )
                    compounds[compound] = style.as_metadata()
                conflicting = any(lap.stint_source == "conflicting" for lap in segment)
                label: str | None = None
                if compound not in compound_legend_seen:
                    label = "Unknown compound" if compound == "UNKNOWN" else compound.title()
                    compound_legend_seen.add(compound)
                elif conflicting and not conflict_legend_seen:
                    label = "Conflicting stint"
                if conflicting:
                    conflict_legend_seen = True
                bars.append(
                    HorizontalBarSpec(
                        y=float(driver_index[driver]),
                        x_start=float(segment[0].lap_number),
                        x_end=float(segment[-1].lap_number + 1),
                        label=label,
                        color=(
                            "#B8BEC5"
                            if compound == "UNKNOWN"
                            else "#CBD5E1"
                            if compound == "HARD"
                            else compounds[compound]["color"]
                        ),
                        alpha=0.95,
                        edge_color="#475569",
                        hatch=("///" if compound == "UNKNOWN" else "xx" if conflicting else None),
                    )
                )
            if context.show_pit_markers:
                pit_marker_laps[driver].extend(_pit_event_laps(driver_laps))

        race_end_lap = max((lap.lap_number for lap in laps), default=0)
        retirement_annotations: list[TextAnnotationSpec] = []
        driver_metadata = {driver.abbreviation: driver for driver in dataset.drivers}
        for driver in context.drivers:
            driver_laps = [lap for lap in laps if lap.driver == driver]
            last_lap = max((lap.lap_number for lap in driver_laps), default=0)
            metadata_driver = driver_metadata.get(driver)
            if (
                metadata_driver is not None
                and _is_retirement_status(metadata_driver.result_status)
                and 0 < last_lap < race_end_lap
            ):
                bars.append(
                    HorizontalBarSpec(
                        y=float(driver_index[driver]),
                        x_start=float(last_lap + 1),
                        x_end=float(race_end_lap + 1),
                        label=None,
                        color="#F3F4F6",
                        alpha=1.0,
                        edge_color="#6B7280",
                        hatch="\\\\",
                    )
                )
                retirement_annotations.append(
                    TextAnnotationSpec(
                        x=float(last_lap + 1.15),
                        y=float(driver_index[driver]),
                        text="RET",
                        color="#991B1B",
                        font_size=8,
                        font_weight="bold",
                    )
                )
        pit_series = _pit_marker_series(pit_marker_laps, driver_index)
        metadata = context.metadata(
            result_kind="strategy_timeline",
            results={
                "template_version": 2,
                "stable_recipe_id": self.recipe_id,
                "value_category": "descriptive",
                "status": "available" if bars else "unavailable",
                "legacy_migration": context.legacy_migration,
                "driver_order": context.drivers,
                "compound_styles": compounds,
            },
            extra_effective={
                "analysis": {
                    "presentation_mode": "strategy_timeline",
                    "context_layer": context.context_layer,
                }
            },
        )
        metadata["y_axis_labels"] = {
            str(index): driver for driver, index in driver_index.items()
        }
        metadata["compounds"] = sorted(compound_filter) if compound_filter is not None else None
        metadata["show_pit_markers"] = context.show_pit_markers
        metadata["pit_marker_laps"] = {
            driver: values for driver, values in sorted(pit_marker_laps.items())
        }
        metadata["layout"] = "stint_bars"
        metadata.setdefault("style_sources", {})["compounds"] = compounds
        panels = _timeline_panels(
            dataset,
            context,
            bars=bars,
            pit_series=pit_series,
            retirement_annotations=retirement_annotations,
            context_layer=context.context_layer,
        )
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=_title(config, dataset, "Strategy Timeline"),
            x_label="Race lap",
            y_label="Driver",
            selected_drivers=context.drivers,
            source_session=dataset.metadata.model_dump(mode="json"),
            warnings=context.warning_messages,
            series=[] if panels else pit_series,
            horizontal_bars=[] if panels else bars,
            shaded_regions=[] if panels else _race_context_regions(laps),
            annotations=[] if panels else retirement_annotations,
            y_tick_labels={} if panels else {float(index): driver for driver, index in driver_index.items()},
            y_axis_inverted=not bool(panels),
            panels=panels,
            metadata=metadata,
        )


class StintPaceRecipe:
    recipe_id = "stint_pace"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        context = _context(dataset, config)
        selected_stints = _selected_stints(context.analysis, context.drivers, config)
        presentation = str(
            parameter_value(config, "presentation_mode", section_name="presentation", default="progression")
        )
        if presentation == "progression" and len(selected_stints) > 4:
            raise ValueError("Stint Pace supports at most four driver-stints per progression chart")
        reference_driver = _driver_value(
            parameter_value(config, "reference_driver", section_name="analysis")
        )
        x_axis_basis = str(
            parameter_value(
                config,
                "x_axis_basis",
                section_name="presentation",
                default="stint_progress",
            )
        )
        if x_axis_basis not in {"stint_progress", "tyre_age", "race_lap"}:
            raise ValueError(f"Unsupported Stint Pace x-axis basis: {x_axis_basis}")
        reference_laps = {
            lap.lap_number: lap
            for lap in context.laps
            if lap.driver == reference_driver
            and lap.is_representative_for_pace
            and lap.lap_time_seconds is not None
        }
        series: list[SeriesSpec] = []
        summary_bars: list[HorizontalBarSpec] = []
        annotations: list[TextAnnotationSpec] = []
        selected_laps: list[StrategyLap] = []
        plotted_x_values: list[float] = []
        line_styles = ("-", "--", "-.", ":")
        markers = ("o", "s", "^", "D")
        summary_rows: list[dict[str, Any]] = []
        summary_tick_labels: dict[float, str] = {}
        if presentation == "consistency_summary":
            selected_stints = sorted(
                selected_stints,
                key=lambda item: (
                    item.statistics.median is None,
                    item.statistics.median or float("inf"),
                    item.driver,
                    item.effective_stint,
                ),
            )
        for summary_index, summary in enumerate(selected_stints):
            label = f"{summary.driver} S{summary.effective_stint}"
            style = context.driver_styles[summary.driver]
            group = [
                lap
                for lap in context.laps
                if lap.driver == summary.driver and lap.effective_stint == summary.effective_stint
            ]
            selected_laps.extend(group)
            representative = [lap for lap in group if lap.is_representative_for_pace and lap.lap_time_seconds is not None]
            excluded = [lap for lap in group if not lap.is_representative_for_pace and lap.lap_time_seconds is not None]
            summary_rows.append(
                {
                    "label": label,
                    "driver": summary.driver,
                    "stint": summary.effective_stint,
                    "compound": summary.compound,
                    "representative_lap_count": summary.representative_lap_count,
                    "median_seconds": summary.statistics.median,
                    "iqr_seconds": summary.statistics.iqr,
                }
            )
            if presentation == "consistency_summary":
                if summary.statistics.median is not None:
                    row = float(summary_index)
                    summary_tick_labels[row] = label
                    series.append(
                        SeriesSpec(
                            label="dot = median" if summary_index == 0 else None,
                            x=[summary.statistics.median],
                            y=[row],
                            color=style["color"],
                            edge_color="#FFFFFF",
                            render_mode="scatter",
                            marker_size=110,
                        )
                    )
                    if summary.statistics.minimum is not None and summary.statistics.maximum is not None:
                        summary_bars.append(
                            HorizontalBarSpec(
                                y=row,
                                x_start=summary.statistics.minimum,
                                x_end=summary.statistics.maximum,
                                label="light band = min/max" if summary_index == 0 else None,
                                color=style["color"],
                                alpha=0.12,
                                height=0.06,
                            )
                        )
                    if summary.statistics.q1 is not None and summary.statistics.q3 is not None:
                        summary_bars.append(
                            HorizontalBarSpec(
                                y=row,
                                x_start=summary.statistics.q1,
                                x_end=summary.statistics.q3,
                                label="dark band = IQR" if summary_index == 0 else None,
                                color=style["color"],
                                alpha=0.62,
                                height=0.12,
                            )
                        )
            else:
                plotted = [
                    lap
                    for lap in representative
                    if (reference_driver is None or lap.lap_number in reference_laps)
                    and _stint_pace_x(lap, x_axis_basis) is not None
                ]
                for segment_index, segment in enumerate(_strategy_lap_segments(plotted)):
                    x_values = [float(_stint_pace_x(lap, x_axis_basis) or 0.0) for lap in segment]
                    y_values = [
                        _stint_pace_y(lap, reference_driver, reference_laps)
                        for lap in segment
                    ]
                    plotted_x_values.extend(x_values)
                    series.append(
                        SeriesSpec(
                            label=label if segment_index == 0 else None,
                            x=x_values,
                            y=y_values,
                            color=style["color"],
                            line_style=line_styles[summary_index % len(line_styles)],
                            marker=markers[summary_index % len(markers)],
                            marker_size=28,
                        )
                    )
                eligible_excluded = [
                    lap
                    for lap in excluded
                    if _stint_pace_x(lap, x_axis_basis) is not None
                    and (reference_driver is None or lap.lap_number in reference_laps)
                ]
                if eligible_excluded:
                    series.append(
                        SeriesSpec(
                            label="Hollow marker = excluded lap" if summary_index == 0 else None,
                            x=[
                                float(_stint_pace_x(lap, x_axis_basis) or 0.0)
                                for lap in eligible_excluded
                            ],
                            y=[float(summary_index)] * len(eligible_excluded),
                            color="#6B7280",
                            render_mode="excluded_strip",
                            marker=markers[summary_index % len(markers)],
                            marker_size=36,
                        )
                    )
                plotted_x_values.extend(
                    float(_stint_pace_x(lap, x_axis_basis) or 0.0)
                    for lap in eligible_excluded
                )
                if plotted:
                    final = plotted[-1]
                    annotations.append(
                        TextAnnotationSpec(
                            x=float(_stint_pace_x(final, x_axis_basis) or 0.0),
                            y=_stint_pace_y(final, reference_driver, reference_laps),
                            text=f"  {label}",
                            color=style["color"],
                            font_size=8,
                            font_weight="bold",
                        )
                    )
        median_delta_seconds: float | None = None
        if (
            len(summary_rows) == 2
            and summary_rows[0]["median_seconds"] is not None
            and summary_rows[1]["median_seconds"] is not None
        ):
            median_delta_seconds = float(summary_rows[0]["median_seconds"]) - float(
                summary_rows[1]["median_seconds"]
            )
        summary_lines = _stint_pace_summary_lines(
            summary_rows,
            median_delta_seconds=median_delta_seconds,
        )
        subtitle = _stint_pace_subtitle(summary_rows)
        x_limits = _stint_pace_x_limits(plotted_x_values) if presentation != "consistency_summary" else None
        results = {
            "value_category": "descriptive",
            "presentation_mode": presentation,
            "metric": "same_lap_delta" if reference_driver else "representative_lap_time",
            "reference_driver": reference_driver,
            "x_axis_basis": x_axis_basis,
            "comparison_summary": {
                "stints": summary_rows,
                "median_delta_seconds": median_delta_seconds,
                "median_delta_sign_convention": (
                    f"{summary_rows[0]['label']} minus {summary_rows[1]['label']}"
                    if len(summary_rows) == 2
                    else None
                ),
            },
            "availability": {
                f"{summary.driver}:S{summary.effective_stint}": (
                    "available"
                    if summary.representative_lap_count
                    >= int(parameter_value(config, "minimum_samples", section_name="analysis", default=3))
                    else "insufficient_sample"
                )
                for summary in selected_stints
            },
            "stints": [summary.model_dump(mode="json") for summary in selected_stints],
        }
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=_title(
                config,
                dataset,
                "Stint Pace Summary" if presentation == "consistency_summary" else "Stint Pace",
            ),
            subtitle=subtitle,
            x_label=(
                "Representative lap time (s)"
                if presentation == "consistency_summary"
                else "Stint lap"
                if x_axis_basis == "stint_progress"
                else "Tyre age (laps)"
                if x_axis_basis == "tyre_age"
                else "Race lap"
            ),
            y_label=(
                ""
                if presentation == "consistency_summary"
                else f"Same-lap delta to {reference_driver} (s)"
                if reference_driver
                else "Representative lap time (s)"
            ),
            selected_drivers=context.drivers,
            source_session=dataset.metadata.model_dump(mode="json"),
            warnings=context.warning_messages,
            series=series,
            annotations=annotations,
            y_tick_labels=summary_tick_labels,
            y_axis_inverted=presentation == "consistency_summary",
            horizontal_bars=summary_bars,
            shaded_regions=(
                _race_context_regions(selected_laps)
                if presentation != "consistency_summary" and x_axis_basis == "race_lap"
                else []
            ),
            summary_lines=summary_lines,
            x_limits=x_limits,
            y_limits=(
                (-0.35, float(len(summary_tick_labels)) - 0.65)
                if presentation == "consistency_summary" and summary_tick_labels
                else None
            ),
            legend_order=(
                ["dot = median", "dark band = IQR", "light band = min/max"]
                if presentation == "consistency_summary"
                else [
                    *[row["label"] for row in summary_rows],
                    "Hollow marker = excluded lap",
                ]
            ),
            legend_location="upper right",
            metadata=context.metadata(
                result_kind="stint_pace",
                results=results,
                extra_effective={
                    "presentation": {
                        "presentation_mode": presentation,
                        "x_axis_basis": x_axis_basis,
                    }
                },
            ),
        )


class PaceEvolutionRecipe:
    recipe_id = "pace_evolution"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        context = _context(dataset, config)
        selected_stints = _selected_stints(context.analysis, context.drivers, config)
        if len(selected_stints) > 4:
            raise ValueError("Pace Evolution supports at most four driver-stints per chart")
        mode = str(parameter_value(config, "evolution_mode", section_name="analysis", default="lap_time"))
        selected_bases = {summary.pace_evolution.basis for summary in selected_stints}
        if len(selected_bases) > 1:
            raise ValueError("Tyre-age and stint-progress results require separate chart instances")
        series: list[SeriesSpec] = []
        annotations: list[TextAnnotationSpec] = []
        summary_lines: list[str] = []
        sector_series: dict[int, list[SeriesSpec]] = {1: [], 2: [], 3: []}
        sector_annotations: dict[int, list[TextAnnotationSpec]] = {1: [], 2: [], 3: []}
        sector_summary_lines: dict[int, list[str]] = {1: [], 2: [], 3: []}
        sector_y_values: list[float] = []
        sector_x_values: list[float] = []
        line_styles = ("-", "--", "-.", ":")
        markers = ("o", "s", "^", "D")
        driver_treatments = {
            driver: (
                line_styles[index % len(line_styles)],
                markers[index % len(markers)],
            )
            for index, driver in enumerate(context.drivers)
        }
        stint_count_by_driver = {
            driver: sum(1 for summary in selected_stints if summary.driver == driver)
            for driver in context.drivers
        }
        for summary in selected_stints:
            fit = summary.pace_evolution
            group = [
                lap
                for lap in context.laps
                if lap.driver == summary.driver
                and lap.effective_stint == summary.effective_stint
                and lap.is_representative_for_pace
                and lap.lap_time_seconds is not None
            ]
            style = context.driver_styles[summary.driver]
            label = (
                summary.driver
                if stint_count_by_driver.get(summary.driver, 0) == 1
                else f"{summary.driver} S{summary.effective_stint}"
            )
            line_style, marker = driver_treatments[summary.driver]
            x_values = [
                float(lap.tyre_age if fit.basis == "tyre_age" else lap.stint_progress or 0)
                for lap in group
                if fit.basis != "tyre_age" or lap.tyre_age is not None
            ]
            if mode == "sector_evolution":
                for sector in summary.sector_evolution:
                    values = [
                        (lap, getattr(lap, f"sector_{sector.sector}_time_seconds"))
                        for lap in group
                        if getattr(lap, f"sector_{sector.sector}_time_seconds") is not None
                        and (fit.basis != "tyre_age" or lap.tyre_age is not None)
                    ]
                    if values:
                        baseline = float(values[0][1] or 0.0)
                        sector_x = [
                            float(
                                lap.tyre_age
                                if sector.fit.basis == "tyre_age"
                                else lap.stint_progress or 0
                            )
                            for lap, _ in values
                        ]
                        sector_y = [float(value or 0.0) - baseline for _, value in values]
                        sector_x_values.extend(sector_x)
                        sector_y_values.extend(sector_y)
                        sector_series[sector.sector].append(
                            SeriesSpec(
                                label=None,
                                x=sector_x,
                                y=sector_y,
                                color=style["color"],
                                render_mode="scatter",
                                marker=marker,
                                marker_size=28,
                            )
                        )
                        sector_fit = sector.fit
                        if (
                            sector_fit.status == "available"
                            and sector_fit.slope is not None
                            and sector_fit.intercept is not None
                        ):
                            fit_x = [min(sector_x), max(sector_x)]
                            fit_y = [
                                sector_fit.slope * x + sector_fit.intercept - baseline
                                for x in fit_x
                            ]
                            sector_y_values.extend(fit_y)
                            sector_series[sector.sector].append(
                                SeriesSpec(
                                    label=None,
                                    x=fit_x,
                                    y=fit_y,
                                    color=style["color"],
                                    line_style=line_style,
                                )
                            )
                            sector_annotations[sector.sector].append(
                                TextAnnotationSpec(
                                    x=fit_x[-1],
                                    y=fit_y[-1],
                                    text=f"  {label}",
                                    color=style["color"],
                                    font_size=8,
                                    font_weight="bold",
                                )
                            )
                            sector_summary_lines[sector.sector].append(
                                f"{label}: {sector_fit.slope:+.3f} s/lap, "
                                f"n={sector_fit.sample_count}, quality={sector_fit.quality}"
                            )
                        else:
                            sector_summary_lines[sector.sector].append(
                                f"{label}: fit unavailable, n={sector_fit.sample_count}, "
                                f"quality={sector_fit.quality}"
                            )
                continue
            y_values = [
                float(lap.lap_time_seconds or 0.0)
                for lap in group
                if fit.basis != "tyre_age" or lap.tyre_age is not None
            ]
            series.append(
                SeriesSpec(
                    label=None,
                    x=x_values,
                    y=y_values,
                    color=style["color"],
                    render_mode="scatter",
                    marker=marker,
                    marker_size=28,
                )
            )
            if fit.status == "available" and fit.slope is not None and fit.intercept is not None and x_values:
                fit_x = [min(x_values), max(x_values)]
                fit_y = [fit.slope * x + fit.intercept for x in fit_x]
                series.append(
                    SeriesSpec(
                        label=None,
                        x=fit_x,
                        y=fit_y,
                        color=style["color"],
                        line_style=line_style,
                    )
                )
                annotations.append(
                    TextAnnotationSpec(
                        x=fit_x[-1],
                        y=fit_y[-1],
                        text=f"  {label}",
                        color=style["color"],
                        font_size=8,
                        font_weight="bold",
                    )
                )
                summary_lines.append(
                    f"{label}: {fit.slope:+.3f} s/lap, "
                    f"n={fit.sample_count}, quality={fit.quality}"
                )
            else:
                summary_lines.append(
                    f"{label}: fit unavailable, n={fit.sample_count}, "
                    f"quality={fit.quality}"
                )
        basis = next(iter(selected_bases), "stint_progress")
        subtitle = (
            "Evolution shown against source tyre age. "
            "Markers = representative samples; lines = observed fits."
            if basis == "tyre_age"
            else "Tyre age unavailable; evolution shown against stint progress. "
            "Markers = representative samples; lines = observed fits."
        )
        results = {
            "value_category": "derived",
            "result_kind": "observed_sector_time_evolution" if mode == "sector_evolution" else "observed_pace_evolution",
            "evolution_mode": mode,
            "stints": [summary.model_dump(mode="json") for summary in selected_stints],
        }
        sector_y_limits = _padded_limits(sector_y_values, minimum_padding=0.03)
        sector_x_limits = _padded_limits(sector_x_values, minimum_padding=0.25)
        sector_context = " vs ".join(
            f"{summary.driver} S{summary.effective_stint}" for summary in selected_stints
        )
        sector_compounds = sorted(
            {summary.compound.title() for summary in selected_stints if summary.compound}
        )
        sector_subtitle = (
            f"{sector_context}, "
            f"{('/'.join(sector_compounds) + ', ') if sector_compounds else ''}"
            f"{'tyre-age' if basis == 'tyre_age' else 'stint-progress'} basis. "
            "Delta normalized to each driver's first representative sector sample."
        )
        panels = (
            [
                PanelSpec(
                    title=f"Sector {sector}: observed sector-time evolution",
                    x_label="Tyre age (completed laps on set)" if basis == "tyre_age" else "Stint progress lap",
                    y_label="Normalized sector-time delta (s)",
                    series=sector_series[sector],
                    annotations=sector_annotations[sector],
                    summary_lines=sector_summary_lines[sector],
                    x_limits=sector_x_limits,
                    y_limits=sector_y_limits,
                )
                for sector in (1, 2, 3)
            ]
            if mode == "sector_evolution"
            else []
        )
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=_title(config, dataset, "Observed Sector-Time Evolution" if mode == "sector_evolution" else "Observed Pace Evolution"),
            subtitle=sector_subtitle if mode == "sector_evolution" else subtitle,
            x_label="Tyre age (completed laps on set)" if basis == "tyre_age" else "Stint progress lap",
            y_label="Sector-time delta from first valid sample (s)" if mode == "sector_evolution" else "Representative lap time (s)",
            selected_drivers=context.drivers,
            source_session=dataset.metadata.model_dump(mode="json"),
            warnings=context.warning_messages,
            series=[] if panels else series,
            panels=panels,
            annotations=[] if panels else annotations,
            summary_lines=[] if panels else summary_lines,
            metadata=context.metadata(result_kind=results["result_kind"], results=results),
        )


class CompoundComparisonRecipe:
    recipe_id = "compound_comparison"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        context = _context(dataset, config)
        mode = str(parameter_value(config, "comparison_mode", section_name="analysis", default="unrestricted_distribution"))
        compounds = parameter_value(config, "compounds", section_name="analysis", default=[])
        if not isinstance(compounds, list) or not compounds:
            compounds = sorted({lap.compound for lap in context.laps if lap.compound})[:2]
        if mode != "unrestricted_distribution" and len(compounds) != 2:
            raise ValueError("Compound difference modes require exactly two compounds")
        age_range = _range_tuple(parameter_value(config, "tyre_age_range", section_name="analysis"))
        lap_range = _range_tuple(effective_lap_range(config))
        if mode != "unrestricted_distribution" and age_range is None and lap_range is None:
            raise ValueError("Compound difference modes require a race-lap or tyre-age range")
        result = compare_compounds(
            context.analysis,
            mode=mode,  # type: ignore[arg-type]
            compounds=[str(value) for value in compounds],
            drivers=context.drivers,
            lap_range=lap_range,
            tyre_age_range=age_range,
            minimum_samples=int(parameter_value(config, "minimum_samples", section_name="analysis", default=5)),
        )
        compound_samples: dict[str, list[float]] = {
            compound: [] for compound in result.compounds
        }
        for key, values in sorted(result.distributions_seconds.items()):
            compound = key.rsplit(":", 1)[-1]
            compound_samples.setdefault(compound, []).extend(float(value) for value in values)
        compound_positions = {
            compound: float(index)
            for index, compound in enumerate(result.compounds)
        }
        all_values = [
            value
            for compound in result.compounds
            for value in compound_samples.get(compound, [])
        ]
        value_span = (max(all_values) - min(all_values)) if all_values else 0.0
        y_padding = max(value_span * 0.10, 0.15)
        series: list[SeriesSpec] = []
        box_summaries: list[BoxSummarySpec] = []
        annotations: list[TextAnnotationSpec] = []
        compound_summaries: dict[str, dict[str, float | int | None]] = {}
        for compound in result.compounds:
            values = compound_samples.get(compound, [])
            position = compound_positions[compound]
            style = resolve_compound_style(dataset, config, compound, context.diagnostics)
            statistics = descriptive_statistics(values)
            compound_summaries[compound] = {
                "n": statistics.sample_count,
                "median_seconds": statistics.median,
                "q1_seconds": statistics.q1,
                "q3_seconds": statistics.q3,
                "iqr_seconds": statistics.iqr,
            }
            if values:
                jitter = (
                    [0.0]
                    if len(values) == 1
                    else [
                        ((index / (len(values) - 1)) - 0.5) * 0.24
                        for index in range(len(values))
                    ]
                )
                series.append(
                    SeriesSpec(
                        label=None,
                        x=[position + offset for offset in jitter],
                        y=values,
                        color=style.color,
                        edge_color="#475569" if compound == "HARD" else None,
                        render_mode="scatter",
                        marker="o",
                        marker_size=28,
                    )
                )
            if statistics.q1 is not None and statistics.q3 is not None:
                if statistics.median is not None:
                    box_summaries.append(
                        BoxSummarySpec(
                            x=position,
                            q1=statistics.q1,
                            median=statistics.median,
                            q3=statistics.q3,
                            width=0.30,
                            face_color=style.color,
                            edge_color="#111827",
                            alpha=0.24,
                        )
                    )
            if all_values:
                annotations.append(
                    TextAnnotationSpec(
                        x=position,
                        y=min(all_values) - y_padding * 0.62,
                        text=(
                            f"n={statistics.sample_count}"
                            if statistics.sample_count
                            else "n=0 · unavailable"
                        ),
                        color="#334155",
                        font_size=8,
                        font_weight="bold",
                        horizontal_alignment="center",
                    )
                )
            if statistics.median is not None and statistics.iqr is not None:
                annotations.append(
                    TextAnnotationSpec(
                        x=position - 0.34,
                        y=max(values) + y_padding * 0.12,
                        text=(
                            f"median {statistics.median:.3f} s · "
                            f"IQR {statistics.iqr:.3f} s"
                        ),
                        color="#334155",
                        font_size=8,
                    )
                )
        subtitle = _compound_comparison_subtitle(result, compound_summaries)
        metadata = context.metadata(
            result_kind=result.result_kind,
            results=result.model_dump(mode="json"),
            extra_effective={"analysis": {"comparison_mode": mode, "compounds": compounds}},
        )
        metadata["compound_summaries"] = compound_summaries
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=_title(config, dataset, "Compound Comparison"),
            subtitle=subtitle,
            x_label="Compound",
            y_label="Representative lap time (s)",
            selected_drivers=context.drivers,
            source_session=dataset.metadata.model_dump(mode="json"),
            warnings=context.warning_messages + result.warnings,
            series=series,
            box_summaries=box_summaries,
            annotations=annotations,
            x_tick_labels={
                compound_positions[compound]: compound.title()
                for compound in result.compounds
            },
            x_limits=(-0.55, max(float(len(result.compounds)) - 0.45, 0.55)),
            y_limits=(
                (min(all_values) - y_padding, max(all_values) + y_padding)
                if all_values
                else None
            ),
            metadata=metadata,
        )


class RaceTimeDeltaEvolutionRecipe:
    recipe_id = "race_time_delta_evolution"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        context = _context(dataset, config)
        mode = str(parameter_value(config, "delta_mode", section_name="analysis", default="derived_cumulative_pace_delta"))
        focal = _driver_value(parameter_value(config, "focal_driver", section_name="selection"))
        benchmark = _driver_value(parameter_value(config, "reference_driver", section_name="analysis"))
        if focal is None:
            raise ValueError("Race-Time Delta requires an explicit focal driver")
        if benchmark is None:
            raise ValueError("Race-Time Delta requires an explicit comparator driver")
        if focal is None or focal == benchmark:
            raise ValueError("Race-Time Delta Evolution requires distinct focal and benchmark drivers")
        if mode == "measured_gap_change" and len(context.drivers) > 2:
            raise ValueError("Measured Direct-Gap Change supports one focal/reference pair")
        result = race_time_delta(
            dataset,
            context.analysis,
            mode=mode,  # type: ignore[arg-type]
            focal_driver=focal,
            benchmark=benchmark,
            lap_range=_range_tuple(effective_lap_range(config)),
        )
        segments = _delta_segments(result.points, result.excluded_laps)
        style = context.driver_styles.get(focal, {"color": "#335CFF"})
        series = [
            SeriesSpec(
                label=f"{focal} vs {benchmark}" if index == 0 else None,
                x=[float(point.lap_number) for point in segment],
                y=[point.value_seconds for point in segment],
                color=style["color"],
                marker="o",
                marker_size=22,
            )
            for index, segment in enumerate(segments)
            if segment
        ]
        pit_series, pit_stop_laps = _delta_pit_stop_series(
            context.laps,
            result.points,
            focal=focal,
            benchmark=benchmark,
            driver_styles=context.driver_styles,
        )
        series.extend(pit_series)
        comparison_label = f"{focal} vs {benchmark}"
        start_lap = result.start_lap
        subtitle = (
            f"Measured race-time gap change · normalized to zero at lap {start_lap} · "
            f"negative = {focal} ahead"
            if mode == "measured_gap_change"
            else f"Cumulative pace difference · normalized to zero at lap {start_lap} · "
            f"negative = {focal} ahead"
        )
        metadata = context.metadata(
            result_kind=result.result_kind,
            results=result.model_dump(mode="json"),
        )
        metadata["pit_stop_laps"] = pit_stop_laps
        metadata["comparison_breaks"] = _delta_break_metadata(
            result.points,
            result.excluded_laps,
            context.laps,
            focal=focal,
            benchmark=benchmark,
        )
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=_race_time_delta_title(config, dataset, focal, benchmark),
            subtitle=subtitle,
            x_label="Race lap",
            y_label=f"{focal} − {benchmark} race-time delta (s)",
            selected_drivers=context.drivers,
            source_session=dataset.metadata.model_dump(mode="json"),
            warnings=context.warning_messages + result.warnings,
            series=series,
            horizontal_markers=[
                HorizontalMarkerSpec(
                    y=0.0,
                    color="#64748B",
                    alpha=0.45,
                    line_style="--",
                    line_width=0.8,
                )
            ],
            shaded_regions=_race_context_regions(context.laps),
            legend_order=[
                comparison_label,
                f"{focal} pit stop",
                f"{benchmark} pit stop",
            ],
            metadata=metadata,
        )


class PitCycleComparisonRecipe:
    recipe_id = "pit_cycle_comparison"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        context = _context(dataset, config, required_driver_count=2)
        focal = _driver_value(parameter_value(config, "focal_driver", section_name="selection"))
        rival = _driver_value(parameter_value(config, "rival_driver", section_name="selection"))
        if focal is None or rival is None:
            raise ValueError("Pit-Cycle Comparison requires explicit focal and rival drivers")
        if focal == rival:
            raise ValueError("Pit-Cycle Comparison requires two distinct drivers")
        configured_pit = parameter_value(config, "pit_stop_lap", section_name="analysis")
        if configured_pit is None:
            raise ValueError("Pit-Cycle Comparison requires an explicit focal pit-in lap")
        pit_in_lap = int(configured_pit)
        result = compare_pit_cycle(
            dataset,
            context.analysis,
            focal_driver=focal,
            rival_driver=rival,
            pit_in_lap=pit_in_lap,
            post_stop_window=int(parameter_value(config, "post_stop_window", section_name="analysis", default=3)),
        )
        pre_lap = result.pre_reference_lap or max(1, result.pit_in_lap - 1)
        post_lap = result.post_reference_lap or result.window_end_lap
        pit_out_lap = result.pit_out_lap or result.pit_in_lap + 1
        x_limits = (float(pre_lap) - 0.5, float(post_lap) + 0.5)
        direct_gap_available = (
            result.pre_direct_gap_seconds is not None
            and result.post_direct_gap_seconds is not None
            and result.measured_gap_change_seconds is not None
            and result.post_reference_lap is not None
        )
        gap_series: list[SeriesSpec] = []
        gap_y_limits: tuple[float, float] | None = None
        if direct_gap_available:
            endpoint_x = [float(pre_lap), float(post_lap)]
            endpoint_y = [
                float(result.pre_direct_gap_seconds),
                float(result.post_direct_gap_seconds),
            ]
            gap_series = [
                SeriesSpec(
                    label=None,
                    x=endpoint_x,
                    y=endpoint_y,
                    color="#94A3B8",
                    line_style=":",
                ),
                SeriesSpec(
                    label=None,
                    x=endpoint_x,
                    y=endpoint_y,
                    color=context.driver_styles[focal]["color"],
                    render_mode="scatter",
                    marker="o",
                    marker_size=34,
                ),
            ]
            endpoint_min = min(endpoint_y)
            endpoint_max = max(endpoint_y)
            endpoint_span = endpoint_max - endpoint_min
            y_padding = (
                endpoint_span * 0.5
                if endpoint_span > 0
                else max(abs(endpoint_min) * 0.05, 0.1)
            )
            gap_y_limits = (endpoint_min - y_padding, endpoint_max + y_padding)
        pit_region = ShadedRegionSpec(
            x_start=float(result.pit_in_lap),
            x_end=float(pit_out_lap),
            label=None,
            color="#718096",
            alpha=0.14,
            annotation=(
                "Pit interval"
                if result.pit_interval_precision == "exact"
                else "Pit interval (lap-bounded)"
            ),
        )
        event_markers = _pit_cycle_event_markers(result)
        relevant_context = _race_context_regions(
            [
                lap
                for lap in context.laps
                if pre_lap <= lap.lap_number <= post_lap
            ]
        )
        tyre_bars: list[HorizontalBarSpec] = []
        compound_legend_seen: set[str] = set()
        visible_compounds: set[str] = set()
        driver_rows = {focal: 0.0, rival: 1.0}
        for driver in (focal, rival):
            driver_laps = sorted(
                (
                    lap
                    for lap in context.laps
                    if lap.driver == driver and pre_lap <= lap.lap_number <= post_lap
                ),
                key=lambda lap: lap.lap_number,
            )
            for group in _timeline_stint_segments(driver_laps):
                compound = group[0].compound or "UNKNOWN"
                visible_compounds.add(compound)
                style = resolve_compound_style(dataset, config, compound, context.diagnostics)
                label = (
                    "Unknown compound"
                    if compound == "UNKNOWN"
                    else compound.title()
                ) if compound not in compound_legend_seen else None
                compound_legend_seen.add(compound)
                tyre_bars.append(
                    HorizontalBarSpec(
                        y=driver_rows[driver],
                        x_start=max(float(pre_lap) - 0.4, float(group[0].lap_number) - 0.4),
                        x_end=min(float(post_lap) + 0.4, float(group[-1].lap_number) + 0.4),
                        label=label,
                        color=style.color,
                        edge_color="#475569",
                        height=0.6,
                    )
                )
        if len(visible_compounds) == 1:
            tyre_bars = [bar.model_copy(update={"label": None}) for bar in tyre_bars]
        state_message = None
        if not direct_gap_available:
            state_message = _pit_cycle_state_message(result)
        show_rejoin_context = bool(
            parameter_value(
                config,
                "show_rejoin_context",
                section_name="presentation",
                default=False,
            )
        )
        show_execution_breakdown = bool(
            parameter_value(
                config,
                "show_execution_breakdown",
                section_name="presentation",
                default=False,
            )
        )
        advanced_context = show_rejoin_context or show_execution_breakdown
        subtitle = (
            _pit_cycle_result_statement(result)
            if advanced_context
            else _pit_cycle_summary(result)
        )
        gap_annotations: list[TextAnnotationSpec] = []
        if advanced_context and direct_gap_available:
            gap_annotations = [
                TextAnnotationSpec(
                    x=float(pre_lap),
                    y=float(result.pre_direct_gap_seconds),
                    text=f"  Pre {result.pre_direct_gap_seconds:+.3f} s",
                    color=context.driver_styles[focal]["color"],
                    font_size=7,
                    font_weight="bold",
                ),
                TextAnnotationSpec(
                    x=float(post_lap),
                    y=float(result.post_direct_gap_seconds),
                    text=f"Post {result.post_direct_gap_seconds:+.3f} s  ",
                    color=context.driver_styles[focal]["color"],
                    font_size=7,
                    font_weight="bold",
                    horizontal_alignment="right",
                ),
            ]
        metadata = context.metadata(
            result_kind=result.result_kind,
            results=result.model_dump(mode="json"),
        )
        metadata["focal_event"] = {
            "label": f"{focal} stop {result.focal_stop_number}",
            "pit_in_lap": result.pit_in_lap,
            "pit_out_lap": result.pit_out_lap,
            "pre_reference_lap": result.pre_reference_lap,
            "post_reference_lap": result.post_reference_lap,
            "status": result.status,
            "unavailable_reasons": result.unavailable_reasons,
            "limitations": result.warnings,
        }
        metadata["timing_state_resolution"] = {
            "method": "as_of_source_state",
            "method_version": 2,
            "description": "Latest source timing value per driver at each comparison boundary",
        }
        panels = [
            PanelSpec(
                title=(
                    "Measured direct-gap endpoints"
                    if direct_gap_available
                    else f"Measured direct gap · {result.status}"
                ),
                x_label="Race lap",
                y_label=f"Positive means {focal} behind {rival} (s)",
                series=gap_series,
                vertical_markers=event_markers,
                horizontal_markers=[
                    HorizontalMarkerSpec(
                        y=0.0,
                        color="#64748B",
                        alpha=0.4,
                        line_style="--",
                        line_width=0.8,
                    )
                ],
                shaded_regions=[pit_region, *relevant_context],
                annotations=gap_annotations,
                x_limits=x_limits,
                y_limits=gap_y_limits,
                state_message=state_message,
                height_ratio=1.2,
            ),
            PanelSpec(
                title="Pit-cycle window",
                x_label="Race lap",
                y_label="Driver",
                horizontal_bars=tyre_bars,
                vertical_markers=[
                    marker.model_copy(update={"annotation": None})
                    for marker in event_markers
                ],
                shaded_regions=[
                    pit_region.model_copy(update={"annotation": None}),
                    *relevant_context,
                ],
                y_tick_labels={0.0: focal, 1.0: rival},
                y_axis_inverted=True,
                x_limits=x_limits,
                height_ratio=1.0,
            ),
        ]
        if advanced_context:
            panels.append(
                _pit_context_strip_panel(
                    result,
                    show_rejoin=show_rejoin_context,
                    show_execution=show_execution_breakdown,
                )
            )
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=_pit_cycle_title(config, dataset, result),
            subtitle=subtitle,
            x_label="Race lap",
            y_label=f"Direct gap: positive means {focal} behind {rival} (s)",
            selected_drivers=[focal, rival],
            source_session=dataset.metadata.model_dump(mode="json"),
            warnings=context.warning_messages + result.warnings,
            series=[],
            panels=panels,
            metadata=metadata,
        )


class DriverBattleRecipe:
    recipe_id = "driver_battle"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        context = _context(dataset, config, required_driver_count=2)
        focal, rival = context.drivers
        focal_laps = {lap.lap_number: lap for lap in context.laps if lap.driver == focal}
        rival_laps = {lap.lap_number: lap for lap in context.laps if lap.driver == rival}
        shared = sorted(set(focal_laps) & set(rival_laps))
        pace_series: list[SeriesSpec] = []
        pace_annotations: list[TextAnnotationSpec] = []
        line_styles = ("-", "--")
        markers = ("o", "s")
        for driver_index, (driver, mapping) in enumerate(
            ((focal, focal_laps), (rival, rival_laps))
        ):
            laps = [mapping[lap] for lap in shared if mapping[lap].is_representative_for_pace and mapping[lap].lap_time_seconds is not None]
            pace_series.append(
                SeriesSpec(
                    label=driver,
                    x=[float(lap.lap_number) for lap in laps],
                    y=[float(lap.lap_time_seconds or 0.0) for lap in laps],
                    color=context.driver_styles[driver]["color"],
                    line_style=line_styles[driver_index],
                    marker=markers[driver_index],
                    marker_size=22,
                )
            )
            if laps:
                pace_annotations.append(
                    TextAnnotationSpec(
                        x=float(laps[-1].lap_number),
                        y=float(laps[-1].lap_time_seconds or 0.0),
                        text=f"  {driver}",
                        color=context.driver_styles[driver]["color"],
                        font_size=8,
                        font_weight="bold",
                    )
                )
        gap_result = race_time_delta(
            dataset,
            context.analysis,
            mode="measured_gap_change",
            focal_driver=focal,
            benchmark=rival,
            lap_range=_range_tuple(effective_lap_range(config)),
        )
        gap_series: list[SeriesSpec] = []
        direct_gap_points = gap_result.direct_gap_points
        for segment_index, segment in enumerate(
            _delta_segments(direct_gap_points, gap_result.excluded_laps)
        ):
            gap_series.append(
                SeriesSpec(
                    label=f"{focal} − {rival} direct gap" if segment_index == 0 else None,
                    x=[float(point.lap_number) for point in segment],
                    y=[point.value_seconds for point in segment],
                    color="#4A5568",
                    marker="o",
                    marker_size=18,
                )
            )
        tyre_bars: list[HorizontalBarSpec] = []
        tyre_annotations: list[TextAnnotationSpec] = []
        compound_legend_seen: set[str] = set()
        driver_rows = {focal: 0.0, rival: 1.0}
        for driver in context.drivers:
            grouped: dict[int, list[StrategyLap]] = defaultdict(list)
            for lap in context.laps:
                if lap.driver == driver and lap.effective_stint is not None:
                    grouped[lap.effective_stint].append(lap)
            for stint, group in sorted(grouped.items()):
                group = sorted(group, key=lambda lap: lap.lap_number)
                compound = group[0].compound or "UNKNOWN"
                compound_style = resolve_compound_style(dataset, config, compound, context.diagnostics)
                compound_label = "Unknown compound" if compound == "UNKNOWN" else compound.title()
                tyre_bars.append(
                    HorizontalBarSpec(
                        y=driver_rows[driver],
                        x_start=float(group[0].lap_number) - 0.4,
                        x_end=float(group[-1].lap_number) + 0.4,
                        label=(
                            compound_label
                            if compound_label not in compound_legend_seen
                            else None
                        ),
                        color=compound_style.color,
                        edge_color="#475569",
                    )
                )
                compound_legend_seen.add(compound_label)
                ages = [lap.tyre_age for lap in group if lap.tyre_age is not None]
                age_text = (
                    f"age {min(ages):.0f}–{max(ages):.0f}"
                    if ages
                    else "age unavailable"
                )
                tyre_annotations.append(
                    TextAnnotationSpec(
                        x=float(group[0].lap_number),
                        y=driver_rows[driver],
                        text=f"S{stint} · {age_text}",
                        color="#111827",
                        font_size=7,
                        font_weight="bold",
                    )
                )
        pit_markers = _driver_battle_pit_markers(context.laps, context.drivers)
        race_context = _race_context_regions(context.laps)
        subtitle = _driver_battle_summary(gap_result)
        battle_x_limits = (
            (
                float(min(lap.lap_number for lap in context.laps)) - 0.5,
                float(max(lap.lap_number for lap in context.laps)) + 0.5,
            )
            if context.laps
            else None
        )
        results = {
            "value_categories": ["descriptive", "measured"],
            "panel_contract": [
                "representative_pace",
                "direct_driver_gap",
                "compound_stint_and_tyre_age_context",
            ],
            "gap_result": gap_result.model_dump(mode="json"),
            "battle_summary": {
                "start_direct_gap_seconds": (
                    direct_gap_points[0].value_seconds if direct_gap_points else None
                ),
                "end_direct_gap_seconds": (
                    direct_gap_points[-1].value_seconds if direct_gap_points else None
                ),
                "observed_change_seconds": gap_result.overall_change_seconds,
            },
            "pit_stop_laps": {
                driver: sorted(
                    lap.lap_number
                    for lap in context.laps
                    if lap.driver == driver and lap.is_pit_in_lap
                )
                for driver in context.drivers
            },
            "stints": [
                summary.model_dump(mode="json")
                for summary in context.analysis.stints
                if summary.driver in context.drivers
            ],
        }
        return ChartSpec(
            recipe_id=self.recipe_id,
            title=_driver_battle_title(config, dataset, focal, rival),
            subtitle=subtitle,
            x_label="Shared race-lap interval",
            y_label="Panel-specific seconds (see analytical metadata)",
            selected_drivers=context.drivers,
            source_session=dataset.metadata.model_dump(mode="json"),
            warnings=context.warning_messages + gap_result.warnings,
            series=[],
            panels=[
                PanelSpec(
                    title="Representative pace",
                    x_label="Race lap",
                    y_label="Lap time (s)",
                    series=pace_series,
                    annotations=pace_annotations,
                    vertical_markers=pit_markers,
                    shaded_regions=race_context,
                    x_limits=battle_x_limits,
                ),
                PanelSpec(
                    title=(
                        f"Direct gap: {focal} vs {rival}"
                        if direct_gap_points
                        else f"Direct gap unavailable: {focal} vs {rival}"
                    ),
                    x_label="Race lap",
                    y_label=f"{focal} − {rival} direct gap (s) · negative = {focal} ahead",
                    series=gap_series,
                    vertical_markers=pit_markers,
                    horizontal_markers=[
                        HorizontalMarkerSpec(
                            y=0.0,
                            color="#64748B",
                            alpha=0.4,
                            line_style="--",
                            line_width=0.8,
                        )
                    ],
                    shaded_regions=race_context,
                    x_limits=battle_x_limits,
                    state_message=(
                        None
                        if direct_gap_points
                        else f"Direct {focal}-versus-{rival} gap unavailable\nNumeric paired timing coverage is required"
                    ),
                ),
                PanelSpec(
                    title="Compound, stint and tyre-age context",
                    x_label="Race lap",
                    y_label="Driver",
                    horizontal_bars=tyre_bars,
                    annotations=tyre_annotations,
                    vertical_markers=pit_markers,
                    shaded_regions=[
                        region.model_copy(update={"label": None})
                        for region in race_context
                    ],
                    y_tick_labels={0.0: focal, 1.0: rival},
                    y_axis_inverted=True,
                    x_limits=battle_x_limits,
                ),
            ],
            metadata=context.metadata(result_kind="driver_battle", results=results),
        )


class _StrategyRecipeContext:
    def __init__(
        self,
        dataset: SessionDataset,
        config: ChartRecipeConfig,
        drivers: list[str],
        analysis: StrategyAnalysisResult,
        diagnostics: ParameterDiagnostics,
        legacy_migration: dict[str, Any],
    ):
        self.dataset = dataset
        self.config = config
        self.drivers = drivers
        self.analysis = analysis
        self.diagnostics = diagnostics
        self.legacy_migration = legacy_migration
        bounds = _range_tuple(effective_lap_range(config))
        self.laps = [
            lap for lap in analysis.laps if lap.driver in drivers and _within(lap.lap_number, bounds)
        ]
        self.driver_styles: dict[str, dict[str, Any]] = {}
        for driver in drivers:
            self.driver_styles[driver] = resolve_driver_style(
                dataset, config, driver, diagnostics
            ).as_metadata()
        for lap in self.laps:
            for reason in lap.pace_exclusion_reasons:
                diagnostics.count(reason)
        self.show_pit_markers = bool(
            parameter_value(config, "show_pit_markers", section_name="presentation", default=True)
        )
        self.context_layer = str(
            parameter_value(config, "context_layer", section_name="presentation", default="race_context")
        )

    @property
    def warning_messages(self) -> list[str]:
        return list(dict.fromkeys([
            *self.analysis.warnings,
            *(warning["message"] for warning in self.diagnostics.warnings),
        ]))

    def metadata(
        self,
        *,
        result_kind: str,
        results: dict[str, Any],
        extra_effective: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            **strategy_metadata(self.analysis, result_kind=result_kind, results=results),
            **effective_configuration_metadata(
                self.dataset,
                self.config,
                selected_drivers=self.drivers,
                diagnostics=self.diagnostics,
                style_sources={"drivers": self.driver_styles},
                extra_effective={
                    "strategy": {
                        "schema_version": self.analysis.schema_version,
                        "exclusion_policy": self.analysis.effective_policy.model_dump(mode="json"),
                    },
                    **(extra_effective or {}),
                },
            ),
        }
        payload["analytical_basis"].update(
            {
                "active_drivers": self.drivers,
                "available_stints": [
                    f"{summary.driver}:{summary.effective_stint}"
                    for summary in self.analysis.stints
                    if summary.driver in self.drivers
                ],
                "active_interval": effective_lap_range(self.config),
            }
        )
        return payload


def _context(
    dataset: SessionDataset,
    config: ChartRecipeConfig,
    *,
    maximum_drivers: int | None = None,
    required_driver_count: int | None = None,
) -> _StrategyRecipeContext:
    diagnostics = ParameterDiagnostics()
    drivers = selected_driver_codes(dataset, config)
    if config.recipe_id == "pit_cycle_comparison":
        focal = _driver_value(
            parameter_value(config, "focal_driver", section_name="selection")
        )
        rival = _driver_value(
            parameter_value(config, "rival_driver", section_name="selection")
        )
        if focal and rival:
            drivers = list(dict.fromkeys([focal, rival]))
    if config.recipe_id == "race_time_delta_evolution":
        focal = _driver_value(
            parameter_value(config, "focal_driver", section_name="selection")
        )
        reference = _driver_value(
            parameter_value(config, "reference_driver", section_name="analysis")
        )
        if focal and reference:
            drivers = list(dict.fromkeys([focal, reference]))
    available_drivers = {driver.abbreviation for driver in dataset.drivers}
    unknown_drivers = sorted(set(drivers) - available_drivers)
    if unknown_drivers:
        raise ValueError(f"Driver is not present in the loaded snapshot: {', '.join(unknown_drivers)}")
    if maximum_drivers is not None and len(drivers) > maximum_drivers:
        raise ValueError(f"Template supports at most {maximum_drivers} drivers; apply a driver filter")
    if required_driver_count is not None and len(drivers) != required_driver_count:
        raise ValueError(f"Template requires exactly {required_driver_count} selected drivers")
    policy = strategy_policy_from_parameters(config.parameters)
    analysis = derive_strategy_analysis(dataset, policy)
    migration: dict[str, Any] = {"from_schema_version": None, "to_schema_version": 2, "diagnostics": []}
    if config.recipe_id == "tyre_strategy":
        layout = parameter_value(config, "layout", section_name="analysis")
        if layout is not None:
            migration["from_schema_version"] = 1
            if layout == "stint_bars":
                migration["diagnostics"].append("Mapped legacy layout=stint_bars to Strategy Timeline.")
            elif layout == "compound_steps":
                migration["diagnostics"].append("Legacy compound_steps is rendered as Strategy Timeline stint bars.")
                diagnostics.warn("layout", "Legacy compound_steps migrated to Strategy Timeline stint bars.")
    return _StrategyRecipeContext(dataset, config, drivers, analysis, diagnostics, migration)


def _selected_stints(
    analysis: StrategyAnalysisResult,
    drivers: list[str],
    config: ChartRecipeConfig,
):
    raw = parameter_value(config, "stints", section_name="selection", default=[])
    requested_order: list[tuple[str, int]] = []
    raw_compounds = parameter_value(config, "compounds", section_name="analysis", default=[])
    compounds = (
        {str(value).upper() for value in raw_compounds}
        if isinstance(raw_compounds, list) and raw_compounds
        else set()
    )
    if isinstance(raw, list):
        for value in raw:
            text = str(value)
            if ":" in text:
                driver, stint = text.split(":", 1)
                if stint.isdigit():
                    key = (driver, int(stint))
                    if key not in requested_order:
                        requested_order.append(key)
    requested = set(requested_order)
    selected = [
        summary
        for summary in analysis.stints
        if summary.driver in drivers
        and (not requested or (summary.driver, summary.effective_stint) in requested)
        and (not compounds or summary.compound in compounds)
    ]
    if requested_order:
        order = {key: index for index, key in enumerate(requested_order)}
        return sorted(
            selected,
            key=lambda summary: order[(summary.driver, summary.effective_stint)],
        )
    driver_order = {driver: index for index, driver in enumerate(drivers)}
    return sorted(
        selected,
        key=lambda summary: (
            driver_order[summary.driver],
            summary.effective_stint,
        ),
    )


def _timeline_stint_segments(laps: list[StrategyLap]) -> list[list[StrategyLap]]:
    segments: list[list[StrategyLap]] = []
    current: list[StrategyLap] = []
    current_signature: tuple[int, str | None, bool] | None = None
    for lap in laps:
        if lap.effective_stint is None:
            if current:
                segments.append(current)
                current = []
            current_signature = None
            continue
        signature = (
            lap.effective_stint,
            lap.compound,
            lap.stint_source == "conflicting",
        )
        if (
            current
            and (
                signature != current_signature
                or lap.lap_number != current[-1].lap_number + 1
            )
        ):
            segments.append(current)
            current = []
        current.append(lap)
        current_signature = signature
    if current:
        segments.append(current)
    return segments


def _strategy_lap_segments(laps: list[StrategyLap]) -> list[list[StrategyLap]]:
    segments: list[list[StrategyLap]] = []
    current: list[StrategyLap] = []
    for lap in sorted(laps, key=lambda item: item.lap_number):
        if current and lap.lap_number != current[-1].lap_number + 1:
            segments.append(current)
            current = []
        current.append(lap)
    if current:
        segments.append(current)
    return segments


def _stint_pace_x(lap: StrategyLap, basis: str) -> float | int | None:
    if basis == "stint_progress":
        return lap.stint_progress
    if basis == "tyre_age":
        return lap.tyre_age
    return lap.lap_number


def _stint_pace_y(
    lap: StrategyLap,
    reference_driver: str | None,
    reference_laps: dict[int, StrategyLap],
) -> float:
    value = float(lap.lap_time_seconds or 0.0)
    if reference_driver is None:
        return value
    reference = reference_laps[lap.lap_number]
    return value - float(reference.lap_time_seconds or 0.0)


def _stint_pace_summary_lines(
    rows: list[dict[str, Any]],
    *,
    median_delta_seconds: float | None,
) -> list[str]:
    lines = [
        (
            f"{row['label']}: representative laps {row['representative_lap_count']} · "
            f"median {_seconds(row['median_seconds'])} · IQR {_seconds(row['iqr_seconds'])}"
        )
        for row in rows
    ]
    if median_delta_seconds is not None and len(rows) == 2:
        if median_delta_seconds == 0:
            lines.append("Median advantage: 0.000 s (equal)")
        else:
            winner_index = 0 if median_delta_seconds < 0 else 1
            winner = rows[winner_index]["driver"]
            if rows[0]["driver"] == rows[1]["driver"]:
                winner = rows[winner_index]["label"]
            lines.append(
                f"{winner} median advantage: {abs(median_delta_seconds):.3f} s"
            )
    return lines


def _stint_pace_subtitle(rows: list[dict[str, Any]]) -> str | None:
    order = {"SOFT": 0, "MEDIUM": 1, "HARD": 2, "INTERMEDIATE": 3, "WET": 4}
    compounds = sorted(
        {str(row["compound"]).upper() for row in rows if row.get("compound")},
        key=lambda compound: (order.get(compound, 99), compound),
    )
    if not compounds:
        return "Unknown compound"
    if len(compounds) == 1:
        return f"{compounds[0].title()} compound"
    return f"{' / '.join(compound.title() for compound in compounds)} compounds"


def _stint_pace_x_limits(values: list[float]) -> tuple[float, float] | None:
    if not values:
        return None
    minimum = min(values)
    maximum = max(values)
    span = maximum - minimum
    left_padding = max(0.25, span * 0.03)
    right_padding = max(0.8, span * 0.08)
    return minimum - left_padding, maximum + right_padding


def _padded_limits(
    values: list[float],
    *,
    minimum_padding: float,
) -> tuple[float, float] | None:
    if not values:
        return None
    minimum = min(values)
    maximum = max(values)
    padding = max((maximum - minimum) * 0.06, minimum_padding)
    return minimum - padding, maximum + padding


def _seconds(value: Any) -> str:
    return "unavailable" if value is None else f"{float(value):.3f} s"


def _pit_event_laps(laps: list[StrategyLap]) -> list[int]:
    pit_in_laps = {lap.lap_number for lap in laps if lap.is_pit_in_lap}
    pit_out_only = {
        lap.lap_number
        for lap in laps
        if lap.is_pit_out_lap and lap.lap_number - 1 not in pit_in_laps
    }
    return sorted(pit_in_laps | pit_out_only)


def _pit_marker_series(
    pit_marker_laps: dict[str, list[int]],
    driver_index: dict[str, int],
) -> list[SeriesSpec]:
    x: list[float] = []
    y: list[float] = []
    for driver in driver_index:
        for lap in pit_marker_laps.get(driver, []):
            x.append(float(lap))
            y.append(float(driver_index[driver]))
    if not x:
        return []
    return [
        SeriesSpec(
            label="Pit stop",
            x=x,
            y=y,
            color="#111827",
            render_mode="scatter",
            marker="v",
            marker_size=26,
        )
    ]


def _is_retirement_status(status: str | None) -> bool:
    if not status:
        return False
    normalized = status.strip().upper()
    return not (
        normalized == "FINISHED"
        or normalized == "CLASSIFIED"
        or normalized.startswith("+")
    )


def _timeline_panels(
    dataset: SessionDataset,
    context: _StrategyRecipeContext,
    *,
    bars: list[HorizontalBarSpec],
    pit_series: list[SeriesSpec],
    retirement_annotations: list[TextAnnotationSpec],
    context_layer: str,
) -> list[PanelSpec]:
    if context_layer == "race_context":
        return []
    timeline = PanelSpec(
        title="Strategy Timeline",
        x_label="Race lap",
        y_label="Driver",
        series=pit_series,
        horizontal_bars=bars,
        shaded_regions=_race_context_regions(context.laps),
        annotations=retirement_annotations,
        y_tick_labels={float(index): driver for index, driver in enumerate(context.drivers)},
        y_axis_inverted=True,
    )
    if context_layer == "conditions":
        by_lap: dict[int, list[float]] = defaultdict(list)
        for lap in context.laps:
            if lap.is_representative_for_pace and lap.lap_time_seconds is not None:
                by_lap[lap.lap_number].append(lap.lap_time_seconds)
        condition_series = [
            SeriesSpec(
                label="Median representative field pace",
                x=[float(lap) for lap in sorted(by_lap)],
                y=[float(median(by_lap[lap])) for lap in sorted(by_lap)],
                color="#335CFF",
            )
        ]
        lap_boundaries = sorted(
            (
                lap.lap_end_time_seconds,
                lap.lap_number,
            )
            for lap in context.laps
            if lap.lap_end_time_seconds is not None
        )
        for label, field, color in (
            ("Track temperature", "track_temp_c", "#D97706"),
            ("Air temperature", "air_temp_c", "#0F766E"),
            ("Rainfall", "rainfall", "#2563EB"),
        ):
            points = [
                (
                    next(
                        (lap for end, lap in lap_boundaries if end >= sample.time_seconds),
                        lap_boundaries[-1][1] if lap_boundaries else 1,
                    ),
                    float(bool(value)) if isinstance(value, bool) else float(value),
                )
                for sample in dataset.weather
                if (value := getattr(sample, field)) is not None
            ]
            if points:
                condition_series.append(
                    SeriesSpec(
                        label=label,
                        x=[float(point[0]) for point in points],
                        y=[point[1] for point in points],
                        color=color,
                    )
                )
        return [
            timeline,
            PanelSpec(
                title="Conditions",
                x_label="Race lap",
                y_label="Source units (see legend and metadata)",
                series=condition_series,
                shaded_regions=_race_context_regions(context.laps),
            ),
        ]
    metric = "position" if context_layer == "position" else "gap_to_leader_seconds"
    label = "Position" if metric == "position" else "Gap to leader (s)"
    context_series: list[SeriesSpec] = []
    for driver in context.drivers:
        points = [
            (lap.lap_number, getattr(lap, metric))
            for lap in context.laps
            if lap.driver == driver and getattr(lap, metric) is not None
        ]
        if points:
            context_series.append(
                SeriesSpec(
                    label=driver,
                    x=[float(point[0]) for point in points],
                    y=[float(point[1]) for point in points],
                    color=context.driver_styles[driver]["color"],
                    render_mode="step" if metric == "position" else "line",
                )
            )
    return [
        timeline,
        PanelSpec(
            title=label,
            x_label="Race lap",
            y_label=label,
            series=context_series,
            shaded_regions=_race_context_regions(context.laps),
            y_axis_inverted=metric == "position",
        ),
    ]


def _race_context_regions(laps: list[StrategyLap]) -> list[ShadedRegionSpec]:
    by_lap: dict[int, set[str]] = defaultdict(set)
    for lap in laps:
        status_codes = set(str(lap.track_status or ""))
        if "4" in status_codes:
            by_lap[lap.lap_number].add("Safety Car")
        if status_codes & {"6", "7"}:
            by_lap[lap.lap_number].add("VSC")
        if "5" in status_codes:
            by_lap[lap.lap_number].add("Red flag")
    regions: list[ShadedRegionSpec] = []
    style = {
        "Safety Car": ("#F6C445", 0.12),
        "VSC": ("#60A5FA", 0.10),
        "Red flag": ("#D90429", 0.12),
    }
    for context_label in ("Safety Car", "VSC", "Red flag"):
        active_laps = sorted(
            lap for lap, labels in by_lap.items() if context_label in labels
        )
        label_used = False
        for start, end in _contiguous_lap_ranges(active_laps):
            color, alpha = style[context_label]
            regions.append(
                ShadedRegionSpec(
                    x_start=float(start),
                    x_end=float(end + 1),
                    label=None if label_used else context_label,
                    color=color,
                    alpha=alpha,
                    annotation=(
                        "SC"
                        if context_label == "Safety Car"
                        else "VSC"
                        if context_label == "VSC"
                        else "RED"
                    ),
                )
            )
            label_used = True
    return regions


def _contiguous_lap_ranges(laps: list[int]) -> list[tuple[int, int]]:
    if not laps:
        return []
    ranges: list[tuple[int, int]] = []
    start = previous = laps[0]
    for lap in laps[1:]:
        if lap != previous + 1:
            ranges.append((start, previous))
            start = lap
        previous = lap
    ranges.append((start, previous))
    return ranges


def _delta_segments(points, excluded_laps: list[int]):
    excluded = set(excluded_laps)
    segments: list[list[Any]] = []
    current: list[Any] = []
    previous: int | None = None
    for point in points:
        if previous is not None and any(lap in excluded for lap in range(previous + 1, point.lap_number)):
            if current:
                segments.append(current)
            current = []
        current.append(point)
        previous = point.lap_number
    if current:
        segments.append(current)
    return segments


def _delta_pit_stop_series(
    laps: list[StrategyLap],
    points: list[Any],
    *,
    focal: str,
    benchmark: str,
    driver_styles: dict[str, dict[str, Any]],
) -> tuple[list[SeriesSpec], dict[str, list[int]]]:
    ordered_points = sorted(points, key=lambda point: point.lap_number)
    series: list[SeriesSpec] = []
    pit_stop_laps: dict[str, list[int]] = {}
    for driver, marker in ((focal, "v"), (benchmark, "^")):
        driver_pits = sorted(
            {
                lap.lap_number
                for lap in laps
                if lap.driver == driver and lap.is_pit_in_lap
            }
        )
        x_values: list[float] = []
        y_values: list[float] = []
        for pit_lap in driver_pits:
            anchor = next(
                (
                    point
                    for point in reversed(ordered_points)
                    if point.lap_number <= pit_lap
                ),
                None,
            )
            if anchor is None:
                continue
            x_values.append(float(pit_lap))
            y_values.append(float(anchor.value_seconds))
        if x_values:
            series.append(
                SeriesSpec(
                    label=f"{driver} pit stop",
                    x=x_values,
                    y=y_values,
                    color="#64748B",
                    render_mode="scatter",
                    marker=marker,
                    marker_size=30,
                )
            )
        pit_stop_laps[driver] = driver_pits
    return series, pit_stop_laps


def _delta_break_metadata(
    points: list[Any],
    excluded_laps: list[int],
    laps: list[StrategyLap],
    *,
    focal: str,
    benchmark: str,
) -> list[dict[str, Any]]:
    excluded = set(excluded_laps)
    by_driver_lap = {(lap.driver, lap.lap_number): lap for lap in laps}
    ordered_points = sorted(points, key=lambda point: point.lap_number)
    breaks: list[dict[str, Any]] = []
    for previous, current in zip(ordered_points, ordered_points[1:]):
        missing_laps = [
            lap_number
            for lap_number in range(previous.lap_number + 1, current.lap_number)
            if lap_number in excluded
        ]
        if not missing_laps:
            continue
        details: list[dict[str, Any]] = []
        for lap_number in missing_laps:
            exclusion_reasons = sorted(
                {
                    reason
                    for driver in (focal, benchmark)
                    for reason in (
                        by_driver_lap.get((driver, lap_number)).pace_exclusion_reasons
                        if by_driver_lap.get((driver, lap_number)) is not None
                        else []
                    )
                }
            )
            details.append(
                {
                    "lap_number": lap_number,
                    "category": (
                        "excluded_comparison_window"
                        if exclusion_reasons
                        else "coverage_loss"
                    ),
                    "exclusion_reasons": exclusion_reasons,
                }
            )
        breaks.append(
            {
                "after_lap": previous.lap_number,
                "before_lap": current.lap_number,
                "reason_categories": sorted({detail["category"] for detail in details}),
                "laps": details,
            }
        )
    return breaks


def _pit_cycle_event_markers(result: Any) -> list[VerticalMarkerSpec]:
    markers = [
        VerticalMarkerSpec(
            x=float(result.pre_reference_lap or max(1, result.pit_in_lap - 1)),
            color="#475569",
            alpha=0.65,
            line_style=":",
            annotation=f"Pre ref L{result.pre_reference_lap or max(1, result.pit_in_lap - 1)}",
        ),
        VerticalMarkerSpec(
            x=float(result.pit_in_lap),
            color="#991B1B",
            alpha=0.7,
            line_style="--",
            annotation=f"Pit-in L{result.pit_in_lap}",
        ),
        VerticalMarkerSpec(
            x=float(result.pit_out_lap or result.pit_in_lap + 1),
            color="#991B1B",
            alpha=0.7,
            line_style="--",
            annotation=(
                f"Pit-out L{result.pit_out_lap}"
                if result.pit_out_lap is not None
                else f"Pit-out boundary L{result.pit_in_lap + 1}"
            ),
        ),
    ]
    if result.post_reference_lap is not None:
        markers.append(
            VerticalMarkerSpec(
                x=float(result.post_reference_lap),
                color="#475569",
                alpha=0.65,
                line_style=":",
                annotation=f"Post ref L{result.post_reference_lap}",
            )
        )
    return markers


def _pit_cycle_summary(result: Any) -> str:
    if (
        result.pre_direct_gap_seconds is not None
        and result.post_direct_gap_seconds is not None
        and result.measured_gap_change_seconds is not None
        and result.pre_reference_lap is not None
        and result.post_reference_lap is not None
    ):
        return (
            f"Pre L{result.pre_reference_lap}: {result.pre_direct_gap_seconds:+.3f} s · "
            f"Post L{result.post_reference_lap}: {result.post_direct_gap_seconds:+.3f} s · "
            f"{_pit_cycle_result_statement(result)}"
        )
    return _pit_cycle_state_message(result).replace("\n", " · ")


def _pit_cycle_result_statement(result: Any) -> str:
    if result.measured_gap_change_seconds is None:
        return _pit_cycle_state_message(result).replace("\n", " · ")
    change = float(result.measured_gap_change_seconds)
    if change < 0:
        return (
            f"{result.focal_driver} gained {abs(change):.3f} s relative to "
            f"{result.rival_driver}"
        )
    if change > 0:
        return (
            f"{result.focal_driver} lost {abs(change):.3f} s relative to "
            f"{result.rival_driver}"
        )
    return (
        f"No measured change between {result.focal_driver} and "
        f"{result.rival_driver}"
    )


def _pit_cycle_state_message(result: Any) -> str:
    heading = (
        "Measured direct gap unavailable"
        if result.status == "unavailable"
        else "Measured direct gap partial"
    )
    labels = {
        "pre_stop_paired_timing_unavailable": "pre-stop paired timing unavailable",
        "pre_stop_gap_is_lap_valued": "pre-stop gap is lap-valued",
        "pre_stop_numeric_gap_unavailable": "pre-stop numeric gap unavailable",
        "eligible_post_stop_lap_unavailable": "no eligible post-stop comparison lap",
        "post_stop_paired_timing_unavailable": "post-stop paired timing unavailable",
        "post_stop_gap_is_lap_valued": "post-stop gap is lap-valued",
        "post_stop_numeric_gap_unavailable": "post-stop numeric gap unavailable",
        "pit_out_boundary_unavailable": "pit-out boundary unavailable",
    }
    reasons = [labels.get(reason, reason.replace("_", " ")) for reason in result.unavailable_reasons]
    return f"{heading}\n{'; '.join(reasons) if reasons else 'required timing input unavailable'}"


def _pit_context_strip_panel(
    result: Any,
    *,
    show_rejoin: bool,
    show_execution: bool,
) -> PanelSpec:
    texts: list[str] = []
    if show_rejoin:
        texts.append(_pit_rejoin_info(result))
    if show_execution:
        texts.append(_pit_execution_info(result))
    positions = [0.5] if len(texts) == 1 else [0.25, 0.75]
    return PanelSpec(
        title="Additional context",
        x_label="",
        y_label="",
        info_blocks=[
            InfoBlockSpec(x=x, y=0.5, text=text, font_size=7.5)
            for x, text in zip(positions, texts)
        ],
        show_axes=False,
        height_ratio=0.48,
    )


def _pit_rejoin_info(result: Any) -> str:
    context = result.rejoin_context
    if context is None or context.status == "unavailable":
        reasons = context.warnings if context is not None else ["Rejoin analysis unavailable."]
        return "REJOIN CONTEXT · unavailable\n" + "; ".join(reasons)
    reference = (
        f"L{context.reference_lap} {context.reference_precision.replace('_', '-')}"
        if context.reference_lap is not None
        else context.reference_precision.replace("_", "-")
    )
    ahead = sorted(
        (
            participant
            for participant in context.participants
            if participant.relation == "ahead"
            and participant.focal_relative_seconds is not None
        ),
        key=lambda participant: float(participant.focal_relative_seconds or 0.0),
    )
    nearest_ahead = (
        f"{ahead[0].driver} {ahead[0].focal_relative_seconds:.3f} s ahead"
        if ahead
        else "No numeric car-ahead interval"
    )
    focal = next(
        (
            participant
            for participant in context.participants
            if participant.driver == result.focal_driver
        ),
        None,
    )
    focal_position = (
        f"{result.focal_driver} rejoined P{focal.position}"
        if focal is not None and focal.position is not None
        else f"{result.focal_driver} rejoin position unavailable"
    )
    return "\n".join(
        [
            f"REJOIN CONTEXT · {reference}",
            nearest_ahead,
            f"{focal_position} · {context.traffic_classification.replace('_', ' ')}",
            (
                context.next_observed_event.replace(
                    f"{result.rival_driver} pitted within",
                    f"{result.rival_driver} next stop: within",
                )
                if context.next_observed_event
                else "No event observed within 3 laps"
            ),
        ]
    )


def _pit_execution_info(result: Any) -> str:
    execution = result.execution_breakdown
    if execution is None or execution.status == "unavailable":
        return (
            "MEASURED PIT-LANE DURATION · unavailable\n"
            "Pit-in or pit-out timing unavailable"
        )
    duration = (
        f"{execution.pit_lane_duration_seconds:.3f} s"
        if execution.pit_lane_duration_seconds is not None
        else "unavailable"
    )
    return "\n".join(
        [
            "MEASURED PIT-LANE DURATION",
            f"{result.focal_driver} Stop {result.focal_stop_number}: {duration}",
            "Source: pit-in to pit-out timestamps",
            "Stationary time and entry/exit components unavailable",
        ]
    )


def _pit_cycle_title(config: ChartRecipeConfig, dataset: SessionDataset, result: Any) -> str:
    configured = parameter_value(config, "title", section_name="chart") or config.title
    if configured:
        return configured
    event = dataset.metadata.event.replace("Grand Prix", "GP").strip()
    return (
        f"{dataset.metadata.season} {event} {dataset.metadata.session} Pit Cycle: "
        f"{result.focal_driver} Stop {result.focal_stop_number} vs {result.rival_driver}"
    )


def _driver_battle_title(
    config: ChartRecipeConfig,
    dataset: SessionDataset,
    focal: str,
    rival: str,
) -> str:
    configured = parameter_value(config, "title", section_name="chart") or config.title
    if configured:
        return configured
    event = dataset.metadata.event.replace("Grand Prix", "GP").strip()
    return f"{dataset.metadata.season} {event} Driver Battle: {focal} vs {rival}"


def _compound_comparison_subtitle(
    result: Any,
    compound_summaries: dict[str, dict[str, float | int | None]],
) -> str:
    counts = " · ".join(
        f"{compound.title()} n={int(compound_summaries[compound]['n'] or 0)}"
        for compound in result.compounds
    )
    delta = result.scalar_difference_seconds
    if delta is None or len(result.compounds) != 2:
        return f"Descriptive only · {counts}"
    first, second = result.compounds
    matched = result.result_kind == "matched_driver_descriptive_difference"
    if delta > 0:
        comparison = (
            f"{first.title()} matched-driver median advantage: {abs(delta):.3f} s over {second.title()}"
            if matched
            else f"{first.title()} median {abs(delta):.3f} s faster than {second.title()}"
        )
    elif delta < 0:
        comparison = (
            f"{second.title()} matched-driver median advantage: {abs(delta):.3f} s over {first.title()}"
            if matched
            else f"{second.title()} median {abs(delta):.3f} s faster than {first.title()}"
        )
    else:
        comparison = f"{first.title()} and {second.title()} medians are equal"
    return f"{comparison} · {counts}"


def _driver_battle_summary(result: Any) -> str:
    points = result.direct_gap_points
    if not points or result.overall_change_seconds is None:
        return "Observed direct-gap summary unavailable · numeric paired timing required"
    change = float(result.overall_change_seconds)
    if change < 0:
        outcome = (
            f"{result.focal_driver} gained {abs(change):.3f} s relative to "
            f"{result.benchmark}"
        )
    elif change > 0:
        outcome = (
            f"{result.focal_driver} lost {abs(change):.3f} s relative to "
            f"{result.benchmark}"
        )
    else:
        outcome = (
            f"No observed change between {result.focal_driver} and "
            f"{result.benchmark}"
        )
    return (
        f"Start L{points[0].lap_number}: {points[0].value_seconds:+.3f} s · "
        f"End L{points[-1].lap_number}: {points[-1].value_seconds:+.3f} s · "
        f"{outcome}"
    )


def _driver_battle_pit_markers(
    laps: list[StrategyLap],
    drivers: list[str],
) -> list[VerticalMarkerSpec]:
    markers: list[VerticalMarkerSpec] = []
    colors = ("#991B1B", "#1D4ED8")
    line_styles = ("--", ":")
    for driver_index, driver in enumerate(drivers):
        for lap_number in sorted(
            {
                lap.lap_number
                for lap in laps
                if lap.driver == driver and lap.is_pit_in_lap
            }
        ):
            markers.append(
                VerticalMarkerSpec(
                    x=float(lap_number),
                    color=colors[driver_index],
                    alpha=0.65,
                    line_style=line_styles[driver_index],
                    annotation=f"{driver} pit L{lap_number}",
                )
            )
    return markers


def _title(config: ChartRecipeConfig, dataset: SessionDataset, default: str) -> str:
    configured = parameter_value(config, "title", section_name="chart") or config.title
    if configured:
        return configured
    event = dataset.metadata.event.replace("Grand Prix", "GP").strip()
    descriptor = "Strategy" if default == "Strategy Timeline" else default
    return (
        f"{dataset.metadata.season} {event} "
        f"{dataset.metadata.session} {descriptor}"
    )


def _race_time_delta_title(
    config: ChartRecipeConfig,
    dataset: SessionDataset,
    focal: str,
    benchmark: str,
) -> str:
    configured = parameter_value(config, "title", section_name="chart") or config.title
    if configured:
        return configured
    event = dataset.metadata.event.replace("Grand Prix", "GP").strip()
    return f"{dataset.metadata.season} {event} Race-Time Delta: {focal} vs {benchmark}"


def _range_tuple(value: Any) -> tuple[Any, Any] | None:
    if not isinstance(value, dict):
        return None
    start = value.get("start")
    end = value.get("end")
    if start is None and end is None:
        return None
    return start, end


def _within(value: float | int | None, bounds: tuple[Any, Any] | None) -> bool:
    if bounds is None:
        return True
    if value is None:
        return False
    return (bounds[0] is None or value >= bounds[0]) and (bounds[1] is None or value <= bounds[1])


def _driver_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if isinstance(value, list) and value:
        return str(value[0])
    return None
