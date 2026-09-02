from __future__ import annotations

import argparse
import statistics
from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

from f1_telemetry_charts.analysis.playback import clear_playback_caches
from f1_telemetry_charts.analysis.workspace import (
    AnalysisService,
    _read_snapshot_dataset_cached,
)
from f1_telemetry_charts.ui.server import create_app


MAXIMUM_COLD_SECONDS = 1.0
MAXIMUM_WARM_MEDIAN_SECONDS = 0.1


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark cached race playback frames.")
    parser.add_argument("analysis", type=Path, help="Analysis workspace directory")
    parser.add_argument("--session-id", help="Loaded session id; defaults to the first session")
    parser.add_argument(
        "--laps",
        default="1,2,10,30,57,30",
        help="Comma-separated lap cursors; repeat a lap to measure frame-cache reuse",
    )
    args = parser.parse_args()

    root = args.analysis.resolve()
    service = AnalysisService(root)
    analysis = service.open_for_playback()
    session = next(
        (
            item
            for item in analysis.sessions
            if args.session_id is None or item.session_id == args.session_id
        ),
        None,
    )
    if session is None:
        raise SystemExit("No matching session found")

    laps = [int(value.strip()) for value in args.laps.split(",") if value.strip()]
    client = TestClient(create_app())
    opened = client.post("/api/analysis/open", json={"path": str(root)})
    opened.raise_for_status()
    _read_snapshot_dataset_cached.cache_clear()
    clear_playback_caches()

    timings: list[float] = []
    for lap in laps:
        started = perf_counter()
        response = client.post(
            "/api/analysis/playback",
            json={
                "session_id": session.session_id,
                "mode": "lap",
                "cursor": lap,
                "max_frames": 1,
                "max_markers": 60,
                "max_points": 500,
            },
        )
        elapsed = perf_counter() - started
        response.raise_for_status()
        timings.append(elapsed)
        print(f"lap={lap} seconds={elapsed:.4f} bytes={len(response.content)}")

    warm_median = statistics.median(timings[1:]) if len(timings) > 1 else 0.0
    if len(timings) > 1:
        print(f"warm_median_seconds={warm_median:.4f}")
    print(f"cold_seconds={timings[0]:.4f}")
    passed = (
        timings[0] <= MAXIMUM_COLD_SECONDS
        and warm_median <= MAXIMUM_WARM_MEDIAN_SECONDS
    )
    print(
        "playback_benchmark="
        f"{'PASS' if passed else 'FAIL'} "
        f"(cold<={MAXIMUM_COLD_SECONDS:.1f}s, "
        f"warm_median<={MAXIMUM_WARM_MEDIAN_SECONDS:.1f}s)"
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
