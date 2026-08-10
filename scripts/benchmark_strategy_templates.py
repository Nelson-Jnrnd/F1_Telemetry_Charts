"""Warm local benchmark for the seven SPEC-008 strategy templates."""

from __future__ import annotations

import statistics
import tempfile
import time
from pathlib import Path

from f1_telemetry_charts.charts.renderers import MatplotlibRenderer
from f1_telemetry_charts.config.models import ChartRecipeConfig, ThemeConfig
from f1_telemetry_charts.data import (
    DriverMetadata,
    LapRecord,
    SessionDataset,
    SessionMetadata,
    SourceProvenance,
    TimingAppRecord,
    TimingStreamRecord,
)
from f1_telemetry_charts.recipes.registry import default_recipe_registry


RUNS_PER_TEMPLATE = 20
TARGET_SECONDS = 3.0


def main() -> int:
    dataset = _benchmark_dataset()
    registry = default_recipe_registry()
    configurations = _configurations()
    failures: list[str] = []
    with tempfile.TemporaryDirectory() as temp_dir:
        output = Path(temp_dir)
        renderer = MatplotlibRenderer()
        theme = ThemeConfig(dpi=72)
        for recipe_id, parameters in configurations.items():
            recipe = registry.create(recipe_id)
            recipe.build_spec(
                dataset,
                ChartRecipeConfig(recipe_id=recipe_id, parameters=parameters),
            )
            durations: list[float] = []
            for run in range(RUNS_PER_TEMPLATE):
                started = time.perf_counter()
                spec = recipe.build_spec(
                    dataset,
                    ChartRecipeConfig(recipe_id=recipe_id, parameters=parameters),
                )
                renderer.render(
                    spec,
                    theme=theme,
                    output_dir=output,
                    artifact_id=f"{recipe_id}-{run}",
                )
                durations.append(time.perf_counter() - started)
            p95 = _percentile(durations, 0.95)
            median = statistics.median(durations)
            print(
                f"{recipe_id}: median={median:.3f}s p95={p95:.3f}s "
                f"target<={TARGET_SECONDS:.3f}s"
            )
            if p95 > TARGET_SECONDS:
                failures.append(f"{recipe_id} p95 {p95:.3f}s exceeds target")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print("OK: all strategy templates meet the warm p95 target")
    return 0


def _percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return ordered[lower] + fraction * (ordered[upper] - ordered[lower])


def _configurations() -> dict[str, dict]:
    pair = {
        "driver_selection_mode": "selected",
        "drivers": ["D00", "D01"],
    }
    return {
        "tyre_strategy": {
            "selection": {"driver_selection_mode": "all_session"},
        },
        "stint_pace": {
            "selection": {**pair, "stints": ["D00:1", "D00:2", "D01:1", "D01:2"]},
        },
        "pace_evolution": {
            "selection": {**pair, "stints": ["D00:1", "D00:2", "D01:1", "D01:2"]},
        },
        "compound_comparison": {
            "selection": pair,
            "analysis": {
                "comparison_mode": "unrestricted_distribution",
                "compounds": ["SOFT", "HARD"],
            },
        },
        "race_time_delta_evolution": {
            "selection": {**pair, "focal_driver": "D01"},
            "analysis": {
                "delta_mode": "measured_gap_change",
                "reference_driver": "D00",
            },
        },
        "pit_cycle_comparison": {
            "selection": {**pair, "focal_driver": "D00", "rival_driver": "D01"},
            "analysis": {"pit_stop_lap": 30, "post_stop_window": 3},
        },
        "driver_battle": {"selection": pair},
    }


def _benchmark_dataset() -> SessionDataset:
    driver_codes = [f"D{index:02d}" for index in range(20)]
    laps: list[LapRecord] = []
    timing: list[TimingStreamRecord] = []
    timing_app: list[TimingAppRecord] = []
    for lap_number in range(1, 61):
        start = float((lap_number - 1) * 90)
        end = float(lap_number * 90)
        for driver_index, driver in enumerate(driver_codes):
            stint = 1 if lap_number <= 30 else 2
            age = lap_number if stint == 1 else lap_number - 30
            compound = "SOFT" if stint == 1 else "HARD"
            focal_stop = driver == "D00"
            laps.append(
                LapRecord(
                    driver=driver,
                    lap_number=lap_number,
                    lap_start_time_seconds=start,
                    lap_end_time_seconds=end,
                    lap_time_seconds=89.0 + driver_index * 0.08 + age * 0.025,
                    compound=compound,
                    stint=stint,
                    position=driver_index + 1,
                    is_pit_in_lap=focal_stop and lap_number == 30,
                    is_pit_out_lap=focal_stop and lap_number == 31,
                    pit_in_time_seconds=end - 20 if focal_stop and lap_number == 30 else None,
                    pit_out_time_seconds=start + 20 if focal_stop and lap_number == 31 else None,
                    is_accurate=True,
                    sector_1_time_seconds=29.0 + age * 0.008,
                    sector_2_time_seconds=36.0 + age * 0.009,
                    sector_3_time_seconds=24.0 + age * 0.008,
                    track_status="1",
                )
            )
            timing.append(
                TimingStreamRecord(
                    driver=driver,
                    session_time_seconds=end,
                    position=driver_index + 1,
                    gap_to_leader_seconds=driver_index * (1.0 + lap_number * 0.002),
                    interval_to_ahead_seconds=0.0 if driver_index == 0 else 1.0,
                    gap_parse_status="leader" if driver_index == 0 else "parsed",
                    interval_parse_status="leader" if driver_index == 0 else "parsed",
                )
            )
            timing_app.append(
                TimingAppRecord(
                    driver=driver,
                    session_time_seconds=end,
                    lap_number=lap_number,
                    stint=stint,
                    total_laps=float(age),
                    compound=compound,
                    start_laps=1.0,
                )
            )
    return SessionDataset(
        metadata=SessionMetadata(season=2026, event="Benchmark GP", session="Race"),
        drivers=[DriverMetadata(abbreviation=driver) for driver in driver_codes],
        laps=laps,
        timing=timing,
        timing_app=timing_app,
        provenance=SourceProvenance(provider="benchmark", cache_status="fixture"),
    )


if __name__ == "__main__":
    raise SystemExit(main())
