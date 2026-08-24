"""Purpose-built Practice chart recipes backed by SPEC-012 results."""

from __future__ import annotations

from math import ceil, floor

from f1_telemetry_charts.charts.models import (
    ChartSpec,
    HorizontalBarSpec,
    SeriesSpec,
)
from f1_telemetry_charts.config.models import ChartRecipeConfig
from f1_telemetry_charts.data.models import SessionDataset


def _results(dataset: SessionDataset, result_type: str):
    from f1_telemetry_charts.analysis.practice import materialize_practice_results

    target = f"{dataset.metadata.season}-{dataset.metadata.event}-{dataset.metadata.session}"
    return [item for item in materialize_practice_results(target, dataset) if item.result_type == result_type]


def _metadata(result_type: str, results: list[object]) -> dict[str, object]:
    return {
        "result_kind": result_type,
        "result_reference_only": True,
        "practice_result_schema_version": 1,
        "analytical_result_ids": [getattr(item, "result_id") for item in results],
        "analytical_results": [getattr(item, "payload") for item in results],
        "limitations": sorted({value for item in results for value in getattr(item, "limitations")}),
    }


def _source(dataset: SessionDataset) -> dict[str, object]:
    return dataset.metadata.model_dump(mode="json")


class PracticeRunOverviewRecipe:
    recipe_id = "practice_run_overview"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        results = _results(dataset, "practice_run_chronology")
        result = results[0]
        runs = result.payload.get("runs", [])
        bars = []
        labels = {}
        for index, run in enumerate(runs):
            start, end = run.get("session_start_seconds"), run.get("session_end_seconds")
            if start is None or end is None:
                continue
            compound = run.get("compound") or "Unknown"
            bars.append(HorizontalBarSpec(y=float(index), x_start=float(start) / 60, x_end=float(end) / 60, label=str(compound), color=_compound_color(str(compound)), hatch="//" if run.get("boundary_confidence") == "partial" else None))
            labels[float(index)] = f"{run['driver']} · {run['label']} · {run['representative_count']} reps"
        return ChartSpec(recipe_id=self.recipe_id, title=config.title or "Practice Run Overview", subtitle="Neutral pit-bounded chronology with compound and representative-lap coverage", x_label="Session time (min)", y_label="Run", selected_drivers=sorted({str(run["driver"]) for run in runs}), source_session=_source(dataset), warnings=result.limitations, metadata=_metadata("practice_run_chronology", results), horizontal_bars=bars, y_tick_labels=labels, legend_location="best")


class PracticeLongRunPaceRecipe:
    recipe_id = "practice_long_run_pace_summary"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        results = _results(dataset, "practice_long_run_pace")
        bars = []
        labels = {}
        median_x = []
        median_y = []
        values: list[float] = []
        for index, result in enumerate(results):
            stats = result.payload["statistics"]
            if any(stats.get(key) is None for key in ("q1", "median", "q3")):
                continue
            bars.append(HorizontalBarSpec(y=float(index), x_start=float(stats["q1"]), x_end=float(stats["q3"]), color=_compound_color(str(result.payload.get("compound") or "")), edge_color="#111827", alpha=0.7, height=0.58))
            median_x.append(float(stats["median"]))
            median_y.append(float(index))
            values.extend([float(stats["q1"]), float(stats["median"]), float(stats["q3"])])
            compound = str(result.payload.get("compound") or "Unknown")
            labels[float(index)] = f"{result.payload['driver']} · {result.payload['label']} · {compound} · {result.payload['representative_count']} laps"
        median_series = [SeriesSpec(label="Median", x=median_x, y=median_y, color="#111827", render_mode="scatter", marker="|", marker_size=90)] if median_x else []
        return ChartSpec(recipe_id=self.recipe_id, title=config.title or "Practice Long-Run Pace Summary", subtitle="Representative-lap median and IQR; incompatible samples are descriptive, not ranked", x_label="Lap time", y_label="Run", selected_drivers=sorted({item.subjects[0] for item in results if item.subjects}), source_session=_source(dataset), warnings=sorted({value for item in results for value in item.limitations}), metadata=_metadata("practice_long_run_pace", results), horizontal_bars=bars, series=median_series, x_tick_labels=_lap_time_ticks(values), y_tick_labels=labels, y_axis_inverted=True, legend_location="best")


class PracticeObservedPaceEvolutionRecipe:
    recipe_id = "practice_observed_pace_evolution"

    def build_spec(self, dataset: SessionDataset, config: ChartRecipeConfig) -> ChartSpec:
        results = _results(dataset, "practice_observed_pace_evolution")
        publishable = [item for item in results if item.payload.get("publishable") and item.payload.get("basis") == "stint_progress"]
        selected = publishable[:4] or [item for item in results if item.payload.get("basis") == "stint_progress"][:4]
        series = []
        values: list[float] = []
        for result in selected:
            samples = result.payload.get("samples", [])
            x = [float(row["x"]) for row in samples]
            y = [float(row["lap_time_seconds"]) for row in samples]
            values.extend(y)
            color = dataset.style.driver_colors.get(result.payload["driver"])
            series.append(SeriesSpec(label=f"{result.payload['driver']} {result.payload['label']} representative laps", x=x, y=y, render_mode="scatter", marker="o", color=color.color if color else None))
            fit = result.payload.get("fit", {})
            if x and fit.get("slope") is not None and fit.get("intercept") is not None:
                series.append(SeriesSpec(label=f"{result.payload['driver']} {result.payload['label']} observed trend", x=[min(x), max(x)], y=[float(fit["intercept"]) + float(fit["slope"]) * min(x), float(fit["intercept"]) + float(fit["slope"]) * max(x)], color=color.color if color else None, line_style="--"))
        return ChartSpec(recipe_id=self.recipe_id, title=config.title or "Observed Practice Pace Evolution", subtitle="Representative laps and fitted observed trend by run progress; causes remain unknown", x_label="Run progress (lap)", y_label="Lap time", selected_drivers=sorted({item.payload["driver"] for item in selected}), source_session=_source(dataset), warnings=sorted({value for item in selected for value in item.limitations}), metadata=_metadata("practice_observed_pace_evolution", selected), series=series, y_tick_labels=_lap_time_ticks(values), legend_location="best")


def _compound_color(compound: str) -> str:
    return {"SOFT": "#DC2626", "MEDIUM": "#EAB308", "HARD": "#D1D5DB", "INTERMEDIATE": "#14B8A6", "WET": "#2563EB"}.get(compound.upper(), "#64748B")


def _lap_time_ticks(values: list[float]) -> dict[float, str]:
    if not values:
        return {}
    span = max(values) - min(values)
    desired = max(span / 5, 0.05)
    step = next((candidate for candidate in (0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0) if candidate >= desired), 20.0)
    start = floor(min(values) / step) * step
    end = ceil(max(values) / step) * step
    return {round(start + index * step, 6): _format_lap_time(start + index * step) for index in range(int(round((end - start) / step)) + 1)}


def _format_lap_time(seconds: float) -> str:
    minutes, remainder = divmod(seconds, 60)
    return f"{int(minutes)}:{remainder:06.3f}"
