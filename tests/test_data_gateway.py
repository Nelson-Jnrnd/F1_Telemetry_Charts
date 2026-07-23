from __future__ import annotations

import unittest
from pathlib import Path

from f1_telemetry_charts.data import DataGatewayError, SessionQuery
from f1_telemetry_charts.data.gateways import FixtureSessionGateway


FIXTURE_PATH = Path("tests/fixtures/2023_bahrain_race_dataset.json")


class DataGatewayTests(unittest.TestCase):
    def test_fixture_gateway_loads_normalized_dataset(self) -> None:
        gateway = FixtureSessionGateway(FIXTURE_PATH)

        dataset = gateway.load_session(_query(["VER", "PER"]))

        self.assertEqual(dataset.metadata.season, 2023)
        self.assertEqual(dataset.metadata.event, "Bahrain Grand Prix")
        self.assertEqual(dataset.provenance.cache_status, "fixture")
        self.assertFalse(dataset.provenance.fetched_from_network)
        self.assertEqual([driver.abbreviation for driver in dataset.drivers], ["VER", "PER"])
        self.assertTrue(dataset.laps)
        self.assertTrue(dataset.telemetry)
        self.assertTrue(dataset.weather)
        self.assertEqual({lap.driver for lap in dataset.laps}, {"VER", "PER"})

    def test_fixture_gateway_loads_all_drivers_when_requested(self) -> None:
        gateway = FixtureSessionGateway(FIXTURE_PATH)

        dataset = gateway.load_session(_query(["*"]))

        self.assertEqual(
            [driver.abbreviation for driver in dataset.drivers],
            ["VER", "PER", "ALO"],
        )
        self.assertEqual({lap.driver for lap in dataset.laps}, {"VER", "PER", "ALO"})

    def test_fixture_gateway_rejects_session_mismatch(self) -> None:
        gateway = FixtureSessionGateway(FIXTURE_PATH)
        query = SessionQuery(
            season=2023,
            event="Monaco Grand Prix",
            session="Race",
            drivers=["VER"],
        )

        with self.assertRaises(DataGatewayError) as raised:
            gateway.load_session(query)

        self.assertIn("event Monaco Grand Prix", str(raised.exception))

    def test_fixture_gateway_rejects_missing_driver(self) -> None:
        gateway = FixtureSessionGateway(FIXTURE_PATH)

        with self.assertRaises(DataGatewayError) as raised:
            gateway.load_session(_query(["HAM"]))

        self.assertIn("drivers HAM", str(raised.exception))


def _query(drivers: list[str]) -> SessionQuery:
    return SessionQuery(
        season=2023,
        event="Bahrain Grand Prix",
        session="Race",
        drivers=drivers,
    )


if __name__ == "__main__":
    unittest.main()
