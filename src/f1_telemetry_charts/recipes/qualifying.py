"""Purpose-built qualifying chart recipes backed by SPEC-011 results."""

from __future__ import annotations

from math import ceil, floor

from f1_telemetry_charts.charts.models import (
    ChartSpec,
    HorizontalBarSpec,
    PanelSpec,
    SeriesSpec,
    ShadedRegionSpec,
    VerticalMarkerSpec,
)
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import SessionDataset


LONG_STOPPAGE_SECONDS = 300.0
COMPRESSED_STOPPAGE_SECONDS = 120.0


def _result(dataset: SessionDataset, result_type: str):
    # Imported lazily so recipe registration does not pull the Analysis package
    # back through the plugin registry during application bootstrap.
    from f1_telemetry_charts.analysis.qualifying import materialize_qualifying_results

    target = f"{dataset.metadata.season}-{dataset.metadata.event}-{dataset.metadata.session}"
    return next(item for item in materialize_qualifying_results(target, dataset) if item.result_type == result_type)


def _metadata(result) -> dict[str, object]:
    return {
        "result_kind": result.result_type,
        "result_reference_only": True,
        "qualifying_result_schema_version": result.result_schema_version,
        "analytical_results": result.payload,
        "analytical_basis": result.analytical_basis,
        "analytical_status": result.analytical_status,
        "coverage": result.coverage,
        "limitations": result.limitations,
    }


def _source(dataset: SessionDataset) -> dict[str, object]:
    return dataset.metadata.model_dump(mode="json")


class QualifyingProgressionRecipe:
    recipe_id = "qualifying_progression"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        result = _result(dataset, "qualifying_attempt_progression")
        records = result.payload.get("timed_lap_records", [])
        interruptions = _result(dataset, "qualifying_interruptions")
        panels = []
        selected: set[str] = set()
        for segment in ("Q1", "Q2", "Q3"):
            segment_rows = [row for row in records if row["segment"] == segment and row.get("session_time_seconds") is not None and row["lap_time_seconds"] is not None]
            segment_interruptions = [
                event
                for event in interruptions.payload.get("events", [])
                if event.get("segment") == segment
                and event.get("start_time_seconds") is not None
                and event.get("end_time_seconds") is not None
            ]
            transform = lambda value: _compressed_session_minutes(float(value), segment_interruptions)
            official = next((item for item in dataset.qualifying_segments if item.segment == segment), None)
            positions = [1, 2, 3] if segment == "Q3" else [1, 2, 3, 15, 16] if segment == "Q1" else [1, 2, 3, 10, 11]
            relevant = [entry.driver for entry in sorted(official.entries, key=lambda item: item.position) if entry.position in positions] if official else []
            selected.update(relevant)
            plot_series: list[SeriesSpec] = []
            for driver in relevant:
                driver_rows = sorted((row for row in segment_rows if row["driver"] == driver and row["valid"]), key=lambda row: float(row["session_time_seconds"]))
                if not driver_rows:
                    continue
                running: list[float] = []
                best: float | None = None
                for row in driver_rows:
                    best = min(best, float(row["lap_time_seconds"])) if best is not None else float(row["lap_time_seconds"])
                    running.append(best)
                color = dataset.style.driver_colors.get(driver)
                plot_series.append(SeriesSpec(label=f"{driver} running best", x=[transform(row["session_time_seconds"]) for row in driver_rows], y=running, render_mode="step", color=color.color if color else None, marker="o"))
            cutoff_position = 15 if segment == "Q1" else 10 if segment == "Q2" else 1
            cutoff_x, cutoff_y = _running_rank_benchmark(segment_rows, cutoff_position)
            if cutoff_x:
                label = f"Running P{cutoff_position} cutoff" if segment != "Q3" else "Running pole benchmark"
                plot_series.append(SeriesSpec(label=label, x=[transform(value) for value in cutoff_x], y=cutoff_y, render_mode="step", color="#111827", line_style="--"))
            for compound, marker, color in (("WET", "s", "#2563EB"), ("INTERMEDIATE", "D", "#14B8A6"), ("SOFT", "o", "#DC2626"), ("MEDIUM", "^", "#EAB308"), ("HARD", "v", "#F3F4F6")):
                compound_rows = [row for row in segment_rows if row["attempt_role"] == "best_update" and str(row.get("compound") or "").upper() == compound and row["driver"] in relevant]
                if compound_rows:
                    plot_series.append(SeriesSpec(label=f"{compound} benchmark updates", x=[transform(row["session_time_seconds"]) for row in compound_rows], y=[float(row["lap_time_seconds"]) for row in compound_rows], render_mode="scatter", marker=marker, color=color))
            deleted_rows = [row for row in segment_rows if row["deleted"]]
            if deleted_rows:
                plot_series.append(SeriesSpec(label="Deleted lap", x=[transform(row["session_time_seconds"]) for row in deleted_rows], y=[float(row["lap_time_seconds"]) for row in deleted_rows], render_mode="scatter", marker="x", color="#B91C1C"))
            conflict_rows = [row for row in segment_rows if row.get("integrity_conflict")]
            if conflict_rows:
                plot_series.append(SeriesSpec(label="Integrity conflict", x=[transform(row["session_time_seconds"]) for row in conflict_rows], y=[float(row["lap_time_seconds"]) for row in conflict_rows], render_mode="scatter", marker="s", color="#6D28D9"))
            shaded = _rain_regions(dataset, segment_rows, segment_interruptions)
            for event in segment_interruptions:
                start_seconds = float(event["start_time_seconds"])
                end_seconds = float(event["end_time_seconds"])
                duration_minutes = (end_seconds - start_seconds) / 60
                annotation = f"Red flag · {duration_minutes:.0f} min" if end_seconds - start_seconds >= LONG_STOPPAGE_SECONDS else "Red flag"
                shaded.append(ShadedRegionSpec(x_start=transform(start_seconds), x_end=transform(end_seconds), label="Red flag", color="#DC2626", alpha=0.12, annotation=annotation))
            compressed = any(float(event["end_time_seconds"]) - float(event["start_time_seconds"]) >= LONG_STOPPAGE_SECONDS for event in segment_interruptions)
            axis_label = "Session time (min; long red flags compressed)" if compressed else "Session time (min)"
            panels.append(PanelSpec(title=segment, x_label=axis_label, y_label="Running best lap", series=plot_series, shaded_regions=shaded, x_tick_labels=_session_time_tick_labels(segment_rows, segment_interruptions), y_tick_labels=_lap_time_tick_labels(plot_series), state_message=None if segment_rows else "No source-assigned timed laps are available for this segment."))
        return ChartSpec(recipe_id=self.recipe_id, title=config.title or "Qualifying Progression", subtitle="Running bests and competitive benchmarks on session time, with tyre and recorded session context", x_label="Session time (min)", y_label="Running best lap", selected_drivers=sorted(selected), source_session=_source(dataset), warnings=result.limitations, metadata=_metadata(result), panels=panels, legend_location="best")


class QualifyingMarginRecipe:
    recipe_id = "qualifying_margin_comparison"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        result = _result(dataset, "qualifying_margin_comparison")
        panels = []
        for comparison in result.payload.get("comparisons", []):
            margin = comparison.get("margin_seconds")
            status = comparison.get("status")
            panels.append(PanelSpec(title=f"{comparison['segment']} · {comparison['kind'].replace('_', ' ').title()}", x_label="Signed margin (s)", y_label="Boundary", horizontal_bars=[] if margin is None else [HorizontalBarSpec(y=0.0, x_start=0.0, x_end=float(margin), label="Official margin")], vertical_markers=[VerticalMarkerSpec(x=0.0)], y_tick_labels={0.0: "P2" if comparison["kind"] == "pole" else "Cutoff"}, state_message=None if status == "available" else "Numeric margin unavailable; official outcome retained."))
        return ChartSpec(recipe_id=self.recipe_id, title=config.title or "Pole and Advancement Margins", subtitle="Each panel uses its own within-segment official comparison", x_label="Signed margin (s)", y_label="", selected_drivers=sorted({driver for row in result.payload.get("comparisons", []) for driver in row.get("drivers", [])}), source_session=_source(dataset), warnings=result.limitations, metadata=_metadata(result), panels=panels, legend_location="best")


class QualifyingSectorContributionRecipe:
    recipe_id = "qualifying_sector_contribution"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        result = _result(dataset, "qualifying_sector_contribution")
        deltas = result.payload.get("sector_deltas_seconds", [])
        compared = [str(item.get("driver")) for item in result.payload.get("laps", [])]
        bars = [HorizontalBarSpec(y=float(index), x_start=0.0, x_end=float(value), label=f"S{index + 1}") for index, value in enumerate(deltas)]
        status = result.payload.get("comparison_status", "unavailable")
        subtitle = f"{compared[0]} vs {compared[1]} · official Q3 best laps" if len(compared) == 2 else "Official Q3 best-lap comparison"
        return ChartSpec(recipe_id=self.recipe_id, title=config.title or "Q3 Pole Sector Contributions", subtitle=subtitle, x_label="P2 minus pole (s)", y_label="Sector", selected_drivers=result.subjects, source_session=_source(dataset), warnings=result.limitations, metadata=_metadata(result), horizontal_bars=bars, vertical_markers=[VerticalMarkerSpec(x=0.0)], y_tick_labels={float(index): f"S{index + 1}" for index in range(3)}, summary_lines=[result.payload.get("summary", "")])


def _running_rank_benchmark(rows: list[dict[str, object]], rank: int) -> tuple[list[float], list[float]]:
    best_by_driver: dict[str, float] = {}
    x_values: list[float] = []
    y_values: list[float] = []
    for row in sorted((item for item in rows if item["valid"]), key=lambda item: float(item["session_time_seconds"])):
        driver = str(row["driver"])
        lap_time = float(row["lap_time_seconds"])
        best_by_driver[driver] = min(best_by_driver.get(driver, lap_time), lap_time)
        ordered = sorted(best_by_driver.values())
        if len(ordered) >= rank:
            x_values.append(float(row["session_time_seconds"]))
            y_values.append(ordered[rank - 1])
    return x_values, y_values


def _compressed_session_minutes(value_seconds: float, events: list[dict[str, object]]) -> float:
    compressed = value_seconds
    for event in sorted(events, key=lambda item: float(item["start_time_seconds"])):
        start = float(event["start_time_seconds"])
        end = float(event["end_time_seconds"])
        duration = end - start
        if duration < LONG_STOPPAGE_SECONDS or value_seconds <= start:
            continue
        if value_seconds < end:
            compressed -= (value_seconds - start) * (1 - COMPRESSED_STOPPAGE_SECONDS / duration)
        else:
            compressed -= duration - COMPRESSED_STOPPAGE_SECONDS
    return compressed / 60


def _session_time_tick_labels(rows: list[dict[str, object]], events: list[dict[str, object]]) -> dict[float, str]:
    if not rows:
        return {}
    minimum = int(min(float(row["session_time_seconds"]) for row in rows) // 300 * 5)
    maximum = int(max(float(row["session_time_seconds"]) for row in rows) // 300 * 5 + 5)
    ticks = range(minimum, maximum + 1, 5)
    labels = {}
    for minute in ticks:
        seconds = minute * 60.0
        if any(float(event["start_time_seconds"]) < seconds < float(event["end_time_seconds"]) for event in events):
            continue
        labels[_compressed_session_minutes(seconds, events)] = str(minute)
    return labels


def _lap_time_tick_labels(series: list[SeriesSpec]) -> dict[float, str]:
    values = [float(value) for item in series for value in item.y]
    if not values:
        return {}
    span = max(values) - min(values)
    desired = max(span / 5, 0.05)
    step = next((candidate for candidate in (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0) if candidate >= desired), 20.0)
    start = floor(min(values) / step) * step
    end = ceil(max(values) / step) * step
    count = int(round((end - start) / step))
    return {
        round(start + index * step, 6): _format_lap_time(start + index * step)
        for index in range(count + 1)
    }


def _format_lap_time(seconds: float) -> str:
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes)}:{remainder:06.3f}"


def _rain_regions(dataset: SessionDataset, rows: list[dict[str, object]], events: list[dict[str, object]]) -> list[ShadedRegionSpec]:
    if not rows:
        return []
    start = min(float(row["session_time_seconds"]) for row in rows)
    end = max(float(row["session_time_seconds"]) for row in rows)
    samples = sorted((item for item in dataset.weather if start <= item.time_seconds <= end), key=lambda item: item.time_seconds)
    regions: list[ShadedRegionSpec] = []
    region_start: float | None = None
    for sample in samples:
        if sample.rainfall and region_start is None:
            region_start = sample.time_seconds
        elif sample.rainfall is False and region_start is not None:
            regions.append(ShadedRegionSpec(x_start=_compressed_session_minutes(region_start, events), x_end=_compressed_session_minutes(sample.time_seconds, events), label="Rain recorded", color="#60A5FA", alpha=0.10, annotation="Rain"))
            region_start = None
    if region_start is not None:
        regions.append(ShadedRegionSpec(x_start=_compressed_session_minutes(region_start, events), x_end=_compressed_session_minutes(end, events), label="Rain recorded", color="#60A5FA", alpha=0.10, annotation="Rain"))
    return regions
