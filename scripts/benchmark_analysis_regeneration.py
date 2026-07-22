#!/usr/bin/env python3
"""Benchmark SPEC-004 snapshot-backed chart regeneration."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from f1_telemetry_charts.analysis.workspace import AnalysisService
from f1_telemetry_charts.config.models import DataCacheConfig, SessionConfig


MAX_REGENERATION_SECONDS = 5.0


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir) / "analysis"
        service = AnalysisService(root)
        analysis = service.create("Benchmark Analysis")

        load_start = time.perf_counter()
        analysis = service.add_session(
            analysis,
            session=SessionConfig(
                season=2023,
                event="Bahrain Grand Prix",
                session="Race",
            ),
            drivers=["VER", "PER"],
            data_cache=DataCacheConfig(
                fixture_path=Path("tests/fixtures/2023_bahrain_race_dataset.json")
            ),
        )
        load_seconds = time.perf_counter() - load_start

        session = analysis.sessions[0]
        analysis = analysis.model_copy(
            update={
                "sessions": [
                    session.model_copy(
                        update={
                            "data_cache": DataCacheConfig(
                                fixture_path=Path("missing-after-snapshot.json")
                            )
                        },
                        deep=True,
                    )
                ]
            },
            deep=True,
        )
        analysis = service.add_chart(
            analysis,
            recipe_id="lap_time_delta",
            target_session_ids=[session.session_id],
            parameters={"title": "Benchmark delta"},
        )
        chart_id = analysis.charts[0].chart_instance_id

        regeneration_start = time.perf_counter()
        analysis = service.generate_charts(analysis, [chart_id])
        regeneration_seconds = time.perf_counter() - regeneration_start
        chart = analysis.charts[0]

        payload = {
            "load_seconds": round(load_seconds, 4),
            "regeneration_seconds": round(regeneration_seconds, 4),
            "max_regeneration_seconds": MAX_REGENERATION_SECONDS,
            "chart_state": chart.generation_state,
            "snapshot_dataset_path": analysis.sessions[0].snapshot.dataset_path
            if analysis.sessions[0].snapshot
            else None,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))

        failures: list[str] = []
        if chart.generation_state != "generated":
            failures.append(f"chart state was {chart.generation_state}")
        if regeneration_seconds > MAX_REGENERATION_SECONDS:
            failures.append("regeneration exceeded threshold")
        if failures:
            print("Benchmark failed: " + "; ".join(failures))
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
