#!/usr/bin/env python3
"""Benchmark the MVP fixture-backed package generation path."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.charts.renderers import MatplotlibRenderer
from f1_telemetry_charts.config.loader import load_config
from f1_telemetry_charts.data import SessionQuery
from f1_telemetry_charts.data.gateways import FixtureSessionGateway
from f1_telemetry_charts.recipes.registry import default_recipe_registry


MAX_DATA_LOAD_SECONDS = 10.0
MAX_SINGLE_RENDER_SECONDS = 5.0


def main() -> int:
    config = load_config("configs/bahrain-race.toml")
    query = SessionQuery(
        season=config.session.season,
        event=config.session.event,
        session=config.session.session,
        drivers=config.driver_selection.drivers,
    )

    data_start = time.perf_counter()
    dataset = FixtureSessionGateway(
        config.data_cache.fixture_path or Path("tests/fixtures/2023_bahrain_race_dataset.json")
    ).load_session(query)
    data_load_seconds = time.perf_counter() - data_start

    registry = default_recipe_registry()
    renderer = MatplotlibRenderer()
    render_timings: dict[str, float] = {}
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        for recipe_config in config.recipes:
            recipe = registry.create(recipe_config.recipe_id)
            spec = recipe.build_spec(dataset, recipe_config)
            render_start = time.perf_counter()
            renderer.render(
                spec,
                theme=config.theme,
                output_dir=output_dir,
                artifact_id=recipe_config.recipe_id,
            )
            render_timings[recipe_config.recipe_id] = time.perf_counter() - render_start

    with tempfile.TemporaryDirectory() as temp_dir:
        run_config = config.model_copy(update={"output_dir": Path(temp_dir)}, deep=True)
        package_start = time.perf_counter()
        result = run_analysis(run_config)
        package_seconds = time.perf_counter() - package_start

    payload = {
        "data_load_seconds": round(data_load_seconds, 4),
        "max_data_load_seconds": MAX_DATA_LOAD_SECONDS,
        "render_timings_seconds": {
            key: round(value, 4) for key, value in sorted(render_timings.items())
        },
        "max_single_render_seconds": MAX_SINGLE_RENDER_SECONDS,
        "package_seconds": round(package_seconds, 4),
        "package_status": result.status,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    failures = []
    if data_load_seconds > MAX_DATA_LOAD_SECONDS:
        failures.append("data load exceeded threshold")
    slow_renders = [
        recipe_id
        for recipe_id, seconds in render_timings.items()
        if seconds > MAX_SINGLE_RENDER_SECONDS
    ]
    if slow_renders:
        failures.append("render exceeded threshold: " + ", ".join(sorted(slow_renders)))
    if result.status != "succeeded":
        failures.append(f"package generation status was {result.status}")

    if failures:
        print("Benchmark failed: " + "; ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
