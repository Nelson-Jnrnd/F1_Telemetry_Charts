"""Fixture-backed session gateway for deterministic tests and examples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from f1_telemetry_charts.data.gateways.base import DataGatewayError
from f1_telemetry_charts.data.models import (
    SessionDataset,
    SessionQuery,
    requests_all_drivers,
)
from f1_telemetry_charts.data.track_geometry import ensure_track_geometry


class FixtureSessionGateway:
    def __init__(self, fixture_path: str | Path):
        self.fixture_path = Path(fixture_path)

    def load_session(self, query: SessionQuery) -> SessionDataset:
        if not self.fixture_path.exists():
            raise DataGatewayError(f"Fixture dataset not found: {self.fixture_path}")

        raw = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        dataset = SessionDataset.model_validate(raw)
        _assert_query_matches_fixture(query, dataset)
        return ensure_track_geometry(dataset).filter_drivers(query.drivers)


def _assert_query_matches_fixture(
    query: SessionQuery, dataset: SessionDataset
) -> None:
    metadata = dataset.metadata
    mismatches: list[str] = []
    if metadata.season != query.season:
        mismatches.append(f"season {query.season}")
    if metadata.event != query.event:
        mismatches.append(f"event {query.event}")
    if metadata.session != query.session:
        mismatches.append(f"session {query.session}")

    if not requests_all_drivers(query.drivers):
        available_drivers = {driver.abbreviation for driver in dataset.drivers}
        missing_drivers = [driver for driver in query.drivers if driver not in available_drivers]
        if missing_drivers:
            mismatches.append(f"drivers {', '.join(missing_drivers)}")

    if mismatches:
        raise DataGatewayError(
            "Fixture dataset does not match query: " + "; ".join(mismatches)
        )
