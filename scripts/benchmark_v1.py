#!/usr/bin/env python3
"""Benchmark V1 report package generation and artifact size bounds."""

from __future__ import annotations

import json
import tempfile
import time
from itertools import cycle, islice
from pathlib import Path

from f1_telemetry_charts.analysis.orchestrator import run_analysis
from f1_telemetry_charts.config.loader import load_config
from f1_telemetry_charts.config.models import ChartRecipeConfig


MAX_TEN_CHART_PACKAGE_SECONDS = 60.0
MIN_DEFAULT_PNG_BYTES = 100 * 1024
MAX_DEFAULT_PNG_BYTES = 2 * 1024 * 1024


def main() -> int:
    base_config = load_config("configs/bahrain-race.toml")
    recipe_ids = list(
        islice(
            cycle(
                [
                    "lap_time_delta",
                    "telemetry_trace",
                    "tyre_strategy",
                    "position_progression",
                ]
            ),
            10,
        )
    )
    recipes = [
        ChartRecipeConfig(recipe_id=recipe_id, title=f"{recipe_id} benchmark {index + 1}")
        for index, recipe_id in enumerate(recipe_ids)
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        config = base_config.model_copy(
            update={
                "project_id": "v1-benchmark",
                "output_dir": Path(temp_dir),
                "recipes": recipes,
            },
            deep=True,
        )
        start = time.perf_counter()
        result = run_analysis(config)
        package_seconds = time.perf_counter() - start
        png_sizes = {
            path.name: path.stat().st_size
            for path in sorted((result.output_dir / "charts").glob("*.png"))
        }

    payload = {
        "max_default_png_bytes": MAX_DEFAULT_PNG_BYTES,
        "max_ten_chart_package_seconds": MAX_TEN_CHART_PACKAGE_SECONDS,
        "min_default_png_bytes": MIN_DEFAULT_PNG_BYTES,
        "package_seconds": round(package_seconds, 4),
        "package_status": result.status,
        "png_sizes_bytes": png_sizes,
        "produced_artifacts": len(result.manifest.artifacts),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    failures = []
    if result.status != "succeeded":
        failures.append(f"package generation status was {result.status}")
    if len(result.manifest.artifacts) != 10:
        failures.append(f"expected 10 artifacts, got {len(result.manifest.artifacts)}")
    if package_seconds > MAX_TEN_CHART_PACKAGE_SECONDS:
        failures.append("10-chart package generation exceeded threshold")

    out_of_bounds = [
        name
        for name, size in png_sizes.items()
        if size < MIN_DEFAULT_PNG_BYTES or size > MAX_DEFAULT_PNG_BYTES
    ]
    if out_of_bounds:
        failures.append(
            "PNG size outside default bounds: " + ", ".join(sorted(out_of_bounds))
        )

    if failures:
        print("Benchmark failed: " + "; ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
