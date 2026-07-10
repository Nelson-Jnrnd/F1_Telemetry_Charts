from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from f1_telemetry_charts.data import DataGatewayError, SessionQuery
from f1_telemetry_charts.data.gateways import FastF1SessionGateway


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


def _query() -> SessionQuery:
    return SessionQuery(
        season=2023,
        event="Bahrain Grand Prix",
        session="Race",
        drivers=["VER"],
    )


def _fake_fastf1_module():
    module = types.SimpleNamespace()
    module.Cache = types.SimpleNamespace(enable_cache=lambda _: None)
    module.get_session = lambda *_: _FakeSession()
    return module


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
