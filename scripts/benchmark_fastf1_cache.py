#!/usr/bin/env python3
"""Benchmark FastF1 cache-only loading for the canonical MVP smoke session."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from f1_telemetry_charts.data import SessionQuery
from f1_telemetry_charts.data.gateways import FastF1SessionGateway


MAX_CACHE_LOAD_SECONDS = 10.0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark cache-only FastF1 session loading."
    )
    parser.add_argument(
        "--cache-dir",
        default=".cache/fastf1-smoke",
        help="Populated FastF1 cache directory to use.",
    )
    args = parser.parse_args()

    cache_dir = Path(args.cache_dir)
    query = SessionQuery(
        season=2023,
        event="Bahrain Grand Prix",
        session="Race",
        drivers=["VER", "PER"],
    )

    start = time.perf_counter()
    dataset = FastF1SessionGateway(cache_dir, cache_only=True).load_session(query)
    load_seconds = time.perf_counter() - start

    payload = {
        "cache_dir": str(cache_dir),
        "data_load_seconds": round(load_seconds, 4),
        "max_cache_load_seconds": MAX_CACHE_LOAD_SECONDS,
        "laps": len(dataset.laps),
        "telemetry_samples": len(dataset.telemetry),
        "weather_samples": len(dataset.weather),
        "fetched_from_network": dataset.provenance.fetched_from_network,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))

    failures = []
    if load_seconds > MAX_CACHE_LOAD_SECONDS:
        failures.append("cache-only FastF1 load exceeded threshold")
    if dataset.provenance.fetched_from_network:
        failures.append("cache-only FastF1 load reported network fetch")

    if failures:
        print("Benchmark failed: " + "; ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
