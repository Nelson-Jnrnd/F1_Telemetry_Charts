from __future__ import annotations

import sys
import tempfile
import types
import unittest
from collections import defaultdict
from pathlib import Path
from unittest.mock import patch

from f1_telemetry_charts.data import DataGatewayError, SessionQuery
from f1_telemetry_charts.data.gateways import FastF1SessionGateway
from f1_telemetry_charts.data.gateways.fastf1 import (
    _telemetry_samples_from_lap_methods,
    _telemetry_samples_from_laps,
)


class FastF1GatewayTests(unittest.TestCase):
    def test_cache_only_requires_existing_cache_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_cache = Path(temp_dir) / "missing"
            gateway = FastF1SessionGateway(missing_cache, cache_only=True)

            with self.assertRaises(DataGatewayError) as raised:
                gateway.load_session(_query())

        self.assertIn("cache-only mode", str(raised.exception))

    def test_fastf1_gateway_normalizes_fastf1_shaped_session(self) -> None:
        fake_fastf1 = _fake_fastf1_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(sys.modules, {"fastf1": fake_fastf1}):
                dataset = FastF1SessionGateway(temp_dir).load_session(_query())

        self.assertEqual(dataset.metadata.season, 2023)
        self.assertEqual(dataset.metadata.event, "Bahrain Grand Prix")
        self.assertEqual(dataset.provenance.provider, "FastF1")
        self.assertEqual(dataset.drivers[0].abbreviation, "VER")
        self.assertEqual(dataset.laps[0].lap_time_seconds, 96.0)
        self.assertEqual(dataset.weather[0].air_temp_c, 26.0)
        self.assertEqual(dataset.missing_data[0].field, "telemetry")

    def test_fastf1_gateway_records_cache_only_provenance(self) -> None:
        fake_fastf1 = _fake_fastf1_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(sys.modules, {"fastf1": fake_fastf1}):
                dataset = FastF1SessionGateway(temp_dir, cache_only=True).load_session(
                    _query()
                )

        self.assertEqual(dataset.provenance.cache_status, "cache-only")
        self.assertFalse(dataset.provenance.fetched_from_network)
        self.assertEqual(fake_fastf1._offline_modes, [True, False])

    def test_grouped_telemetry_matches_fastf1_lap_methods_for_cached_smoke(self) -> None:
        cache_dir = Path(".cache/fastf1-smoke")
        if not cache_dir.exists():
            self.skipTest("FastF1 smoke cache is not available")

        try:
            import fastf1
        except ImportError:
            self.skipTest("FastF1 is not installed")

        fastf1.Cache.enable_cache(str(cache_dir))
        fastf1.Cache.offline_mode(True)
        try:
            session = fastf1.get_session(2023, "Bahrain Grand Prix", "Race")
            session.load(laps=True, telemetry=True, weather=True, messages=False)
        finally:
            fastf1.Cache.offline_mode(False)

        laps = session.laps.pick_drivers(["VER", "PER"])
        optimized = _telemetry_samples_from_laps(laps, session=session)
        reference = _telemetry_samples_from_lap_methods(laps)

        optimized_by_lap = _samples_by_lap(optimized)
        reference_by_lap = _samples_by_lap(reference)
        self.assertEqual(set(optimized_by_lap), set(reference_by_lap))

        for key, reference_samples in reference_by_lap.items():
            optimized_samples = optimized_by_lap[key]
            self.assertEqual(len(optimized_samples), len(reference_samples), key)
            for optimized_sample, reference_sample in zip(
                optimized_samples, reference_samples, strict=True
            ):
                self.assertAlmostEqual(
                    optimized_sample.distance_m,
                    reference_sample.distance_m,
                    places=9,
                    msg=str(key),
                )
                self.assertEqual(optimized_sample.speed_kph, reference_sample.speed_kph)
                self.assertEqual(
                    optimized_sample.throttle_percent,
                    reference_sample.throttle_percent,
                )
                self.assertEqual(optimized_sample.brake, reference_sample.brake)
                self.assertEqual(optimized_sample.gear, reference_sample.gear)


def _query() -> SessionQuery:
    return SessionQuery(
        season=2023,
        event="Bahrain Grand Prix",
        session="Race",
        drivers=["VER"],
    )


def _fake_fastf1_module():
    module = types.SimpleNamespace()
    module._offline_modes = []
    module.Cache = types.SimpleNamespace(
        enable_cache=lambda _: None,
        offline_mode=lambda enabled: module._offline_modes.append(enabled),
    )
    module.get_session = lambda *_: _FakeSession()
    return module


def _samples_by_lap(samples):
    grouped = defaultdict(list)
    for sample in samples:
        grouped[(sample.driver, sample.lap_number)].append(sample)
    return grouped


class _FakeSession:
    name = "Race"
    event = types.SimpleNamespace(RoundNumber=1)

    def __init__(self) -> None:
        self.laps = _FakeLaps(
            [
                {
                    "Driver": "VER",
                    "LapNumber": 1,
                    "LapTime": _Duration(96.0),
                    "Compound": "SOFT",
                    "Stint": 1,
                    "Position": 1,
                    "PitInTime": None,
                    "PitOutTime": None,
                }
            ]
        )
        self.results = _FakeRows(
            [
                {
                    "DriverNumber": "1",
                    "Abbreviation": "VER",
                    "FullName": "Max Verstappen",
                    "TeamName": "Red Bull Racing",
                    "TeamColor": "#3671C6",
                }
            ]
        )
        self.weather_data = _FakeRows(
            [
                {
                    "Time": _Duration(0.0),
                    "AirTemp": 26.0,
                    "TrackTemp": 31.0,
                    "Humidity": 40.0,
                    "Rainfall": False,
                }
            ]
        )

    def load(self, **_: object) -> None:
        return None


class _FakeRows:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self._rows = rows

    def iterrows(self):
        for index, row in enumerate(self._rows):
            yield index, row


class _FakeLaps(_FakeRows):
    def pick_drivers(self, drivers: list[str]):
        return _FakeLaps([row for row in self._rows if row["Driver"] in drivers])


class _Duration:
    def __init__(self, seconds: float) -> None:
        self._seconds = seconds

    def total_seconds(self) -> float:
        return self._seconds


if __name__ == "__main__":
    unittest.main()
