from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from f1_telemetry_charts.data import (
    FastF1EventCatalog,
    FixtureEventCatalog,
    normalize_session_type,
)
from f1_telemetry_charts.ui.server import create_app


class _Rows:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows

    def iterrows(self):
        return enumerate(self.rows)


class EventDiscoveryTests(unittest.TestCase):
    def test_fastf1_catalog_normalizes_event_and_available_sessions(self) -> None:
        catalog = FastF1EventCatalog(
            lambda _season: _Rows(
                [
                    {
                        "RoundNumber": 1,
                        "EventName": "Bahrain Grand Prix",
                        "OfficialEventName": "FORMULA 1 BAHRAIN GRAND PRIX",
                        "Country": "Bahrain",
                        "Location": "Sakhir",
                        "EventDate": "2026-03-08T00:00:00",
                        "EventFormat": "conventional",
                        "Session1": "Practice 1",
                        "Session1DateUtc": "2026-03-06T11:30:00Z",
                        "Session2": "Qualifying",
                        "Session2DateUtc": "2026-03-07T15:00:00Z",
                        "Session3": "Race",
                        "Session3DateUtc": "2026-03-08T15:00:00Z",
                    }
                ]
            )
        )

        result = catalog.events_for_season(2026)

        self.assertEqual(result.season, 2026)
        self.assertEqual(result.events[0].country, "Bahrain")
        self.assertEqual(result.events[0].event_date.isoformat(), "2026-03-08")
        self.assertEqual(
            [session.session_type for session in result.events[0].sessions],
            ["practice", "qualifying", "race"],
        )

    def test_fixture_catalog_and_api_are_deterministic_and_grouped_by_year(self) -> None:
        catalog = FixtureEventCatalog(
            [
                {
                    "season": 2026,
                    "events": [
                        {
                            "round_number": 1,
                            "event_name": "Synthetic Grand Prix",
                            "country": "Testland",
                            "sessions": [{"name": "Sprint", "session_type": "sprint"}],
                        }
                    ],
                }
            ]
        )
        response = TestClient(create_app(event_catalog=catalog)).get(
            "/api/analysis/events?year=2025&year=2026&year=2026"
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([item["season"] for item in response.json()], [2025, 2026])
        self.assertEqual(response.json()[0]["events"], [])
        self.assertEqual(response.json()[1]["events"][0]["country"], "Testland")

    def test_session_type_aliases_normalize_for_template_filtering(self) -> None:
        self.assertEqual(normalize_session_type("FP2"), "practice")
        self.assertEqual(normalize_session_type("Sprint Shootout"), "sprint_qualifying")
        self.assertEqual(normalize_session_type("Sprint"), "sprint")
        self.assertEqual(normalize_session_type("Race"), "race")


if __name__ == "__main__":
    unittest.main()
